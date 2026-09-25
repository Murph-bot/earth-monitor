import psycopg
from fastapi import APIRouter

from app.api.deps import DbConn
from app.api.v1 import aois, scenes, sensors

router = APIRouter()
router.include_router(sensors.router)
router.include_router(aois.router)
router.include_router(scenes.router)


@router.get("/health")
def health(db: DbConn) -> dict[str, str]:
    try:
        db.execute("SELECT 1")
        db_status = "ok"
    except psycopg.Error:
        db_status = "error"
    return {"status": "ok", "db": db_status}
