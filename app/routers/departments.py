from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Literal,Optional

from app.database import get_db
from app.models import Department, Employee
from app.schemas import DepartmentCreate, DepartmentResponse, DepartmentTreeResponse, EmployeeCreate, EmployeeResponse, DepartmentUpdate


router = APIRouter(prefix="/departments", tags=["Departments"])

@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    """Создает новое подразделение."""
    existing_dept = db.query(Department).filter(
        Department.name == payload.name,
        Department.parent_id == payload.parent_id
    ).first()

    if existing_dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Подразделение с таким именем уже существует на этом уровне."
        )

    if payload.parent_id is not None:
        parent_dept = db.query(Department).filter(Department.id == payload.parent_id).first()
        if not parent_dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Родительское подразделение не найдено."
            )

    new_dept = Department(name=payload.name, parent_id=payload.parent_id)
    db.add(new_dept)
    db.commit()
    db.refresh(new_dept)

    return new_dept


@router.post("/{dept_id}/employees/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee_in_department(dept_id: int, payload: EmployeeCreate, db: Session = Depends(get_db)):
    """Нанимает нового сотрудника в указанный отдел."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Указанный отдел не найден."
        )

    new_emp = Employee(
        full_name=payload.full_name,
        position=payload.position,
        department_id=dept_id,
        hired_at=payload.hired_at
    )
    db.add(new_emp)
    db.commit()
    db.refresh(new_emp)
    return new_emp


@router.get("/", response_model=list[DepartmentResponse])
def get_all_departments(db: Session = Depends(get_db)):
    """Возвращает плоский список всех подразделений."""
    return db.query(Department).all()


@router.get("/{dept_id}", response_model=DepartmentTreeResponse)
def get_department(
    dept_id: int, 
    depth: int = Query(5, ge=1, description="Глубина вложенности дерева"), 
    include_employees: bool = Query(False, description="Включать ли списки сотрудников"),
    db: Session = Depends(get_db)
):
    """
    Возвращает информацию о конкретном отделе.
    Умеет рекурсивно собирать подотделы до указанной глубины и подтягивать сотрудников.
    """
    
    def build_tree(current_id: int, current_depth: int) -> Optional[dict]:
        dept = db.query(Department).filter(Department.id == current_id).first()
        if not dept:
            return None
        
        dept_data = {
            "id": dept.id,
            "name": dept.name,
            "parent_id": dept.parent_id,
            "created_at": dept.created_at,
            "children": [],
            "employees": []
        }

        if include_employees:
            employees = db.query(Employee).filter(Employee.department_id == current_id).order_by(Employee.full_name).all()
            dept_data["employees"] = employees

        if current_depth < depth:
            children = db.query(Department).filter(Department.parent_id == current_id).all()
            for child in children:
                child_node = build_tree(child.id, current_depth + 1)  # type: ignore
                if child_node:
                    dept_data["children"].append(child_node)

        return dept_data

    tree = build_tree(dept_id, 1)
    
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подразделение не найдено."
        )
        
    return tree


@router.patch("/{dept_id}", response_model=DepartmentResponse)
def update_department(dept_id: int, payload: DepartmentUpdate, db: Session = Depends(get_db)):
    """
    Обновляет данные отдела (переименование и/или перемещение).
    Содержит защиту от образования циклических зависимостей в дереве.
    """
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подразделение не найдено."
        )

    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        return dept

    # 1. Если меняют название, проверяем, нет ли уже такого имени на уровне текущего родителя
    # (или на уровне нового родителя, если parent_id тоже меняется)
    if "name" in update_data:
        new_name = update_data["name"]
        check_parent_id = update_data.get("parent_id", dept.parent_id)
        
        existing_dept = db.query(Department).filter(
            Department.name == new_name,
            Department.parent_id == check_parent_id,
            Department.id != dept_id
        ).first()
        
        if existing_dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Подразделение с таким именем уже существует на этом уровне."
            )

    # 2. Если меняют родителя, запускаем проверку на циклы
    if "parent_id" in update_data:
        new_parent_id = update_data["parent_id"]

        if new_parent_id == dept_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Отдел не может быть родителем самому себе."
            )

        if new_parent_id is not None:
            # Проверяем, существует ли вообще новый родитель
            new_parent_dept = db.query(Department).filter(Department.id == new_parent_id).first()
            if not new_parent_dept:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Указанный новый родительский отдел не найден."
                )

            # Алгоритм обхода вверх: идем от нового родителя к корню
            current_check_id = new_parent_id
            while current_check_id is not None:
                if current_check_id == dept_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Нельзя переместить отдел внутрь его собственного подотдела (циклическая зависимость)."
                    )
                # Делаем запрос к БД, чтобы найти родителя текущего проверяемого узла
                parent_node = db.query(Department.parent_id).filter(Department.id == current_check_id).first()
                if not parent_node:
                    break # Такого быть не должно из-за FK, но перестраховка не помешает
                
                current_check_id = parent_node.parent_id

    # 3. Применяем изменения, если проверки пройдены
    for key, value in update_data.items():
        setattr(dept, key, value)

    db.commit()
    db.refresh(dept)
    
    return dept

@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: int, 
    mode: Literal["cascade", "reassign"] = Query("cascade", description="Режим удаления: cascade или reassign"),
    reassign_to_department_id: Optional[int] = Query(None, description="ID отдела для перевода сотрудников (только для mode=reassign)"),
    db: Session = Depends(get_db)
):
    """
    Удаляет отдел.
    Режимы (mode):
    - cascade: удаляет отдел и все вложенные отделы с их сотрудниками (поведение БД по умолчанию).
    - reassign: переводит сотрудников удаляемого отдела в reassign_to_department_id перед удалением.
    """
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подразделение не найдено."
        )

    if mode == "reassign":
        if reassign_to_department_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для режима reassign необходимо указать параметр reassign_to_department_id."
            )
        
        if reassign_to_department_id == dept_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя перевести сотрудников в удаляемый отдел."
            )
            
        target_dept = db.query(Department).filter(Department.id == reassign_to_department_id).first()
        if not target_dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запасной отдел (reassign_to_department_id) не найден."
            )
            
        # Массово переводим сотрудников удаляемого отдела в новый отдел
        db.query(Employee).filter(Employee.department_id == dept_id).update({"department_id": reassign_to_department_id})

    db.delete(dept)
    db.commit()
    return None