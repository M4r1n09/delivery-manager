"""
Middleware API – Ice Delivery Manager
Servidor FastAPI que conecta la app móvil con PostgreSQL.
"""
import sys
import os

# Asegurar que el directorio del middleware esté en el path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import API_HOST, API_PORT, MAX_BULK_ITEMS
from database import db
from models import (
    # Auth
    LoginRequest, LoginResponse,
    # Customers
    CustomerCreate, CustomerUpdate,
    # Workers
    WorkerCreate, WorkerUpdate,
    # Routes
    RouteCreate, RouteUpdate,
    # Deliveries
    DeliveryCreate,
    # Sales
    SaleCreate,
    # Trucks
    TruckCreate, TruckAssign, TruckStatusUpdate,
    # Fridges
    FridgeCreate, FridgeUpdate,
    # Bulk
    BulkSyncRequest, BulkSyncResponse, BulkOperationResult,
    # Generic
    ApiResponse,
)


# ─────────────── Lifespan ───────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not db.connect():
        print("⚠️ No se pudo conectar a la DB al iniciar, se reintentará en cada request")
    yield
    # Shutdown
    db.close()


app = FastAPI(
    title="Ice Delivery Manager – Middleware API",
    version="1.0.0",
    description="API REST para interconectar la app móvil con la base de datos PostgreSQL",
    lifespan=lifespan,
)

# CORS – permitir conexiones desde la app móvil y cualquier origen de desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════
#  HEALTH CHECK
# ═══════════════════════════════════════════
@app.get("/health", tags=["Health"])
def health_check():
    alive = db.is_connection_alive()
    return {"status": "ok" if alive else "degraded", "database": alive}


# ═══════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════
@app.post("/auth/login", response_model=LoginResponse, tags=["Auth"])
def login(body: LoginRequest):
    user = db.authenticate(body.username, body.password)
    if user:
        return LoginResponse(success=True, user=user, message="Login exitoso")
    return LoginResponse(success=False, message="Credenciales incorrectas")


# ═══════════════════════════════════════════
#  CUSTOMERS
# ═══════════════════════════════════════════
@app.get("/customers", tags=["Customers"])
def list_customers():
    return ApiResponse(success=True, data=db.get_customers())


