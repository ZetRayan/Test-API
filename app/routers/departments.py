from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Department
from app.schemas import DepartmentCreate, DepartmentResponse, DepartmentTreeResponse


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


@router.get("/", response_model=list[DepartmentResponse])
def get_all_departments(db: Session = Depends(get_db)):
    """Возвращает плоский список всех подразделений."""
    return db.query(Department).all()


@router.get("/{dept_id}", response_model=DepartmentTreeResponse)
def get_department(dept_id: int, db: Session = Depends(get_db)):
    """Возвращает информацию о конкретном отделе и всех его подотделах."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подразделение не найдено."
        )
    return dept


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(dept_id: int, db: Session = Depends(get_db)):
    """
    Удаляет отдел.
    Благодаря каскаду в БД (ondelete='CASCADE'), все вложенные отделы удалятся автоматически.
    """
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подразделение не найдено."
        )
    
    db.delete(dept)
    db.commit()
    return None