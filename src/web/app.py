from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Ressy Korosoft Dashboard API")
    return app
