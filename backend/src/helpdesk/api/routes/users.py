from uuid import UUID

from fastapi import APIRouter, status

from helpdesk.api.dependencies import ContainerDep, CurrentActor
from helpdesk.api.errors import error_responses
from helpdesk.api.schemas import Request, UserResponse
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


@router.get("/me")
async def get_profile(actor: CurrentActor, container: ContainerDep) -> UserResponse:
    return UserResponse.from_user(await container.users().get_profile(actor))


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
