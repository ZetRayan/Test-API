"""
Тестовое покрытие API Организационной структуры.
Используется изолированная база данных SQLite in-memory.

Оглавление тестов:

[ Подразделения: POST /departments/ ]
* test_create_department_success — Успешное создание корневого отдела.
* test_create_department_duplicate — Защита от дубликатов имен на одном уровне.
* test_create_department_validation_error — Валидация Pydantic (пустые имена).

[ Подразделения: GET /departments/ ]
* test_get_all_departments — Получение плоского списка.
* test_get_department_success — Получение конкретного отдела.
* test_get_department_with_employees — Проверка вывода сотрудников и сортировки.
* test_get_department_depth_limit — Проверка ограничения рекурсии (depth).
* test_get_department_defaults — Проверка дефолтных параметров ТЗ.
* test_get_department_max_depth_error — Защита от превышения глубины (depth > 5).
* test_get_department_not_found — Ошибка 404.

[ Подразделения: DELETE /departments/ ]
* test_delete_department_cascade — Успешное каскадное удаление.
* test_delete_department_reassign_success — Успешное удаление с эвакуацией сотрудников.
* test_delete_department_reassign_missing_target — Ошибка при отсутствии запасного отдела.
* test_delete_department_reassign_protection — Защита от каскадного уничтожения при эвакуации.
* test_delete_department_not_found — Ошибка 404.

[ Подразделения: PATCH /departments/ ]
* test_update_department_name_success — Успешное переименование.
* test_update_department_move_success — Успешное перемещение к новому родителю.
* test_update_department_name_conflict — Защита от одинаковых имен при переименовании.
* test_update_department_self_parent — Защита от назначения самого себя родителем.
* test_update_department_cycle_protection — Защита от циклических зависимостей (Уроборос).

[ Сотрудники: Employees ]
* test_create_employee_success — Успешный найм.
* test_create_employee_invalid_department — Найм в несуществующий отдел.
* test_get_all_employees — Получение списка всех сотрудников.
* test_delete_employee_success — Увольнение сотрудника.
"""


import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, Base

# ==========================================
# --- Изолированная тестовая БД (SQLite in-memory) ---
# ==========================================
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=pool.StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ==========================================
# --- Перехват зависимостей (Dependency Override) ---
# ==========================================
def override_get_db():
    """Подменяет реальную базу (Postgres) на тестовую (SQLite)"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
# ==========================================
# --- Вспомогательные функции ---
# ==========================================
def generate_name():
    """Генерирует уникальное имя (оставляем для надежности)"""
    return f"Test_Dept_{uuid.uuid4().hex[:6]}"

# ==========================================
# --- Настройка тестового клиента и фикстур ---
# ==========================================
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    """
    Эта фикстура автоматически срабатывает перед КАЖДЫМ тестом.
    Она создает чистые таблицы, а после завершения теста — сносит их.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    

# ==========================================
# --- Тесты для эндпоинта POST /departments/ ---
# ==========================================

