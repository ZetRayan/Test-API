import uuid
from fastapi.testclient import TestClient

from app.main import app

# ==========================================
# --- Настройка тестового клиента ---
# ==========================================

# TestClient берет наше FastAPI приложение и позволяет слать к нему HTTP-запросы напрямую.
client = TestClient(app)

# Генерируем уникальное имя для каждого запуска тестов. 
# Мы стучимся в нашу основную БД, и чтобы тесты не падали из-за того, 
# что отдел "Test" уже был создан вчерашним запуском, делаем имя случайным.
UNIQUE_DEPT_NAME = f"Test_Dept_{uuid.uuid4().hex[:6]}"


# ==========================================
# --- Тесты для эндпоинта POST /departments/ ---
# ==========================================


def test_create_department_success():
    """Тест 1: Успешное создание корневого отдела"""
    payload = {
        "name": UNIQUE_DEPT_NAME,
        "parent_id": None
    }
    response = client.post("/departments/", json=payload)
    
    # Проверяем статус-код (201 Created)
    assert response.status_code == 201
    
    # Проверяем, что в ответе вернулись правильные данные и база присвоила ID
    data = response.json()
    assert data["name"] == UNIQUE_DEPT_NAME
    assert "id" in data
    assert data["parent_id"] is None


def test_create_department_duplicate():
    """Тест 2: Проверка защиты от дубликатов (бизнес-логика)"""
    # Пытаемся создать отдел с тем же сгенерированным именем и тем же родителем
    payload = {
        "name": UNIQUE_DEPT_NAME,
        "parent_id": None
    }
    response = client.post("/departments/", json=payload)
    
    # Наш код в router должен отбить это со статусом 400
    assert response.status_code == 400
    assert response.json()["detail"] == "Подразделение с таким именем уже существует на этом уровне."


def test_create_department_validation_error():
    """Тест 3: Проверка фейс-контроля Pydantic"""
    # Отправляем имя из одних пробелов (наш кастомный валидатор должен это пресечь)
    payload = {
        "name": "   ",
        "parent_id": None
    }
    response = client.post("/departments/", json=payload)
    
    # Pydantic должен вернуть 422 Unprocessable Entity
    assert response.status_code == 422
    
    # Проверяем, что ошибка прилетела именно из-за поля 'name'
    errors = response.json()["detail"]
    assert errors[0]["loc"] == ["body", "name"]
    assert "Название подразделения не может состоять только из пробелов" in errors[0]["msg"]

