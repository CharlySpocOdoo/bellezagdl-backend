"""
Enums compartidos entre múltiples módulos.
Este archivo es la única fuente de verdad para enums de PostgreSQL
que se usan en más de una tabla.
"""
import enum
from sqlalchemy import Enum as SAEnum


class Gender(str, enum.Enum):
    male   = "male"
    female = "female"
    other  = "other"


class UserRole(str, enum.Enum):
    admin  = "admin"
    vendor = "vendor"
    client = "client"


class WorkplaceType(str, enum.Enum):
    government      = "government"
    school_employee = "school_employee"
    student         = "student"
    independent     = "independent"
    private         = "private"
    other           = "other"


class InvitationType(str, enum.Enum):
    vendor_onboarding = "vendor_onboarding"
    client_signup     = "client_signup"


class OrderStatus(str, enum.Enum):
    pending             = "pending"
    partially_available = "partially_available"
    confirmed           = "confirmed"
    preparing           = "preparing"
    in_delivery         = "in_delivery"
    delivery_failed     = "delivery_failed"
    delivered_to_vendor = "delivered_to_vendor"
    delivered_to_client = "delivered_to_client"
    return_requested    = "return_requested"
    returned            = "returned"
    cancelled           = "cancelled"


class FailureReason(str, enum.Enum):
    vendor_absent = "vendor_absent"
    accident      = "accident"
    wrong_address = "wrong_address"
    other         = "other"


class SyncStatus(str, enum.Enum):
    running   = "running"
    completed = "completed"
    failed    = "failed"


class BrandOrigin(str, enum.Enum):
    national = "national"
    imported = "imported"


# Instancias de SAEnum con create_type=False para módulos que NO son los dueños
# El módulo dueño usa el enum de Python directamente — SQLAlchemy lo crea solo una vez
gender_type        = SAEnum(Gender,        name="gender",        create_type=False)
userrole_type      = SAEnum(UserRole,      name="userrole",      create_type=False)
workplacetype_type = SAEnum(WorkplaceType, name="workplacetype", create_type=False)
orderstatus_type   = SAEnum(OrderStatus,   name="orderstatus",   create_type=False)
failurereason_type = SAEnum(FailureReason, name="failurereason", create_type=False)
