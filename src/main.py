import uvicorn

from src.core.config import settings
# from src.server import app

if __name__ == "__main__":
    uvicorn.run(
        app="src.server:app",
        reload=settings.ENV != "prod",
        workers=1,
        host="0.0.0.0",
        port=5000,
    )
