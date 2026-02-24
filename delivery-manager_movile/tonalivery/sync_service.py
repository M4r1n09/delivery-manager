"""
sync_service.py - Servicio de sincronizacion entre middleware y DB local
"""

import httpx  # o requests
import json
import os
from datetime import datetime, timedelta
from database_mobile_simplified import db_manager

# URL de tu middleware
MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "http://localhost:9000")

# Archivo para guardar la ultima sincronizacion
SYNC_TIMESTAMP_FILE = "last_sync.json"


def get_last_sync_time() -> datetime | None:
    """Lee la ultima vez que se sincronizo"""
    try:
        with open(SYNC_TIMESTAMP_FILE, "r") as f:
            data = json.load(f)
            return datetime.fromisoformat(data["last_sync"])
    except (FileNotFoundError, KeyError, ValueError):
        return None


def save_sync_time():
    """Guarda el timestamp de sincronizacion"""
    with open(SYNC_TIMESTAMP_FILE, "w") as f:
        json.dump({"last_sync": datetime.now().isoformat()}, f)


def needs_sync() -> bool:
    """Verifica si han pasado mas de 24 horas desde la ultima sync"""
    last = get_last_sync_time()
    if last is None:
        return True
    return datetime.now() - last > timedelta(hours=24)


def sync_all_data() -> dict:
    """
    Descarga todos los datos del middleware y actualiza el db_manager local.
    Retorna un resumen del resultado.
    """
    results = {"success": False, "errors": [], "synced": []}

    try:
        # 1. Sincronizar Workers
        resp = httpx.get(f"{MIDDLEWARE_URL}/workers", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                db_manager.users = data["data"]
                results["synced"].append(f"Workers: {len(data['data'])}")
        else:
            results["errors"].append(f"Workers: HTTP {resp.status_code}")

        # 2. Sincronizar Rutas
        resp = httpx.get(f"{MIDDLEWARE_URL}/routes", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                db_manager.routes = data["data"]
                results["synced"].append(f"Rutas: {len(data['data'])}")
        else:
            results["errors"].append(f"Rutas: HTTP {resp.status_code}")

        # 3. Sincronizar Clientes
        resp = httpx.get(f"{MIDDLEWARE_URL}/customers", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                db_manager.customers = data["data"]
                results["synced"].append(f"Clientes: {len(data['data'])}")
        else:
            results["errors"].append(f"Clientes: HTTP {resp.status_code}")
        # 4. Sincronizar Camiones
        resp = httpx.get(f"{MIDDLEWARE_URL}/trucks", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                db_manager.trucks = data["data"]
                results["synced"].append(f"Camiones: {len(data['data'])}")
        else:
            results["errors"].append(f"Camiones: HTTP {resp.status_code}")

        # 5. Sincronizar Ventas
        resp = httpx.get(f"{MIDDLEWARE_URL}/sales?limit=500", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                db_manager.sales = data["data"]
                results["synced"].append(f"Ventas: {len(data['data'])}")
        else:
            results["errors"].append(f"Ventas: HTTP {resp.status_code}")

        # Guardar timestamp si hubo al menos una sync exitosa
        if results["synced"]:
            save_sync_time()
            results["success"] = True

    except httpx.ConnectError:
        results["errors"].append("No se pudo conectar al servidor")
    except httpx.TimeoutException:
        results["errors"].append("Timeout al conectar con el servidor")
    except Exception as e:
        results["errors"].append(f"Error inesperado: {str(e)}")

    return results


def sync_if_needed() -> dict | None:
    """Sincroniza solo si han pasado mas de 24 horas"""
    # if needs_sync():
    return sync_all_data()
    # return None
