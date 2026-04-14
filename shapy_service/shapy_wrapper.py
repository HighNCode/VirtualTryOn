import json
import logging
import os
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from measurement_engine.constants import REQUIRED_JOINTS


logger = logging.getLogger(__name__)


class ShapyWrapper:
    """
    SHAPY inference wrapper based on the official regressor demo flow.
    """

    def __init__(self, data_dir: str, checkpoint_path: str):
        self.data_dir = data_dir
        self.checkpoint_path = checkpoint_path
        self._shapy_python = os.environ.get("SHAPY_PYTHON", "python")
        self._service_root = Path(__file__).resolve().parent
        repo_dir = os.environ.get("SHAPY_REPO_DIR")
        if repo_dir:
            self._shapy_root = Path(repo_dir)
        elif Path("/root/shapy").exists():
            self._shapy_root = Path("/root/shapy")
        else:
            self._shapy_root = self._service_root / "shapy"
        self._regressor_root = self._shapy_root / "regressor"
        self._initialized = False
        self._init_error = None
        self._mp_pose = None
        self._diagnostic_logs_enabled = os.environ.get("SHAPY_DIAGNOSTIC_LOGS", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            if not self.data_dir or not os.path.exists(self.data_dir):
                raise FileNotFoundError(f"SHAPY_DATA_DIR not found: {self.data_dir}")
            if not self.checkpoint_path or not os.path.exists(self.checkpoint_path):
                raise FileNotFoundError(
                    f"SHAPY_CHECKPOINT not found: {self.checkpoint_path}"
                )
            if not self._regressor_root.exists():
                raise FileNotFoundError(f"Missing SHAPY regressor dir: {self._regressor_root}")

            import mediapipe as mp  # noqa: F401

            probe = subprocess.run(
                [self._shapy_python, "-c", "import torch, human_shape; print('ok')"],
                env=os.environ.copy(),
                capture_output=True,
                text=True,
            )
            if probe.returncode != 0:
                raise RuntimeError(
                    f"SHAPY Python env probe failed: {probe.stderr[-400:]}"
                )

            self._validate_required_joint_names()
            self._initialized = True
            logger.info("SHAPY wrapper initialized")
        except Exception as exc:
            self._init_error = str(exc)
            logger.exception("SHAPY wrapper failed to initialize")

    def _validate_required_joint_names(self) -> None:
        code = (
            "from human_shape.data.utils.keypoint_names import KEYPOINT_NAMES_DICT\n"
            "import json\n"
            "print(json.dumps(KEYPOINT_NAMES_DICT.get('smplx', [])))"
        )
        proc = subprocess.run(
            [self._shapy_python, "-c", code],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to validate SHAPY keypoints: {proc.stderr[-600:]}")
        try:
            names = set(json.loads(proc.stdout.strip()))
        except Exception as exc:
            raise RuntimeError("Unable to parse SHAPY keypoint names.") from exc
        missing = [name for name in REQUIRED_JOINTS if name not in names]
        if missing:
            raise RuntimeError(f"Required SHAPY joints missing from SMPL-X schema: {missing}")

    @property
    def ready(self) -> bool:
        return self._initialized

    @property
    def init_error(self) -> str:
        return self._init_error or ""

    def measure(
        self,
        front_image: bytes,
        side_image: bytes,
        height_cm: float,
        weight_kg: float,
        gender: str,
    ) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError(f"SHAPY model not ready: {self.init_error}")

        with tempfile.TemporaryDirectory(prefix="shapy_infer_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            samples_dir = tmp_path / "samples"
            images_dir = samples_dir / "images"
            keyps_dir = samples_dir / "openpose"
            output_dir = tmp_path / "output"
            images_dir.mkdir(parents=True, exist_ok=True)
            keyps_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            (images_dir / "front.jpg").write_bytes(front_image)
            (images_dir / "side.jpg").write_bytes(side_image)

            self._write_openpose_file(front_image, keyps_dir / "front_keypoints.json")
            self._write_openpose_file(side_image, keyps_dir / "side_keypoints.json")

            self._run_shapy_demo(samples_dir=samples_dir, output_dir=output_dir)

            front = self._compute_full_measurements_from_npz(
                npz_path=output_dir / "front.npz",
                height_cm=height_cm,
            )
            side = self._compute_full_measurements_from_npz(
                npz_path=output_dir / "side.npz",
                height_cm=height_cm,
            )
            merged = self._merge_measurements(front, side)

            measurements = merged["measurements"]
            diagnostics = merged["diagnostics"]
            missing = [k for k, v in measurements.items() if v is None]
            low_quality = [
                k for k, d in diagnostics.items()
                if (
                    isinstance(d, dict)
                    and (
                        float((d.get("front") or {}).get("quality_score", 1.0)) < 0.45
                        or float((d.get("side") or {}).get("quality_score", 1.0)) < 0.45
                    )
                )
            ]
            if low_quality:
                logger.warning("Low-quality SHAPY metrics detected: %s", low_quality)
            if self._diagnostic_logs_enabled:
                self._log_metric_diagnostics(measurements, diagnostics, missing, low_quality)
            return {
                "measurements": measurements,
                "diagnostics": diagnostics,
                "body_type": "average",
                "confidence_score": merged["confidence_score"],
                "missing_measurements": missing,
                "missing_reason": None
                if not missing
                else "Some SHAPY measurements were unavailable from mesh geometry.",
            }

    def _get_pose_detector(self):
        if self._mp_pose is not None:
            return self._mp_pose
        import mediapipe as mp

        self._mp_pose = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=2,
            min_detection_confidence=0.5,
        )
        return self._mp_pose

    def _write_openpose_file(self, image_bytes: bytes, out_path: Path) -> None:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        h, w = arr.shape[:2]
        pose = self._get_pose_detector()
        result = pose.process(arr)
        if not result.pose_landmarks:
            raise RuntimeError("MediaPipe failed to detect pose for SHAPY keypoint generation")

        lms = result.pose_landmarks.landmark

        def to_xyv(idx):
            lm = lms[idx]
            return [float(lm.x * w), float(lm.y * h), float(max(0.0, min(1.0, lm.visibility)))]

        body = [[0.0, 0.0, 0.0] for _ in range(25)]
        body[0] = to_xyv(0)
        body[2] = to_xyv(12)
        body[3] = to_xyv(14)
        body[4] = to_xyv(16)
        body[5] = to_xyv(11)
        body[6] = to_xyv(13)
        body[7] = to_xyv(15)
        body[9] = to_xyv(24)
        body[10] = to_xyv(26)
        body[11] = to_xyv(28)
        body[12] = to_xyv(23)
        body[13] = to_xyv(25)
        body[14] = to_xyv(27)
        body[15] = to_xyv(5)
        body[16] = to_xyv(2)
        body[17] = to_xyv(8)
        body[18] = to_xyv(7)
        body[19] = to_xyv(31)
        body[21] = to_xyv(29)
        body[22] = to_xyv(32)
        body[24] = to_xyv(30)

        def midpoint(a, b):
            return [
                (a[0] + b[0]) / 2.0,
                (a[1] + b[1]) / 2.0,
                min(a[2], b[2]),
            ]

        body[1] = midpoint(body[2], body[5])
        body[8] = midpoint(body[9], body[12])
        body[20] = body[19]
        body[23] = body[22]

        payload = {
            "version": 1.3,
            "people": [
                {
                    "pose_keypoints_2d": [v for p in body for v in p],
                    "face_keypoints_2d": [0.0] * (70 * 3),
                    "hand_left_keypoints_2d": [0.0] * (21 * 3),
                    "hand_right_keypoints_2d": [0.0] * (21 * 3),
                }
            ],
        }
        out_path.write_text(json.dumps(payload), encoding="utf-8")

    def _run_shapy_demo(self, samples_dir: Path, output_dir: Path) -> None:
        cmd = [
            self._shapy_python,
            "demo.py",
            "--save-vis",
            "false",
            "--save-params",
            "true",
            "--save-mesh",
            "false",
            "--split",
            "test",
            "--datasets",
            "openpose",
            "--output-folder",
            str(output_dir),
            "--exp-cfg",
            "configs/b2a_expose_hrnet_demo.yaml",
            "--exp-opts",
            f"output_folder={self.data_dir}/trained_models/shapy/SHAPY_A",
            "part_key=pose",
            f"datasets.pose.openpose.data_folder={samples_dir}",
            "datasets.pose.openpose.img_folder=images",
            "datasets.pose.openpose.keyp_folder=openpose",
            "datasets.batch_size=1",
            "datasets.pose_shape_ratio=1.0",
            "network.smplx.use_b2a=false",
            "network.smplx.use_a2b=false",
            "network.smplx.compute_measurements=true",
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(self._regressor_root),
            env={
                **os.environ.copy(),
                "PYOPENGL_PLATFORM": "egl",
            },
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"SHAPY demo failed ({proc.returncode}). stderr: {proc.stderr[-1200:]}"
            )

    def _compute_full_measurements_from_npz(
        self,
        npz_path: Path,
        height_cm: float,
    ) -> Dict[str, Any]:
        if not npz_path.exists():
            raise FileNotFoundError(f"Missing SHAPY output file: {npz_path}")

        runner_path = self._service_root / "shapy_measurement_runner.py"
        cmd = [
            self._shapy_python,
            str(runner_path),
            "--npz",
            str(npz_path),
            "--height-cm",
            str(height_cm),
        ]
        calibration_path = os.environ.get("SHAPY_CALIBRATION_PATH")
        if calibration_path:
            cmd.extend(["--calibration-path", calibration_path])

        proc = subprocess.run(
            cmd,
            env={**os.environ.copy(), "PYOPENGL_PLATFORM": "egl"},
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to parse SHAPY npz via SHAPY_PYTHON. stderr: {proc.stderr[-900:]}"
            )
        try:
            payload = json.loads(proc.stdout.strip())
        except Exception as exc:
            raise RuntimeError(f"Invalid SHAPY measurement output: {proc.stdout[-600:]}") from exc

        measurements = payload.get("measurements") or {}
        diagnostics = payload.get("diagnostics") or {}
        return {
            "measurements": measurements,
            "diagnostics": diagnostics,
            "confidence_score": float(payload.get("confidence_score", 0.0)),
        }

    def _merge_measurements(self, front: Dict[str, Any], side: Dict[str, Any]) -> Dict[str, Any]:
        merged_measurements: Dict[str, Any] = {}
        merged_diagnostics: Dict[str, Any] = {}

        front_m = front.get("measurements") or {}
        side_m = side.get("measurements") or {}
        front_d = front.get("diagnostics") or {}
        side_d = side.get("diagnostics") or {}
        keys: List[str] = sorted(set(front_m.keys()) | set(side_m.keys()))

        def score(diag: Dict[str, Any]) -> float:
            try:
                return float(diag.get("quality_score", 0.65))
            except Exception:
                return 0.65

        for key in keys:
            fv = front_m.get(key)
            sv = side_m.get(key)
            fd = front_d.get(key, {})
            sd = side_d.get(key, {})
            divergence_flag = False
            if fv is not None and sv is not None:
                fw = max(0.01, score(fd))
                sw = max(0.01, score(sd))
                merged_value = round((fv * fw + sv * sw) / (fw + sw), 1)
                if key == "chest":
                    # Divergence guard: avoid selecting an anatomically implausible outlier side.
                    rel_diff = abs(fv - sv) / max(1e-6, max(abs(fv), abs(sv)))
                    if rel_diff > 0.15:
                        divergence_flag = True
                        merged_value = round(min(fv, sv), 1)
            else:
                merged_value = fv if fv is not None else sv
            merged_measurements[key] = merged_value

            front_quality = score(fd) if fv is not None else 0.0
            side_quality = score(sd) if sv is not None else 0.0
            if fv is not None and sv is not None:
                metric_quality = (front_quality + side_quality) / 2.0
            else:
                metric_quality = max(front_quality, side_quality) * 0.9
            if fd.get("fallback_path") or sd.get("fallback_path"):
                metric_quality -= 0.10
            if fd.get("filter_relaxed") or sd.get("filter_relaxed"):
                metric_quality -= 0.15
            if (fd.get("loop_count") or 0) > 1 or (sd.get("loop_count") or 0) > 1:
                metric_quality -= 0.10
            if divergence_flag:
                metric_quality -= 0.20
            metric_quality = max(0.0, min(1.0, metric_quality if merged_value is not None else 0.0))

            merged_diagnostics[key] = {
                "front": fd,
                "side": sd,
                "front_value": fv,
                "side_value": sv,
                "quality_score": round(float(metric_quality), 3),
                "divergence_guard_applied": divergence_flag,
            }
            if fv is not None and sv is not None and max(fv, sv) > 0:
                ratio = min(fv, sv) / max(fv, sv)
                merged_diagnostics[key]["front_side_ratio"] = round(float(ratio), 3)

        # Chest plausibility cap vs waist/hip after metric merge.
        chest = merged_measurements.get("chest")
        waist = merged_measurements.get("waist")
        hip = merged_measurements.get("hip")
        refs = [x for x in (waist, hip) if x is not None]
        if chest is not None and refs:
            upper_cap = max(refs) + 18.0
            if chest > upper_cap:
                merged_measurements["chest"] = round(float(upper_cap), 1)
                merged_diagnostics.setdefault("chest", {})
                merged_diagnostics["chest"]["plausibility_cap_applied"] = True
                merged_diagnostics["chest"]["plausibility_cap_cm"] = round(float(upper_cap), 1)
                merged_diagnostics["chest"]["quality_score"] = round(
                    max(0.0, float(merged_diagnostics["chest"].get("quality_score", 0.8)) - 0.15), 3
                )

        metric_scores = []
        for key in keys:
            if merged_measurements.get(key) is None:
                metric_scores.append(0.0)
            else:
                metric_scores.append(float((merged_diagnostics.get(key) or {}).get("quality_score", 0.7)))
        confidence = round(float(sum(metric_scores) / max(1, len(metric_scores))), 3)

        return {
            "measurements": merged_measurements,
            "diagnostics": merged_diagnostics,
            "confidence_score": confidence,
        }

    def _log_metric_diagnostics(
        self,
        measurements: Dict[str, Any],
        diagnostics: Dict[str, Any],
        missing: List[str],
        low_quality: List[str],
    ) -> None:
        interesting = sorted(set(missing + low_quality))
        if not interesting:
            interesting = sorted(diagnostics.keys())

        compact: Dict[str, Any] = {}
        for metric in interesting:
            d = diagnostics.get(metric, {}) or {}
            front = d.get("front", {}) or {}
            side = d.get("side", {}) or {}
            compact[metric] = {
                "value": measurements.get(metric),
                "front_value": d.get("front_value"),
                "side_value": d.get("side_value"),
                "front_quality": front.get("quality_score"),
                "side_quality": side.get("quality_score"),
                "front_reason": front.get("failure_reason"),
                "side_reason": side.get("failure_reason"),
                "front_range": front.get("range_check"),
                "side_range": side.get("range_check"),
                "front_source": front.get("source"),
                "side_source": side.get("source"),
                "front_fallback": front.get("fallback_path"),
                "side_fallback": side.get("fallback_path"),
                "front_loops": front.get("loop_count"),
                "side_loops": side.get("loop_count"),
                "front_selected_loop_cm": front.get("selected_loop_length_cm"),
                "side_selected_loop_cm": side.get("selected_loop_length_cm"),
                "front_segments_before": front.get("segments_before_filter"),
                "side_segments_before": side.get("segments_before_filter"),
                "front_segments_after": front.get("segments_after_filter"),
                "side_segments_after": side.get("segments_after_filter"),
                "front_filter_relaxed": front.get("filter_relaxed"),
                "side_filter_relaxed": side.get("filter_relaxed"),
                "front_shift_m": front.get("attempt_shift_m"),
                "side_shift_m": side.get("attempt_shift_m"),
                "front_side_ratio": d.get("front_side_ratio"),
                "divergence_guard_applied": d.get("divergence_guard_applied"),
                "merged_quality": d.get("quality_score"),
                "plausibility_cap_applied": d.get("plausibility_cap_applied"),
                "plausibility_cap_cm": d.get("plausibility_cap_cm"),
            }

        logger.warning(
            "SHAPY diagnostic details: %s",
            json.dumps(compact, ensure_ascii=False, sort_keys=True),
        )
