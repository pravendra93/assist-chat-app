# app/schemas.py
from pydantic import BaseModel, EmailStr
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime



class AccountOut(BaseModel):
    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    role: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}




class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    sender: str
    text: str
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}





class TenantOut(BaseModel):
    id: UUID
    name: str
    owner_account_id: Optional[UUID] = None
    status: str
    plan: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}



class TenantUserOut(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}



