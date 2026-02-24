"""
Database manager simplificado para la aplicación móvil Ice Delivery
Usa datos mock ya que Android no soporta PostgreSQL
"""

import os
from typing import Dict, List, Optional
import hashlib
import uuid
from datetime import datetime
import json


class DatabaseManager:
    def __init__(self):
        """Inicializar con datos mock"""
        self.users = [
            {
                "id": str(uuid.uuid4()),
                "username": "admin",
                "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
                "role": "admin",
                "name": "Administrador",
                "email": "admin@tonalivery.com",
                "phone": "+1234567890",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "username": "worker1",
                "password_hash": hashlib.sha256("worker123".encode()).hexdigest(),
                "role": "worker",
                "name": "Juan Pérez",
                "email": "juan@tonalivery.com",
                "phone": "+1234567891",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            },
        ]

        self.customers = [
            {
                "id": str(uuid.uuid4()),
                "name": "Restaurante El Buen Sabor",
                "address": "Av. Principal 123, Centro",
                "phone": "+1234567892",
                "email": "pedidos@elbuensabor.com",
                "price_sale": 15.50,
                "latitude": 0.0,
                "longitude": 0.0,
                "barcode": "1001234567",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Hotel Plaza",
                "address": "Calle Comercio 456, Zona Hotelera",
                "phone": "+1234567893",
                "email": "compras@hotelplaza.com",
                "price_sale": 12.00,
                "latitude": 0.0,
                "longitude": 0.0,
                "barcode": "1001234568",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Supermercado Mi Tienda",
                "address": "Av. Los Andes 789, Sector Norte",
                "phone": "+1234567894",
                "email": "gerencia@mitienda.com",
                "price_sale": 18.75,
                "latitude": 0.0,
                "longitude": 0.0,
                "barcode": "1001234569",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            },
        ]

        self.routes = [
            {
                "id": str(uuid.uuid4()),
                "name": "Ruta Centro",
                "description": "Ruta del centro de la ciudad",
                "status": "pending",
                "bags": 50,
                "assigned_worker_id": self.users[1]["id"],  # worker1
                "created_at": datetime.now().isoformat(),
                "customer_name": "Restaurante El Buen Sabor",
                "customer_email": "pedidos@elbuensabor.com",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Ruta Hotelera",
                "description": "Ruta zona hotelera",
                "status": "pending",
                "bags": 30,
                "assigned_worker_id": self.users[1]["id"],  # worker1
                "created_at": datetime.now().isoformat(),
                "customer_name": "Hotel Plaza",
                "customer_email": "compras@hotelplaza.com",
            },
        ]

        self.trucks = [
            {
                "id": str(uuid.uuid4()),
                "license_plate": "ABC-123",
                "brand": "Ford",
                "model": "F-150",
                "year": 2020,
                "capacity_kg": 1000,
                "fuel_type": "gasoline",
                "status": "available",
                "assigned_worker_id": None,
                "last_maintenance": None,
                "notes": "",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            }
        ]

        self.sales = []
        self.deliveries = []

        print("✅ Mock database initialized successfully")

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Autentica un usuario"""
        if self.users:
            print("KEYS del primer user:", self.users[0].keys())
            print("Primer user:", self.users[0])
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        for user in self.users:
            print(f"Checking user: {user['username']}")
            if (
                user["username"] == username
                and user["password_hash"] == password_hash
                and user["is_active"]
            ):
                return user
        return None

    def get_routes(self) -> List[Dict]:
        """Obtiene todas las rutas activas"""
        return [
            route
            for route in self.routes
            if route["status"] in ["pending", "in_progress"]
        ]

    def get_route_customers(self, route_id: str) -> List[Dict]:
        """Obtiene clientes de una ruta"""
        # Mock: retorna el primer cliente para simplificar
        return [self.customers[0]] if self.customers else []

    def get_route_customer_by_id(self, route_id: str):
        """Obtiene ID del cliente de una ruta"""
        # Mock: retorna el ID del primer cliente
        return self.customers[0]["id"] if self.customers else None

    def get_customer_by_barcode(self, barcode: str) -> Optional[Dict]:
        """Obtiene cliente por código de barras"""
        for customer in self.customers:
            if customer["barcode"] == barcode and customer["is_active"]:
                return customer
        return None

    def get_customers(self) -> List[Dict]:
        """Obtiene todos los clientes activos"""
        return [c for c in self.customers if c["is_active"]]

    def get_workers(self) -> List[Dict]:
        """Obtiene todos los trabajadores"""
        return [u for u in self.users if u["role"] == "worker"]

    def get_sales(self, limit: int = 50) -> List[Dict]:
        """Obtiene las ventas más recientes"""
        return self.sales[-limit:] if self.sales else []

    def get_dashboard_stats(self) -> Dict:
        """Obtiene estadísticas para el dashboard"""
        return {
            "total_customers": len([c for c in self.customers if c["is_active"]]),
            "total_workers": len([u for u in self.users if u["role"] == "worker"]),
            "total_sales": len(self.sales),
            "total_revenue": sum(sale.get("total_amount", 0) for sale in self.sales),
            "total_trucks": len([t for t in self.trucks if t["is_active"]]),
            "available_trucks": len(
                [t for t in self.trucks if t["status"] == "available"]
            ),
        }

    def get_worker_truck(self, worker_username: str) -> Optional[Dict]:
        """Obtiene camión asignado al trabajador"""
        for truck in self.trucks:
            print(truck)
            print("\nusername:", worker_username)
            if (
                truck["assigned_worker_username"] == worker_username
                and truck["status"] == "in_use"
            ):
                return truck
        return None

    def add_delivery_record(
        self,
        customer_id,
        worker_username,
        bags_delivered,
        merma_bags,
        total_amount,
        refrigerator_status,
        cleaning_data,
        evidence_notes,
        route_id,
    ):
        """Registra un record completo de entrega"""
        delivery_id = str(uuid.uuid4())
        delivery = {
            "id": delivery_id,
            "customer_id": customer_id,
            "worker_id": next(
                (u["id"] for u in self.users if u["username"] == worker_username), None
            ),
            "bags_delivered": bags_delivered,
            "merma_bags": merma_bags,
            "total_amount": total_amount,
            "refrigerator_status": (
                refrigerator_status.get("status")
                if isinstance(refrigerator_status, dict)
                else refrigerator_status
            ),
            "status_notes": (
                refrigerator_status.get("notes")
                if isinstance(refrigerator_status, dict)
                else ""
            ),
            "cleaning_performed": (
                cleaning_data.get("performed")
                if isinstance(cleaning_data, dict)
                else False
            ),
            "cleaning_notes": (
                cleaning_data.get("notes") if isinstance(cleaning_data, dict) else ""
            ),
            "evidence_notes": evidence_notes,
            "delivery_date": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
        }
        self.deliveries.append(delivery)

        # También crear una venta
        sale = {
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "worker_id": delivery["worker_id"],
            "route_id": route_id,
            "total_amount": total_amount,
            "bags_delivered": bags_delivered,
            "notes": f"Entrega automática - {evidence_notes}",
            "created_at": datetime.now().isoformat(),
        }
        self.sales.append(sale)

        print(f"✅ Entrega registrada exitosamente - ID: {delivery_id}")
        return True

    def update_route_status(self, route_id: str, status: str) -> bool:
        """Actualizar estado de ruta"""
        for route in self.routes:
            if route["id"] == route_id:
                route["status"] = status
                return True
        return False

    def mark_customer_delivered(self, route_id: str, customer_id: str) -> bool:
        """Marcar cliente como entregado en ruta"""
        # En el mock, simplemente retornamos True
        return True

    # Métodos adicionales para compatibilidad
    def get_routes_for_worker(self, worker_id: str) -> List[Dict]:
        """Obtiene rutas asignadas a un trabajador"""
        return [
            route
            for route in self.routes
            if route.get("assigned_worker_id") == worker_id
        ]

    def get_delivery_history_for_worker(
        self, worker_id: str, limit: int = 10
    ) -> List[Dict]:
        """Obtiene historial de entregas del trabajador"""
        worker_deliveries = [d for d in self.deliveries if d["worker_id"] == worker_id]
        return worker_deliveries[-limit:] if worker_deliveries else []

    def check_worker_has_truck(self, worker_id: str) -> bool:
        """Verifica si un trabajador tiene camión asignado"""
        return any(
            truck["assigned_worker_id"] == worker_id
            for truck in self.trucks
            if truck["is_active"]
        )

    def get_worker_routes_summary(self, worker_id: str) -> Dict:
        """Obtiene resumen de rutas del trabajador"""
        worker_routes = self.get_routes_for_worker(worker_id)
        return {
            "pending_routes": len(
                [r for r in worker_routes if r["status"] == "pending"]
            ),
            "in_progress_routes": len(
                [r for r in worker_routes if r["status"] == "in_progress"]
            ),
            "today_deliveries": len(
                [
                    d
                    for d in self.deliveries
                    if d["worker_id"] == worker_id
                    and d["delivery_date"].startswith(
                        datetime.now().strftime("%Y-%m-%d")
                    )
                ]
            ),
        }

    def close(self):
        """Método de compatibilidad - no hace nada en mock"""
        pass


# Instancia global del manejador de base de datos
db_manager = DatabaseManager()
