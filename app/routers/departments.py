from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Department, Employee
from app.schemas import DepartmentCreate, DepartmentResponse, DepartmentTreeResponse, EmployeeCreate, EmployeeResponse


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


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(dept_id: int, db: Session = Depends(get_db)):
    """Удаляет отдел."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подразделение не найдено."
        )
    
    db.delete(dept)
    db.commit()
    return None