@app.get("/customers/{customer_id}", tags=["Customers"])
def get_customer(customer_id: str):
    c = db.get_customer_by_id(customer_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return ApiResponse(success=True, data=c)


@app.get("/customers/barcode/{barcode}", tags=["Customers"])
def get_customer_by_barcode(barcode: str):
    c = db.get_customer_by_barcode(barcode)
    if not c:
        raise HTTPException(404, "Cliente no encontrado con ese código de barras")
    return ApiResponse(success=True, data=c)


@app.post("/customers", tags=["Customers"])
def create_customer(body: CustomerCreate):
    try:
        result = db.add_customer(
            name=body.name, address=body.address, phone=body.phone,
            email=body.email, price_sale=body.price_sale,
            latitude=body.latitude, longitude=body.longitude,
        )
        return ApiResponse(success=True, message="Cliente creado", data=result)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/customers/{customer_id}", tags=["Customers"])
def update_customer(customer_id: str, body: CustomerUpdate):
    ok = db.update_customer(
        customer_id, name=body.name, address=body.address, phone=body.phone,
        email=body.email, price_sale=body.price_sale,
        latitude=body.latitude, longitude=body.longitude,
    )
    if not ok:
        raise HTTPException(404, "Cliente no encontrado o sin cambios")
    return ApiResponse(success=True, message="Cliente actualizado")


@app.delete("/customers/{customer_id}", tags=["Customers"])
def delete_customer(customer_id: str):
    ok = db.delete_customer(customer_id)
    if not ok:
        raise HTTPException(404, "Cliente no encontrado")
    return ApiResponse(success=True, message="Cliente eliminado")


# ═══════════════════════════════════════════
#  WORKERS
# ═══════════════════════════════════════════
@app.get("/workers", tags=["Workers"])
def list_workers():
    return ApiResponse(success=True, data=db.get_workers())


@app.get("/workers/{worker_id}", tags=["Workers"])
def get_worker(worker_id: str):
    w = db.get_worker_by_id(worker_id)
    if not w:
        raise HTTPException(404, "Trabajador no encontrado")
    return ApiResponse(success=True, data=w)


@app.post("/workers", tags=["Workers"])
def create_worker(body: WorkerCreate):
    try:
        db.add_worker(
            username=body.username, name=body.name, password=body.password,
            email=body.email, phone=body.phone,
        )
        return ApiResponse(success=True, message="Trabajador creado")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/workers/{worker_id}", tags=["Workers"])
def update_worker(worker_id: str, body: WorkerUpdate):
    ok = db.update_worker(
        worker_id, username=body.username, name=body.name,
        email=body.email, phone=body.phone, is_active=body.is_active,
    )
    if not ok:
        raise HTTPException(404, "Trabajador no encontrado o sin cambios")
    return ApiResponse(success=True, message="Trabajador actualizado")


@app.delete("/workers/{worker_id}", tags=["Workers"])
def delete_worker(worker_id: str):
    ok = db.delete_worker(worker_id)
    if not ok:
        raise HTTPException(404, "Trabajador no encontrado")
    return ApiResponse(success=True, message="Trabajador eliminado")


# ═══════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════
@app.get("/routes", tags=["Routes"])
def list_routes():
    return ApiResponse(success=True, data=db.get_routes())


@app.get("/routes/{route_id}", tags=["Routes"])
def get_route(route_id: str):
    r = db.get_route_by_id(route_id)
    if not r:
        raise HTTPException(404, "Ruta no encontrada")
    return ApiResponse(success=True, data=r)


@app.get("/routes/{route_id}/customers", tags=["Routes"])
def get_route_customers(route_id: str):
    customers = db.get_route_customers(route_id)
    return ApiResponse(success=True, data=customers)


@app.get("/routes/worker/{worker_id}", tags=["Routes"])
def get_worker_routes(worker_id: str):
    routes = db.get_routes_for_worker(worker_id)
    return ApiResponse(success=True, data=routes)


@app.post("/routes", tags=["Routes"])
def create_route(body: RouteCreate):
    try:
        db.add_route(
            sequence_route=body.sequence_route, name=body.name,
            customer=body.customer, worker_assign=body.worker_assign,
            status=body.status, bag=body.bag, description=body.description,
        )
        return ApiResponse(success=True, message="Ruta creada")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/routes/{route_id}", tags=["Routes"])
def update_route(route_id: str, body: RouteUpdate):
    ok = db.update_route(
        route_id, name=body.name, description=body.description,
        assigned_worker_id=body.assigned_worker_id, status=body.status,
    )
    if not ok:
        raise HTTPException(404, "Ruta no encontrada o sin cambios")
    return ApiResponse(success=True, message="Ruta actualizada")


@app.delete("/routes/{route_id}", tags=["Routes"])
def delete_route(route_id: str):
    ok = db.delete_route(route_id)
    if not ok:
        raise HTTPException(404, "Ruta no encontrada")
    return ApiResponse(success=True, message="Ruta eliminada")


# ═══════════════════════════════════════════
#  DELIVERIES
# ═══════════════════════════════════════════
@app.post("/deliveries", tags=["Deliveries"])
def create_delivery(body: DeliveryCreate):
    ok = db.add_delivery_record(
        customer_id=body.customer_id,
        worker_username=body.worker_username,
        bags_delivered=body.bags_delivered,
        merma_bags=body.merma_bags,
        total_amount=body.total_amount,
        refrigerator_status=body.refrigerator_status.model_dump(),
        cleaning_data=body.cleaning_data.model_dump(),
        evidence_notes=body.evidence_notes,
        route_id=body.route_id,
    )
    if not ok:
        raise HTTPException(500, "Error registrando entrega")
    return ApiResponse(success=True, message="Entrega registrada")


# ═══════════════════════════════════════════
#  SALES
# ═══════════════════════════════════════════
@app.get("/sales", tags=["Sales"])
def list_sales(limit: int = Query(50, ge=1, le=500)):
    return ApiResponse(success=True, data=db.get_sales(limit))


@app.get("/sales/period/{period}", tags=["Sales"])
def get_sales_by_period(period: str):
    if period not in ("weekly", "monthly", "all"):
        raise HTTPException(400, "Período inválido. Usa: weekly, monthly, all")
    return ApiResponse(success=True, data=db.get_sales_by_period(period))


@app.post("/sales", tags=["Sales"])
def create_sale(body: SaleCreate):
    ok = db.add_sale(
        customer_id=body.customer_id,
        worker_username=body.worker_username,
        bags_delivered=body.bags_delivered,
        unit_price=body.unit_price,
        route_id=body.route_id,
    )
    if not ok:
        raise HTTPException(500, "Error registrando venta")
    return ApiResponse(success=True, message="Venta registrada")


# ═══════════════════════════════════════════
#  TRUCKS
# ═══════════════════════════════════════════
@app.get("/trucks", tags=["Trucks"])
def list_trucks():
    return ApiResponse(success=True, data=db.get_trucks())


@app.get("/trucks/available", tags=["Trucks"])
def list_available_trucks():
    return ApiResponse(success=True, data=db.get_available_trucks())


@app.get("/trucks/worker/{worker_id}", tags=["Trucks"])
def get_truck_by_worker(worker_id: str):
    t = db.get_truck_by_worker(worker_id)
    if not t:
        raise HTTPException(404, "No se encontró camión asignado a este trabajador")
    return ApiResponse(success=True, data=t)


@app.post("/trucks", tags=["Trucks"])
def create_truck(body: TruckCreate):
    try:
        db.add_truck(
            license_plate=body.license_plate, brand=body.brand,
            model=body.model, year=body.year, capacity_kg=body.capacity_kg,
            fuel_type=body.fuel_type, notes=body.notes,
        )
        return ApiResponse(success=True, message="Camión registrado")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/trucks/{truck_id}/assign", tags=["Trucks"])
def assign_truck(truck_id: str, body: TruckAssign):
    ok = db.assign_truck(truck_id, body.worker_id)
    if not ok:
        raise HTTPException(400, "No se pudo asignar el camión (ya asignado o no disponible)")
    return ApiResponse(success=True, message="Camión asignado")


@app.post("/trucks/{truck_id}/unassign", tags=["Trucks"])
def unassign_truck(truck_id: str):
    ok = db.unassign_truck(truck_id)
    if not ok:
        raise HTTPException(404, "Camión no encontrado")
    return ApiResponse(success=True, message="Camión desasignado")


@app.put("/trucks/{truck_id}/status", tags=["Trucks"])
def update_truck_status(truck_id: str, body: TruckStatusUpdate):
    ok = db.update_truck_status(truck_id, body.status, body.notes)
    if not ok:
        raise HTTPException(404, "Camión no encontrado")
    return ApiResponse(success=True, message="Estado del camión actualizado")


# ═══════════════════════════════════════════
#  FRIDGES
# ═══════════════════════════════════════════
@app.get("/fridges", tags=["Fridges"])
def list_fridges():
    return ApiResponse(success=True, data=db.get_fridges())


@app.get("/fridges/{fridge_id}", tags=["Fridges"])
def get_fridge(fridge_id: str):
    f = db.get_fridge_by_id(fridge_id)
    if not f:
        raise HTTPException(404, "Refrigerador no encontrado")
    return ApiResponse(success=True, data=f)


@app.get("/fridges/customer/{customer_id}", tags=["Fridges"])
def get_fridges_by_customer(customer_id: str):
    return ApiResponse(success=True, data=db.get_fridges_by_customer(customer_id))


@app.post("/fridges", tags=["Fridges"])
def create_fridge(body: FridgeCreate):
    try:
        db.add_fridge(
            customer_id=body.customer_id, name=body.name,
            size=body.size, capacity=body.capacity, model=body.model,
        )
        return ApiResponse(success=True, message="Refrigerador creado")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/fridges/{fridge_id}", tags=["Fridges"])
def update_fridge(fridge_id: str, body: FridgeUpdate):
    ok = db.update_fridge(
        fridge_id, customer_id=body.customer_id, name=body.name,
        size=body.size, capacity=body.capacity, model=body.model,
    )
    if not ok:
        raise HTTPException(404, "Refrigerador no encontrado o sin cambios")
    return ApiResponse(success=True, message="Refrigerador actualizado")


@app.delete("/fridges/{fridge_id}", tags=["Fridges"])
def delete_fridge(fridge_id: str):
    ok = db.delete_fridge(fridge_id)
    if not ok:
        raise HTTPException(404, "Refrigerador no encontrado")
    return ApiResponse(success=True, message="Refrigerador eliminado")


# ═══════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════
@app.get("/dashboard/stats", tags=["Dashboard"])
def dashboard_stats():
    return ApiResponse(success=True, data=db.get_dashboard_stats())


# ═══════════════════════════════════════════
#  BULK SYNC (carga masiva desde app móvil)
# ═══════════════════════════════════════════
OPERATION_MAP = {
    "create_delivery": lambda d: db.add_delivery_record(**d),
    "create_sale": lambda d: db.add_sale(**d),
    "update_route": lambda d: db.update_route(**d),
}


@app.post("/sync/bulk", response_model=BulkSyncResponse, tags=["Sync"])
def bulk_sync(body: BulkSyncRequest):
    if len(body.operations) > MAX_BULK_ITEMS:
        raise HTTPException(
            400, f"Máximo {MAX_BULK_ITEMS} operaciones por lote"
        )

    results = []
    ok_count = 0
    fail_count = 0

    for op in body.operations:
        handler = OPERATION_MAP.get(op.operation)
        if not handler:
            results.append(BulkOperationResult(
                client_ref=op.client_ref, operation=op.operation,
                success=False, message=f"Operación desconocida: {op.operation}",
            ))
            fail_count += 1
            continue

        try:
            result = handler(op.data)
            if result:
                results.append(BulkOperationResult(
                    client_ref=op.client_ref, operation=op.operation,
                    success=True, message="OK",
                ))
                ok_count += 1
            else:
                results.append(BulkOperationResult(
                    client_ref=op.client_ref, operation=op.operation,
                    success=False, message="La operación retornó False",
                ))
                fail_count += 1
        except Exception as e:
            results.append(BulkOperationResult(
                client_ref=op.client_ref, operation=op.operation,
                success=False, message=str(e),
            ))
            fail_count += 1

    return BulkSyncResponse(
        total=len(body.operations),
        successful=ok_count,
        failed=fail_count,
        results=results,
    )


# ═══════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Iniciando middleware en {API_HOST}:{API_PORT}")
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)

