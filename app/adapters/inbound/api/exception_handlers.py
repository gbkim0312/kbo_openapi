from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainError


def error_body(code: str, message: str, request: Request, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "requestId": getattr(request.state, "request_id", str(uuid4())),
        }
    }


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(error_body(exc.code, exc.message, request), status_code=exc.status_code)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        error_body(
            "INVALID_REQUEST", "요청 형식이 올바르지 않습니다.", request, {"errors": exc.errors()}
        ),
        status_code=422,
    )
