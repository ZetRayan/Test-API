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


def test_get_department_not_found():
    """Тест: Попытка получить несуществующий отдел"""
    response = client.get("/departments/99999999")
    assert response.status_code == 404


# ==========================================
# --- Тесты: Удаление (DELETE) ---
# ==========================================

def test_delete_department_success():
    """Тест: успешное удаление отдела"""
    create_res = client.post("/departments/", json={"name": generate_name(), "parent_id": None})
    target_id = create_res.json()["id"]
    
    delete_res = client.delete(f"/departments/{target_id}")
    assert delete_res.status_code == 204
    
    get_res = client.get(f"/departments/{target_id}")
    assert get_res.status_code == 404

def test_delete_department_not_found():
    """Тест: удаление несуществующего отдела возвращает 404"""
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
