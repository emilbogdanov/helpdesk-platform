from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from helpdesk.api.container import Container
from helpdesk.application.actor import Actor
from helpdesk.application.errors import InvalidTokenError

_bearer = HTTPBearer(auto_error=False, description="Access token from POST /auth/token")


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_current_actor(
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Actor:
    # auto_error is off so a missing token goes through the same 401 path as a bad one.
    if credentials is None:
        raise InvalidTokenError("missing access token")
    return await container.auth().authenticate(credentials.credentials)


CurrentActor = Annotated[Actor, Depends(get_current_actor)]
