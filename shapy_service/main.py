import logging
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic_settings import BaseSettings

from measurement_mapper import map_shapy_output
from shapy_wrapper import ShapyWrapper


class Settings(BaseSettings):
    SHAPY_DATA_DIR: str = "../backend/data"
    SHAPY_CHECKPOINT: str = (
        "../backend/data/trained_models/shapy/SHAPY_A/checkpoints/best_checkpoint"
    )
    SHAPY_API_KEY: Optional[str] = None
    SHAPY_LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

logging.basicConfig(level=getattr(logging, settings.SHAPY_LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)

wrapper = ShapyWrapper(
    data_dir=settings.SHAPY_DATA_DIR,
    checkpoint_path=settings.SHAPY_CHECKPOINT,
)
wrapper.initialize()

app = FastAPI(title="SHAPY Service", version="1.0.0")


def _authorize(authorization: Optional[str]) -> None:
    if not settings.SHAPY_API_KEY:
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    expected = f"Bearer {settings.SHAPY_API_KEY}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid Authorization token")


@app.get("/health")
async def health(authorization: Optional[str] = Header(default=None)) -> dict:
    _authorize(authorization)
    return {
        "ok": wrapper.ready,
        "service": "shapy",
        "error": wrapper.init_error if not wrapper.ready else None,
    }


@app.post("/measure")
async def measure(
    front_image: UploadFile = File(...),
    side_image: UploadFile = File(...),
    height_cm: float = Form(...),
    weight_kg: float = Form(...),
    gender: str = Form(...),
    authorization: Optional[str] = Header(default=None),
) -> dict:
    _authorize(authorization)

    if gender not in {"male", "female", "unisex"}:
        raise HTTPException(status_code=400, detail="gender must be male/female/unisex")
    if height_cm < 100 or height_cm > 250:
        raise HTTPException(status_code=400, detail="height_cm must be 100-250")
    if weight_kg < 30 or weight_kg > 300:
        raise HTTPException(status_code=400, detail="weight_kg must be 30-300")

    if not wrapper.ready:
        raise HTTPException(status_code=503, detail=f"SHAPY model not ready: {wrapper.init_error}")

    front_data = await front_image.read()
    side_data = await side_image.read()

    try:
        raw_output = wrapper.measure(
            front_image=front_data,
            side_image=side_data,
            height_cm=height_cm,
            weight_kg=weight_kg,
            gender=gender,
        )
        return map_shapy_output(raw_output)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SHAPY measure failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
