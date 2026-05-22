from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, Department
from app.schemas import EmployeeCreate, EmployeeResponse


router = APIRouter(prefix="/employees", tags=["Employees"])

@router.post("/", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)):
    """Нанимает нового сотрудника и привязывает его к отделу."""
    
    # Проверяем, существует ли вообще такой отдел. Нельзя нанять человека в пустоту.
    dept = db.query(Department).filter(Department.id == payload.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Указанный отдел не найден."
        )

    new_emp = Employee(
        full_name=payload.full_name,
        position=payload.position,
        department_id=payload.department_id,
        hired_at=payload.hired_at
    )
    
    db.add(new_emp)
    db.commit()
    db.refresh(new_emp)

    return new_emp


@router.get("/", response_model=list[EmployeeResponse])
def get_all_employees(db: Session = Depends(get_db)):
    """Возвращает плоский список всех сотрудников компании."""
    return db.query(Employee).all()


@router.delete("/{emp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    """Увольняет сотрудника (удаляет запись из БД)."""
    
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Сотрудник не найден."
        )
    
    db.delete(emp)
    db.commit()
    
    return None