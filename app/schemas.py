from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==========================================
# --- DEPARTMENTS ---
# ==========================================

class DepartmentCreate(BaseModel):
    """Схема для валидации входящего JSON при создании отдела"""
    name: str = Field(min_length=1, max_length=200)
    parent_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Название подразделения не может состоять только из пробелов")
        return stripped


class DepartmentResponse(BaseModel):
    """Схема для отдачи базовой информации об отделе"""
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentTreeResponse(DepartmentResponse):
    """Схема для отдачи отдела вместе с его подотделами и сотрудниками (Рекурсия)"""
    children: list['DepartmentTreeResponse'] = []
    employees: Optional[list['EmployeeResponse']] = []
    
    
class DepartmentUpdate(BaseModel):
    """Схема для валидации входящего JSON при обновлении отдела (PATCH)"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    parent_id: Optional[int] = Field(None, description="ID нового родительского отдела. Передайте null, чтобы сделать отдел корневым.")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            stripped = value.strip()
            if not stripped:
                raise ValueError("Название подразделения не может состоять только из пробелов")
            return stripped
        return value

# ==========================================
# --- EMPLOYEES ---
# ==========================================

class EmployeeCreate(BaseModel):
    """Схема для валидации входящего JSON при найме сотрудника"""
    full_name: str = Field(min_length=1, max_length=200)
    position: str = Field(min_length=1, max_length=200)
    hired_at: Optional[date] = None

    @field_validator("full_name", "position")
    @classmethod
    def validate_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Текстовое поле не может состоять только из пробелов")
        return stripped


class EmployeeResponse(BaseModel):
    """Схема для отдачи данных о сотруднике"""
    id: int
    full_name: str
    position: str
    department_id: int
    hired_at: Optional[date]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)