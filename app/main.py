from fastapi import FastAPI
from app.routers import departments, employees


app = FastAPI(
    title="Организационная структура API",
    description="Тестовое задание",
    version="1.0.0"
)

app.include_router(departments.router)
app.include_router(employees.router)
