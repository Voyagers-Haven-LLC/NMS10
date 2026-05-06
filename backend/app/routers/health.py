from fastapi import APIRouter

from .. import config

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/_meta")
def meta() -> dict:
    return {
        "db_path": str(config.DB_PATH),
        "admin_password_is_default": config.ADMIN_PASSWORD_IS_DEFAULT,
        "jwt_secret_is_default": config.JWT_SECRET_IS_DEFAULT,
    }
