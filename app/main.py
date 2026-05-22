from fastapi import FastAPI
from app.routers import departments


app = FastAPI(
    title="Организационная структура API",
    description="Тестовое задание",
    version="1.0.0"
)

app.include_router(departments.router)
