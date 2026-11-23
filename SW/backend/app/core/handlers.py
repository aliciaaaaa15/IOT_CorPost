from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.core.response_codes import ResponseCode


def error(status_code: int, code: str, message: str):
    """Error envelope {"error": {"code", "message"}}. Successful responses return the Pydantic model directly."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def app_exception_handler(request: Request, exc: AppException):
    """Our own exceptions (raised by services/routers)."""
    return error(exc.status_code, exc.code, exc.message)


def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Any HTTP error raised by FastAPI/Starlette itself (404, 405, 403...). The code is the status name."""
    return error(exc.status_code, HTTPStatus(exc.status_code).name, str(exc.detail))


def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Body/query that does not match the Pydantic schema (FastAPI default is 422 with its own format)."""
    first = exc.errors()[0]
    if first["type"] == "json_invalid":
        # loc is ("body", <character position>): the position is not a field name
        field = ""
    else:
        field = ".".join(str(p) for p in first["loc"] if p not in ("body", "query"))
    message = f"{field}: {first['msg']}" if field else first["msg"]
    return error(status.HTTP_422_UNPROCESSABLE_CONTENT, ResponseCode.VALIDATION_ERROR, message)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
