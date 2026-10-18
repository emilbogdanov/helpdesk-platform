from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from helpdesk.api.container import Container
from helpdesk.api.errors import register_error_handlers
from helpdesk.api.routes import auth, users


def create_app(container: Container) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await container.close()

    app = FastAPI(title="Helpdesk", version="0.1.0", lifespan=lifespan)
    app.state.container = container
    register_error_handlers(app)
    for router in (auth.router, users.router):
        app.include_router(router)
    return app
