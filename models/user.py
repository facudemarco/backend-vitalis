from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, UUID, Boolean
from sqlalchemy.ext.declarative import declarative_base
from fastapi import Form
from sqlalchemy.dialects.mysql import CHAR
Base = declarative_base()

class Patients(Base):
    __tablename__ = "patients"
    id = Column(CHAR(36), primary_key=True, index=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    dni = Column(Integer)
    date_of_birth = Column(String(50))
    phone = Column(String(50))
    address = Column(String(50))
    social_security = Column(String(50))
    company_id = Column(CHAR(36))
    user_id = Column(CHAR(36))
    
    class Config:
        from_attributes = True
    

class professionals(Base):
    __tablename__ = "professionals"
    id = Column(CHAR(36), primary_key=True, index=True)
    user_id = Column(CHAR(36))
    license_number = Column(String(50))
    speciality = Column(String(50))
    phone = Column(String(50))
    
    class Config:
        from_attributes = True
        
class companies(Base):
    __tablename__ = "companies"
    id = Column(CHAR(36), primary_key=True, index=True)
    name = Column(String(50))
    responsable_name = Column(String(50))
    cuit = Column(String(50))
    email = Column(String(50))
    phone = Column(String(50))
    address = Column(String(50))
    owner_user_id = Column(CHAR(36))
    
    class Config:
        from_attributes = True

class User(Base):
    __tablename__ = "users"
    
    id = Column(CHAR(36), primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(100))
    first_name = Column(String(50))
    last_name = Column(String(50))
    dni = Column(String(50))
    date_of_birth = Column(String(50))
    phone = Column(String(50))
    role = Column(String(50))
    is_active = Column(Boolean, default=True)
    

class UserCreate(BaseModel):
    id: str
    email: str
    hashed_password: str
    first_name: str
    last_name: str
    dni: str
    date_of_birth: str
    phone: str
    role: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    
class UserUpdate(BaseModel):
    id: str
    email: str
    hashed_password: str
    first_name: str
    last_name: str
    dni: str
    date_of_birth: str
    phone: str
    role: str
    is_active: bool