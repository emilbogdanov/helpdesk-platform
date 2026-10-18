from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field

from helpdesk.api.cursors import decode_user_cursor, encode_user_cursor
from helpdesk.api.dependencies import ContainerDep, CurrentActor
from helpdesk.api.errors import error_responses
from helpdesk.api.schemas import PersonResponse, Request, UserResponse
from helpdesk.application.users.queries import MAX_PAGE_SIZE, UserQuery
from helpdesk.domain.ids import UserId
from helpdesk.domain.roles import Role
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password

router = APIRouter(
    prefix="/users", tags=["users"], responses=error_responses(401, 403, 404, 409, 422)
)


class CreateUserRequest(Request):
    email: str
    display_name: str
    role: Role
    password: str


class RoleChangeRequest(Request):
    role: Role


class UserListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role | None = None
    status: Literal["active", "deactivated"] | None = None
    q: str | None = Field(None, max_length=100, description="Part of a name or email address")
    limit: int = Field(50, ge=1, le=MAX_PAGE_SIZE)
    cursor: str | None = Field(None, description="`next_cursor` from the previous page")

    def to_query(self) -> UserQuery:
        return UserQuery(
            role=self.role,
            active=None if self.status is None else self.status == "active",
            search=self.q,
            after=decode_user_cursor(self.cursor) if self.cursor else None,
            limit=self.limit,
        )


class UserListResponse(BaseModel):
    items: list[UserResponse]
    # Pass back as `cursor` for the next page; null on the last page.
    next_cursor: str | None


@router.get("/me")
async def get_profile(actor: CurrentActor, container: ContainerDep) -> UserResponse:
    return UserResponse.from_user(await container.users().get_profile(actor))


@router.get("")
async def list_users(
    params: Annotated[UserListParams, Query()], actor: CurrentActor, container: ContainerDep
) -> UserListResponse:
    page = await container.users().list_users(actor, params.to_query())
    return UserListResponse(
        items=[UserResponse.from_user(user) for user in page.users],
        next_cursor=encode_user_cursor(page.next_cursor) if page.next_cursor else None,
    )


# Declared before /{user_id} so "staff" isn't read as an id.
@router.get("/staff")
async def list_staff(actor: CurrentActor, container: ContainerDep) -> list[PersonResponse]:
    return [PersonResponse.from_user(user) for user in await container.people().staff(actor)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest, actor: CurrentActor, container: ContainerDep
) -> UserResponse:
    user = await container.users().create_user(
        actor,
        email=EmailAddress(body.email),
        display_name=DisplayName(body.display_name),
        role=body.role,
        password=Password(body.password),
    )
    return UserResponse.from_user(user)


@router.get("/{user_id}")
async def get_user(user_id: UUID, actor: CurrentActor, container: ContainerDep) -> UserResponse:
    return UserResponse.from_user(await container.users().get_user(actor, UserId(user_id)))


@router.put("/{user_id}/role")
async def change_role(
    user_id: UUID, body: RoleChangeRequest, actor: CurrentActor, container: ContainerDep
) -> UserResponse:
    user = await container.users().change_role(actor, UserId(user_id), body.role)
    return UserResponse.from_user(user)


@router.post("/{user_id}/deactivate")
async def deactivate(user_id: UUID, actor: CurrentActor, container: ContainerDep) -> UserResponse:
    return UserResponse.from_user(await container.users().deactivate(actor, UserId(user_id)))


@router.post("/{user_id}/reactivate")
async def reactivate(user_id: UUID, actor: CurrentActor, container: ContainerDep) -> UserResponse:
    return UserResponse.from_user(await container.users().reactivate(actor, UserId(user_id)))
