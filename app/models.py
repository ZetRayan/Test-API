from datetime import datetime
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

# ==========================================
# --- Таблица: Подразделения (Departments) ---
# ==========================================
class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Связи (Relationships) ---
    employees = relationship("Employee", back_populates="department", cascade="all, delete-orphan")
    children = relationship("Department", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("Department", back_populates="children", remote_side=[id])


# ==========================================
# --- Таблица: Сотрудники (Employees) ---
# ==========================================
class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    
    full_name = Column(String(200), nullable=False)
    position = Column(String(200), nullable=False)
    hired_at = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Связи (Relationships) ---
    department = relationship("Department", back_populates="employees")