from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ======================== AUTH ========================
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    user: Optional[Dict[str, Any]] = None
    message: str = ""


# ======================== CUSTOMERS ========================
class CustomerCreate(BaseModel):
    name: str
    address: str
    phone: str
    email: Optional[str] = None
    price_sale: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0


class CustomerUpdate(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    email: Optional[str] = None
    price_sale: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0


# ======================== USERS ========================
class UserCreate(BaseModel):
    username: str
    name: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    username: str
    name: str
    email: str = ""
    phone: str = ""
    is_active: bool = True


# ======================== WORKERS ========================
class WorkerCreate(BaseModel):
    username: str
    name: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None


class WorkerUpdate(BaseModel):
    username: str
    name: str
    email: str = ""
    phone: str = ""
    is_active: bool = True


# ======================== ROUTES ========================
class RouteCreate(BaseModel):
    sequence_route: int
    name: str
    customer: str
    worker_assign: str
    status: str = "pending"
    bag: str = "0"
    description: Optional[str] = None


class RouteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    assigned_worker_id: Optional[str] = None
    status: Optional[str] = None


# ======================== DELIVERIES ========================
class RefrigeratorStatus(BaseModel):
    status: str
    notes: str = ""


class CleaningData(BaseModel):
    performed: bool = False
    notes: str = ""


class DeliveryCreate(BaseModel):
    customer_id: str
    worker_username: str
    bags_delivered: int
    merma_bags: int = 0
    total_amount: float
    refrigerator_status: RefrigeratorStatus
    cleaning_data: CleaningData
    evidence_notes: str = ""
    route_id: str


# ======================== SALES ========================
class SaleCreate(BaseModel):
    customer_id: str
    worker_id: str
    route_id: Optional[str] = None
    total_amount: float
    bags_delivered: int
    notes: str = ""
    delivered_at: Optional[str] = None


# ======================== TRUCKS ========================
class TruckCreate(BaseModel):
    license_plate: str
    brand: str
    model: str
    year: Optional[int] = None
    capacity_kg: int = 1000
    fuel_type: str = "gasoline"
    notes: Optional[str] = None


class TruckAssign(BaseModel):
    worker_id: str


class TruckStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


# ======================== FRIDGES ========================
class FridgeCreate(BaseModel):
    customer_id: str
    name: str
    size: str
    capacity: str
    model: str


class FridgeUpdate(BaseModel):
    customer_id: str
    name: str
    size: str
    capacity: str
    model: str


# ======================== BULK SYNC ========================
class BulkOperation(BaseModel):
    """Una operación individual dentro de una carga masiva."""

    operation: str  # "create_delivery", "create_sale", "update_route", etc.
    data: Dict[str, Any]
    client_ref: Optional[str] = None  # Referencia del cliente para tracking


class BulkSyncRequest(BaseModel):
    """Request para carga masiva de datos desde la app móvil."""

    operations: List[BulkOperation]
    device_id: Optional[str] = None
    sync_timestamp: Optional[str] = None


class BulkOperationResult(BaseModel):
    """Resultado de una operación individual."""

    client_ref: Optional[str] = None
    operation: str
    success: bool
    message: str = ""
    data: Optional[Dict[str, Any]] = None


class BulkSyncResponse(BaseModel):
    """Respuesta de la carga masiva."""

    total: int
    successful: int
    failed: int
    results: List[BulkOperationResult]


# ======================== GENERIC RESPONSE ========================
class ApiResponse(BaseModel):
    success: bool
    message: str = ""
    data: Optional[Any] = None
