import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


EXPECTED_MEASUREMENT_KEYS = [
    "height",
    "shoulder_width",
    "arm_length",
    "torso_length",
    "inseam",
    "chest",
    "waist",
    "hip",
    "neck",
    "thigh",
    "upper_arm",
    "wrist",
    "calf",
    "ankle",
    "bicep",
]

CM_MEASUREMENTS = set(EXPECTED_MEASUREMENT_KEYS)


class SHAPYClientError(Exception):
    pass


class SHAPYServiceUnavailableError(SHAPYClientError):
    pass


class SHAPYInvalidResponseError(SHAPYClientError):
    pass


class SHAPYClient:
    def __init__(self, base_url: str, timeout: int, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    async def healthcheck(self) -> bool:
        if not self.base_url:
            return False
        headers = self._headers()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health", headers=headers)
                return response.status_code == 200
        except Exception:
            return False

    async def measure(
        self,
        front_image: bytes,
        side_image: bytes,
        height_cm: float,
        weight_kg: float,
        gender: str,
    ) -> Dict:
        if not self.base_url:
            raise SHAPYServiceUnavailableError("SHAPY_SERVICE_URL is empty")

        files = {
            "front_image": ("front.jpg", front_image, "image/jpeg"),
            "side_image": ("side.jpg", side_image, "image/jpeg"),
        }
        data = {
            "height_cm": str(height_cm),
            "weight_kg": str(weight_kg),
            "gender": gender,
        }
        headers = self._headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/measure",
                    files=files,
                    data=data,
                    headers=headers,
                )
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as exc:
            raise SHAPYServiceUnavailableError(f"SHAPY request failed: {exc}") from exc
        except Exception as exc:
            raise SHAPYClientError(f"Unexpected SHAPY client error: {exc}") from exc

        if response.status_code >= 500:
            raise SHAPYServiceUnavailableError(
                f"SHAPY service error status: {response.status_code}"
            )
        if response.status_code >= 400:
            raise SHAPYClientError(
                f"SHAPY request rejected status: {response.status_code}"
            )

        payload = response.json()
        return self._normalize_payload(payload)

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _normalize_payload(self, payload: Dict) -> Dict:
        if not isinstance(payload, dict):
            raise SHAPYInvalidResponseError("SHAPY payload is not a JSON object")

        measurements = payload.get("measurements")
        if not isinstance(measurements, dict):
            raise SHAPYInvalidResponseError("SHAPY payload missing measurements dict")

        if "hips" in measurements and "hip" not in measurements:
            measurements["hip"] = measurements.get("hips")

        normalized_measurements = {}
        for key in EXPECTED_MEASUREMENT_KEYS:
            value = measurements.get(key)
            try:
                numeric = float(value) if value is not None else None
            except (TypeError, ValueError):
                numeric = None
            normalized_measurements[key] = self._to_cm_if_needed(key, numeric)

        missing_measurements = [
            key for key in EXPECTED_MEASUREMENT_KEYS if normalized_measurements.get(key) is None
        ]

        return {
            "measurements": normalized_measurements,
            "body_type": payload.get("body_type") or "average",
            "confidence_score": float(payload.get("confidence_score") or 0.7),
            "missing_measurements": missing_measurements,
            "missing_reason": payload.get("missing_reason")
            or (
                "Current SHAPY endpoint output only includes a subset "
                "(height/chest/waist/hip) for this pipeline."
                if missing_measurements
                else None
            ),
        }

    def _to_cm_if_needed(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if key not in CM_MEASUREMENTS:
            return value
        # SHAPY outputs can be in meters; backend contract expects centimeters.
        if 0 < value < 10:
            return round(value * 100.0, 2)
        return round(value, 2)