def test_create_department_success():
    """Тест: успешное создание корневого отдела"""
    name = generate_name()
    payload = {
        "name": name,
        "parent_id": None
    }
    response = client.post("/departments/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == name
    assert "id" in data
    assert data["parent_id"] is None


def test_create_department_duplicate():
    """Тест: проверка защиты от дубликатов (бизнес-логика)"""
    name = generate_name()
    payload = {
        "name": name,
        "parent_id": None
    }
    client.post("/departments/", json=payload)
    response = client.post("/departments/", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Подразделение с таким именем уже существует на этом уровне."


def test_create_department_validation_error():
    """Тест: проверка валидации Pydantic для поля name"""
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
    """Тест: Получение плоского списка всех отделов"""
    client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    response = client.get("/departments/")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_department_success():
    """Тест: Получение конкретного отдела (базовое)"""
    create_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    dept_id = create_res.json()["id"]
    
    response = client.get(f"/departments/{dept_id}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == dept_id
    assert "children" in data
    assert isinstance(data["children"], list)


def test_get_department_with_employees():
    """Тест: Проверка параметра include_employees=True и сортировки"""
    dept_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    dept_id = dept_res.json()["id"]
    
    client.post(f"/departments/{dept_id}/employees/", json={
        "full_name": "Яблоков Яков", "position": "Тестировщик"
    })
    client.post(f"/departments/{dept_id}/employees/", json={
        "full_name": "Абрикосов Антон", "position": "Разработчик"
    })
    
    response = client.get(f"/departments/{dept_id}?include_employees=true")
    assert response.status_code == 200
    data = response.json()
    
    assert "employees" in data
    assert len(data["employees"]) == 2
    assert data["employees"][0]["full_name"] == "Абрикосов Антон"
    assert data["employees"][1]["full_name"] == "Яблоков Яков"


def test_get_department_depth_limit():
    """Тест: Проверка ограничения рекурсии (depth)"""
    grandpa = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()
    father = client.post("/departments/", json={"name": generate_name(), "parent_id": grandpa["id"]}).json()
    son = client.post("/departments/", json={"name": generate_name(), "parent_id": father["id"]}).json()

    response = client.get(f"/departments/{grandpa['id']}?depth=2")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["children"]) == 1
    assert data["children"][0]["id"] == father["id"]
    assert len(data["children"][0]["children"]) == 0


def test_get_department_defaults():
    """Тест: Проверка строгого соответствия ТЗ (depth=1, include_employees=true по умолчанию)"""
    parent_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    client.post("/departments/", json={"name": generate_name(), "parent_id": parent_id})
    
    client.post(f"/departments/{parent_id}/employees/", json={
        "full_name": "Неизвестный Солдат", "position": "Снайпер"
    })
    
    response = client.get(f"/departments/{parent_id}")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["employees"]) == 1
    assert len(data["children"]) == 0


def test_get_department_max_depth_error():
    """Тест: Защита от превышения лимита глубины (depth > 5)"""
    dept_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    
    response = client.get(f"/departments/{dept_id}?depth=6")

    assert response.status_code == 422


def test_get_department_not_found():
    """Тест: Попытка получить несуществующий отдел"""
    response = client.get("/departments/99999999")
    assert response.status_code == 404


# ==========================================
# --- Тесты: Удаление (DELETE) ---
# ==========================================

def test_delete_department_cascade():
    """Тест: Успешное удаление отдела (режим cascade)"""
    create_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    target_id = create_res.json()["id"]
    
    delete_res = client.delete(f"/departments/{target_id}?mode=cascade")
    assert delete_res.status_code == 204
    
    get_res = client.get(f"/departments/{target_id}")
    assert get_res.status_code == 404


def test_delete_department_reassign_success():
    """Тест: Успешный перевод сотрудников в независимый отдел перед удалением."""
    doomed_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    safe_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    
    client.post(f"/departments/{doomed_id}/employees/", json={
        "full_name": "Выживший Тестер", "position": "QA"
    })
    
    response = client.delete(f"/departments/{doomed_id}?mode=reassign&reassign_to_department_id={safe_id}")
    assert response.status_code == 204
    assert client.get(f"/departments/{doomed_id}").status_code == 404
    
    safe_dept_res = client.get(f"/departments/{safe_id}?include_employees=true")
    data = safe_dept_res.json()
    assert len(data["employees"]) == 1
    assert data["employees"][0]["full_name"] == "Выживший Тестер"
    assert data["employees"][0]["department_id"] == safe_id


def test_delete_department_reassign_missing_target():
    """Тест: Ошибка при reassign, если не передан ID запасного отдела"""
    doomed_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    response = client.delete(f"/departments/{doomed_id}?mode=reassign")
    assert response.status_code == 400


def test_delete_department_reassign_protection():
    """Тест: Защита от перевода сотрудников в дочерний отдел удаляемого."""
    res_parent = client.post("/departments/", json={"name": generate_name()})
    parent_id = res_parent.json()["id"]

    res_child = client.post("/departments/", json={"name": generate_name(), "parent_id": parent_id})
    child_id = res_child.json()["id"]

    res_delete = client.delete(f"/departments/{parent_id}?mode=reassign&reassign_to_department_id={child_id}")
    
    assert res_delete.status_code == 400
    assert "Нельзя перевести сотрудников во вложенный отдел" in res_delete.json()["detail"]


def test_delete_department_not_found():
    """Тест: Попытка удалить несуществующий отдел"""
    response = client.delete("/departments/99999999")
    assert response.status_code == 404

# ==========================================
# --- Тесты: Сотрудники (Employees) ---
# ==========================================

def test_create_employee_success():
    """Тест: POST /departments/{dept_id}/employees/ — успешный найм сотрудника в существующий отдел"""
    dept_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    dept_id = dept_res.json()["id"]

    payload = {
        "full_name": "Иван Иванов",
        "position": "Разработчик",
        "hired_at": "2026-05-22"
    }
    response = client.post(f"/departments/{dept_id}/employees/", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Иван Иванов"
    assert data["position"] == "Разработчик"
    assert data["department_id"] == dept_id
    assert "id" in data


def test_create_employee_invalid_department():
    """Тест: POST /departments/{dept_id}/employees/ — 404 при найме в несуществующий отдел"""
    payload = {
        "full_name": "Петр Петров",
        "position": "Тестировщик",
        "hired_at": "2026-05-22"
    }
    response = client.post("/departments/99999999/employees/", json=payload)

    assert response.status_code == 404


def test_get_all_employees():
    """Тест: GET /employees/ — получение списка сотрудников"""
    dept_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    dept_id = dept_res.json()["id"]

    client.post(
        f"/departments/{dept_id}/employees/",
        json={
            "full_name": "Анна Смирнова",
            "position": "Аналитик",
        }
    )

    response = client.get("/employees/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_delete_employee_success():
    """Тест: DELETE /employees/{emp_id} — 204 при увольнении и 404 при повторном удалении"""
    dept_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    dept_id = dept_res.json()["id"]

    emp_res = client.post(
        f"/departments/{dept_id}/employees/",
        json={
            "full_name": "Кандидат на вылет",
            "position": "Стажер",
        }
    )
    emp_id = emp_res.json()["id"]

    delete_res = client.delete(f"/employees/{emp_id}")
    assert delete_res.status_code == 204

    delete_again = client.delete(f"/employees/{emp_id}")
    assert delete_again.status_code == 404


# ==========================================
# --- Тесты: Обновление (PATCH) ---
# ==========================================

def test_update_department_name_success():
    """Тест: Успешное переименование отдела"""
    create_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    dept_id = create_res.json()["id"]
    
    new_name = generate_name()
    response = client.patch(f"/departments/{dept_id}", json={"name": new_name})
    
    assert response.status_code == 200
    assert response.json()["name"] == new_name


def test_update_department_move_success():
    """Тест: Успешное перемещение отдела к новому родителю"""
    parent_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    parent_id = parent_res.json()["id"]
    
    child_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    child_id = child_res.json()["id"]
    
    response = client.patch(f"/departments/{child_id}", json={"parent_id": parent_id})
    
    assert response.status_code == 200
    assert response.json()["parent_id"] == parent_id


def test_update_department_name_conflict():
    """Тест: Защита от одинаковых имен на одном уровне"""
    parent_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    
    name1 = generate_name()
    client.post("/departments/", json={"name": name1, "parent_id": parent_id})
    child2_id = client.post("/departments/", json={"name": generate_name(), "parent_id": parent_id}).json()["id"]
    
    response = client.patch(f"/departments/{child2_id}", json={"name": name1})
    
    assert response.status_code == 400


def test_update_department_self_parent():
    """Тест: Защита от назначения самого себя родителем"""
    dept_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    
    response = client.patch(f"/departments/{dept_id}", json={"parent_id": dept_id})
    assert response.status_code == 400


def test_update_department_cycle_protection():
    """Тест: Защита от циклических зависимостей (Уроборос)"""
    grandpa_id = client.post("/departments/", json={"name": generate_name(), "parent_id": None}).json()["id"]
    father_id = client.post("/departments/", json={"name": generate_name(), "parent_id": grandpa_id}).json()["id"]
    son_id = client.post("/departments/", json={"name": generate_name(), "parent_id": father_id}).json()["id"]
    
    response = client.patch(f"/departments/{grandpa_id}", json={"parent_id": son_id})
    
    assert response.status_code == 400
    assert "циклическая зависимость" in response.json()["detail"].lower()


