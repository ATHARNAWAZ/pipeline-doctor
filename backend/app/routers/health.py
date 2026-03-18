from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check() -> JSONResponse:
    return JSONResponse(content={"status": "ok", "version": "0.1.0"})
