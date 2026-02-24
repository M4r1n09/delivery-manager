"""
sync_queue.py - Cola local offline-first con reintento limitado
"""

import json
import os
import httpx
from datetime import datetime

QUEUE_FILE = "pending_operations.json"
SYNC_STATE_FILE = "sync_state.json"
MIDDLEWARE_URL = os.getenv(
    "MIDDLEWARE_URL", "http://localhost:6789"
)  # "http://18.117.83.152:6789"
MAX_AUTO_RETRIES = 2


def _load_queue() -> list:
    try:
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_queue(queue: list):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2, default=str)


def _load_sync_state() -> dict:
    try:
        with open(SYNC_STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"auto_retries_done": 0, "manual_required": False}


def _save_sync_state(state: dict):
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def reset_sync_state():
    """Resetea el contador cuando hay pendientes nuevos"""
    _save_sync_state({"auto_retries_done": 0, "manual_required": False})


def is_manual_required() -> bool:
    """Devuelve True si los 2 intentos automaticos ya fallaron"""
    state = _load_sync_state()
    return state.get("manual_required", False)


def add_to_queue(operation: str, endpoint: str, data: dict):
    queue = _load_queue()
    queue.append(
        {
            "id": f"{datetime.now().timestamp()}",
            "operation": operation,
            "endpoint": endpoint,
            "data": data,
            "created_at": datetime.now().isoformat(),
        }
    )
    _save_queue(queue)
    # Hay datos nuevos, resetear intentos automaticos
    reset_sync_state()


def flush_queue(is_manual: bool = False) -> dict:
    """
    Envia pendientes al servidor.

    Args:
        is_manual: True si lo activo el usuario con el boton.
                   Si es False, respeta el limite de 2 intentos.
    """
    queue = _load_queue()
    if not queue:
        return {"sent": 0, "failed": 0, "pending": 0, "blocked": False}

    state = _load_sync_state()

    # Si NO es manual y ya gastamos los 2 intentos, no hacer nada
    if not is_manual and state["auto_retries_done"] >= MAX_AUTO_RETRIES:
        return {
            "sent": 0,
            "failed": 0,
            "pending": len(queue),
            "blocked": True,  # Senala que necesita accion manual
        }

    sent = 0
    failed = 0
    remaining = []

    for item in queue:
        try:
            if item["operation"] == "POST":
                resp = httpx.post(
                    f"{MIDDLEWARE_URL}{item['endpoint']}", json=item["data"], timeout=10
                )
            elif item["operation"] == "PUT":
                resp = httpx.put(
                    f"{MIDDLEWARE_URL}{item['endpoint']}", json=item["data"], timeout=10
                )
            else:
                continue

            if resp.status_code in (200, 201):
                sent += 1
                continue  # Eliminado de la cola
            else:
                failed += 1
                remaining.append(item)

        except (httpx.ConnectError, httpx.TimeoutException):
            failed += 1
            remaining.append(item)

    _save_queue(remaining)

    # Actualizar estado de reintentos
    if len(remaining) > 0 and not is_manual:
        state["auto_retries_done"] += 1
        if state["auto_retries_done"] >= MAX_AUTO_RETRIES:
            state["manual_required"] = True
    else:
        # Todo enviado O fue envío manual, resetear completamente
        state = {"auto_retries_done": 0, "manual_required": False}

    _save_sync_state(state)

    return {"sent": sent, "failed": failed, "pending": len(remaining), "blocked": False}


def get_pending_count() -> int:
    return len(_load_queue())
