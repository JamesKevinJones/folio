import uvicorn

from folio.api.app import app, mount_companion
from folio.config import get_settings


def run() -> None:
    mount_companion(app)
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
