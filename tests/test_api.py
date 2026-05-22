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

def generate_name():
    """Генерирует уникальное имя, чтобы тесты не конфликтовали в базе"""
    return f"Test_Dept_{uuid.uuid4().hex[:6]}"

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


# ==========================================
# --- Тесты: Чтение (GET) ---
# ==========================================


def test_get_all_departments():
    """Тест 4: Получение всех отделов (проверяем, что ответ - это список и что он не пустой)"""
    client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    response = client.get("/departments/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_get_department_success():
    """Тест 5: Получение конкретного отдела (с проверкой наличия массива children)"""
    create_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    dept_id = create_res.json()["id"]
    response = client.get(f"/departments/{dept_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == dept_id
    assert "children" in data
    assert isinstance(data["children"], list)

def test_get_department_not_found():
    """Тест 6: Попытка получить несуществующий отдел"""
    response = client.get("/departments/99999999")
    assert response.status_code == 404


# ==========================================
# --- Тесты: Удаление (DELETE) ---
# ==========================================

def test_delete_department_success():
    """Тест 7: Успешное удаление отдела и проверка, что он действительно удален"""
    # Создаем жертву
    create_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    target_id = create_res.json()["id"]
    
    # Убиваем жертву
    delete_res = client.delete(f"/departments/{target_id}")
    assert delete_res.status_code == 204
    
    # Проверяем, что отдел действительно удален, пытаясь его получить
    get_res = client.get(f"/departments/{target_id}")
    assert get_res.status_code == 404

def test_delete_department_not_found():
    """Тест 8: Попытка удалить то, чего нет"""
    response = client.delete("/departments/99999999")
    assert response.status_code == 404