from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Department
from app.schemas import DepartmentCreate, DepartmentResponse


router = APIRouter(prefix="/departments", tags=["Departments"])

@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    """
    Создает новое подразделение.
    Проверяет, чтобы в пределах одного родителя названия были уникальны.
    """

    existing_dept = db.query(Department).filter(
        Department.name == payload.name,
        Department.parent_id == payload.parent_id
    ).first()

    if existing_dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Подразделение с таким именем уже существует на этом уровне."
        )

    # Проверка, существует ли parent_id, если он передан
    if payload.parent_id is not None:
        parent_dept = db.query(Department).filter(Department.id == payload.parent_id).first()
        if not parent_dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Родительское подразделение не найдено."
            )

    # Собираем модель БД и сохраняем
    new_dept = Department(
        name=payload.name,
        parent_id=payload.parent_id
    )
    
    db.add(new_dept)
    db.commit()
    db.refresh(new_dept)

    return new_dept
