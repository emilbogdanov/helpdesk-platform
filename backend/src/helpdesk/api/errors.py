import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from helpdesk.api.schemas import ErrorResponse
from helpdesk.application.errors import (
    AdminOnlyError,
    ApplicationError,
    ConcurrentUpdateError,
    EmailTakenError,
    IdempotencyKeyConflictError,
    IdempotencyKeyReusedError,
    InvalidAssigneeError,
    InvalidCredentialsError,
    InvalidTokenError,
    OwnAccountError,
    StaffOnlyError,
    TicketNotFoundError,
    UserNotFoundError,
)
from helpdesk.domain.errors import DomainError, InvalidValueError
from helpdesk.domain.tickets.errors import (
    AssigneeRequiredError,
    InternalNoteNotAllowedError,
    InvalidStatusTransitionError,
    NotTicketRequesterError,
    TicketClosedError,
)

logger = logging.getLogger(__name__)

# The one place where business errors become HTTP responses. The code is stable and meant for
# clients to branch on; the message is for people.
ERROR_RESPONSES: dict[type[Exception], tuple[int, str]] = {
    InvalidValueError: (422, "invalid_value"),
    InvalidAssigneeError: (422, "invalid_assignee"),
    IdempotencyKeyReusedError: (422, "idempotency_key_reused"),
    InvalidCredentialsError: (401, "invalid_credentials"),
    InvalidTokenError: (401, "invalid_token"),
    StaffOnlyError: (403, "staff_only"),
    AdminOnlyError: (403, "admin_only"),
    OwnAccountError: (403, "own_account"),
    InternalNoteNotAllowedError: (403, "internal_note_not_allowed"),
    NotTicketRequesterError: (403, "not_ticket_requester"),
    TicketNotFoundError: (404, "ticket_not_found"),
    UserNotFoundError: (404, "user_not_found"),
    InvalidStatusTransitionError: (409, "invalid_status_transition"),
    AssigneeRequiredError: (409, "assignee_required"),
    TicketClosedError: (409, "ticket_closed"),
    EmailTakenError: (409, "email_taken"),
    ConcurrentUpdateError: (409, "concurrent_update"),
    IdempotencyKeyConflictError: (409, "idempotency_key_conflict"),
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI entries so generated clients know every error has the ErrorResponse shape."""
    return {status_code: {"model": ErrorResponse} for status_code in status_codes}


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _to_response)
    app.add_exception_handler(ApplicationError, _to_response)
    app.exception_handler(RequestValidationError)(_malformed_request)


# FastAPI's default 422 body has a different shape from every other error. Clients get one
# shape to handle instead, with the per-field details kept under "errors".
async def _malformed_request(_: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "request is malformed",
            "code": "invalid_request",
            "errors": jsonable_encoder(error.errors()),
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


async def _to_response(request: Request, error: Exception) -> JSONResponse:
    mapped = next(
        (ERROR_RESPONSES[cls] for cls in type(error).__mro__ if cls in ERROR_RESPONSES), None
    )
    if mapped is None:
        logger.error("unmapped %s on %s %s", type(error).__name__, request.method, request.url.path)
        return JSONResponse({"detail": "internal error", "code": "internal"}, status_code=500)
    status_code, code = mapped
    return JSONResponse(
        {"detail": str(error), "code": code},
        status_code=status_code,
        headers={"WWW-Authenticate": "Bearer"}
        if status_code == status.HTTP_401_UNAUTHORIZED
        else None,
    )
