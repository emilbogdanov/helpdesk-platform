from datetime import datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from helpdesk.api.dependencies import ContainerDep
from helpdesk.api.errors import error_responses
from helpdesk.api.schemas import Request, UserResponse
from helpdesk.domain.users.values import (
    PASSWORD_MAX_LENGTH,
    DisplayName,
    EmailAddress,
    Password,
)

router = APIRouter(prefix="/auth", tags=["auth"], responses=error_responses(401, 409, 422))


class SignUpRequest(Request):
    email: str
    display_name: str
    password: str


class TokenRequest(Request):
    email: str
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - the OAuth token type, not a secret
    expires_at: datetime


@router.post("/sign-up", status_code=status.HTTP_201_CREATED)
async def sign_up(body: SignUpRequest, container: ContainerDep) -> UserResponse:
    user = await container.auth().sign_up(
        email=EmailAddress(body.email),
        display_name=DisplayName(body.display_name),
        password=Password(body.password),
    )
    return UserResponse.from_user(user)


@router.post("/token")
async def issue_token(body: TokenRequest, container: ContainerDep) -> TokenResponse:
    access = await container.auth().log_in(EmailAddress(body.email), body.password)
    return TokenResponse(access_token=access.token, expires_at=access.expires_at)
