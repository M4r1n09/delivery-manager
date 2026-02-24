import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import uuid
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

from config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
)


class DatabaseManager:
    def __init__(self):
        self.connection_params = {
            "host": DB_HOST,
            "port": DB_PORT,
            "database": DB_NAME,
            "user": DB_USER,
            "password": DB_PASSWORD,
        }
        self.connection = None
        self.max_retries = 5
        self.retry_delay = 1
        self.connection_timeout = 30
        self.last_ping = None
        self.ping_interval = 300
        self._lock = threading.Lock()

    # ─────────────── Conexión ───────────────
    def connect(self) -> bool:
        for attempt in range(self.max_retries):
            try:
                if self.connection:
                    try:
                        self.connection.close()
                    except Exception:
                        pass

                self.connection = psycopg2.connect(
                    connect_timeout=self.connection_timeout,
                    **self.connection_params,
                )
                self.connection.autocommit = True
                self.last_ping = datetime.now()
                print(f"✅ Conexión a DB exitosa (intento {attempt + 1})")
                return True
            except Exception as e:
                print(
                    f"❌ Error conectando (intento {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    wait = self.retry_delay * (2**attempt)
                    time.sleep(wait)
                else:
                    self.connection = None
        return False

    def is_connection_alive(self) -> bool:
        if not self.connection:
            return False
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")
                self.last_ping = datetime.now()
                return True
        except (psycopg2.OperationalError, psycopg2.InterfaceError, AttributeError):
            return False

    def ensure_connection(self) -> bool:
        with self._lock:
            if not self.is_connection_alive():
                print("🔄 Reconectando...")
                return self.connect()
            return True

    def execute_query(self, query: str, params=None, fetch: bool = False):
        """Ejecuta query con reconexión automática."""
        if not self.ensure_connection():
            raise Exception("No se pudo conectar a la base de datos")

        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                return cur.rowcount
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            print(f"⚠️ Error de conexión: {e}")
            if self.ensure_connection():
                with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params)
                    if fetch:
                        return cur.fetchall()
                    return cur.rowcount
            raise Exception("No se pudo reconectar a la base de datos")

    def execute_transaction(self, queries: List[tuple]) -> bool:
        """Ejecuta múltiples queries en una transacción."""
        if not self.ensure_connection():
            raise Exception("No se pudo conectar a la base de datos")

        old_autocommit = self.connection.autocommit
        self.connection.autocommit = False
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
                results = []
                for query, params in queries:
                    cur.execute(query, params)
                    try:
                        results.append(cur.fetchall())
                    except psycopg2.ProgrammingError:
                        results.append(None)
            self.connection.commit()
            return results
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            self.connection.autocommit = old_autocommit

    # ─────────────── Helpers ───────────────
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def close(self):
        if self.connection:
            self.connection.close()
            print("🔌 Conexión cerrada")

    # ─────────────── Auth ───────────────
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        hashed = self.hash_password(password)
        rows = self.execute_query(
            """SELECT id, username, role, name, email, phone
               FROM users
               WHERE username = %s AND password_hash = %s AND is_active = TRUE""",
            (username, hashed),
            fetch=True,
        )
        if rows:
            row = dict(rows[0])
            row["id"] = str(row["id"])
            return row
        return None

    # ─────────────── Customers ───────────────
    def get_customers(self) -> List[Dict]:
        rows = self.execute_query(
            """SELECT id, name, address, phone, barcode, email, latitude, longitude, price_sale, is_active
               FROM customers WHERE is_active = TRUE ORDER BY name""",
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    def get_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        rows = self.execute_query(
            """SELECT id, name, address, phone, email, latitude, longitude, price_sale
               FROM customers WHERE id = %s AND is_active = TRUE""",
            (customer_id,),
            fetch=True,
        )
        return self._serialize(rows[0]) if rows else None

    def get_customer_by_barcode(self, barcode: str) -> Optional[Dict]:
        rows = self.execute_query(
            """SELECT id, name, address, phone, email, price_sale, barcode, latitude, longitude
               FROM customers WHERE barcode = %s AND is_active = TRUE""",
            (barcode,),
            fetch=True,
        )
        return self._serialize(rows[0]) if rows else None

    def add_customer(
        self,
        name,
        address,
        phone,
        email=None,
        price_sale=0.0,
        latitude=0.0,
        longitude=0.0,
    ) -> Optional[Dict]:
        import re, barcode as barcode_lib

        clean_name = re.sub(r"[^a-zA-Z0-9]", "", name)[:6].upper()
        clean_addr = re.sub(r"[^a-zA-Z0-9]", "", address)[:6].upper()
        code = barcode_lib.Code128(f"{clean_name}-{clean_addr}")
        cid = str(uuid.uuid4())
        self.execute_query(
            """INSERT INTO customers (id, name, address, latitude, longitude, phone, email, price_sale, barcode, is_active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)""",
            (
                cid,
                name,
                address,
                latitude,
                longitude,
                phone,
                email,
                price_sale,
                str(code),
            ),
        )
        return self.get_customer_by_id(cid)

    def update_customer(
        self,
        customer_id,
        name,
        address,
        phone=None,
        email=None,
        price_sale=0.0,
        latitude=0.0,
        longitude=0.0,
    ) -> bool:
        count = self.execute_query(
            """UPDATE customers
               SET name=%s, address=%s, latitude=%s, longitude=%s, phone=%s, email=%s, price_sale=%s
               WHERE id=%s AND is_active=TRUE""",
            (name, address, latitude, longitude, phone, email, price_sale, customer_id),
        )
        return count > 0

    def delete_customer(self, customer_id) -> bool:
        self.execute_query("DELETE FROM sales WHERE customer_id=%s", (customer_id,))
        count = self.execute_query("DELETE FROM customers WHERE id=%s", (customer_id,))
        return count > 0

    # ─────────────── Workers ───────────────
    def get_workers(self) -> List[Dict]:
        rows = self.execute_query(
            """SELECT id, username, password_hash, role, name, email, phone, created_at, is_active
               FROM users WHERE role='worker' ORDER BY name""",
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    def get_worker_by_id(self, worker_id) -> Optional[Dict]:
        rows = self.execute_query(
            """SELECT id, username, password_hash, role,name, email, phone, is_active
               FROM users WHERE id=%s AND role='worker'""",
            (worker_id,),
            fetch=True,
        )
        return self._serialize(rows[0]) if rows else None

    def add_worker(self, username, name, password, email=None, phone=None) -> bool:
        hashed = self.hash_password(password)
        self.execute_query(
            """INSERT INTO users (id, username, password_hash, role, name, email, phone, is_active)
               VALUES (%s,%s,%s,'worker',%s,%s,%s,TRUE)""",
            (str(uuid.uuid4()), username, hashed, name, email, phone),
        )
        return True

    def update_worker(
        self, worker_id, username, name, email="", phone="", is_active=True
    ) -> bool:
        count = self.execute_query(
            """UPDATE users SET username=%s, name=%s, email=%s, phone=%s, is_active=%s
               WHERE id=%s AND role='worker'""",
            (username, name, email, phone, is_active, worker_id),
        )
        return count > 0

    def delete_worker(self, worker_id) -> bool:
        self.execute_query("DELETE FROM sales WHERE worker_id=%s", (worker_id,))
        count = self.execute_query(
            "DELETE FROM users WHERE id=%s AND role='worker'",
            (worker_id,),
        )
        return count > 0

    # ─────────────── Routes ───────────────
    def get_routes(self) -> List[Dict]:
        rows = self.execute_query(
            """SELECT r.id, r.name, r.description, r.status, r.bags,
                    u.name AS assigned_worker_name, u.username AS assigned_worker_username,
                    c.id AS customer_id,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    c.phone AS customer_phone,
                    c.address AS customer_address,
                    c.barcode AS customer_barcode,
                    rc.order_sequence
            FROM routes r
            LEFT JOIN users u ON r.assigned_worker_id = u.id
            LEFT JOIN route_customers rc ON r.id = rc.route_id
            LEFT JOIN customers c ON rc.customer_id = c.id
            WHERE r.status IN ('pending','in_progress')
            ORDER BY r.name, rc.order_sequence""",
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    def get_route_by_id(self, route_id) -> Optional[Dict]:
        rows = self.execute_query(
            "SELECT id, name, description, assigned_worker_id, status FROM routes WHERE id=%s",
            (route_id,),
            fetch=True,
        )
        return self._serialize(rows[0]) if rows else None

    def add_route(
        self,
        sequence_route,
        name,
        customer,
        worker_assign,
        status="pending",
        bag="0",
        description=None,
    ) -> bool:
        rid = str(uuid.uuid4())
        self.execute_query(
            """INSERT INTO routes (id, name, description, bags, assigned_worker_id, status, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (rid, name, description, int(bag), worker_assign, status, datetime.now()),
        )
        self.execute_query(
            """INSERT INTO route_customers (id, route_id, customer_id, order_sequence)
               VALUES (%s,%s,%s,%s)""",
            (str(uuid.uuid4()), rid, customer, sequence_route),
        )
        return True

    def update_route(
        self,
        route_id,
        name=None,
        description=None,
        assigned_worker_id=None,
        status=None,
    ) -> bool:
        parts, vals = [], []
        if name is not None:
            parts.append("name=%s")
            vals.append(name)
        if description is not None:
            parts.append("description=%s")
            vals.append(description)
        if assigned_worker_id is not None:
            parts.append("assigned_worker_id=%s")
            vals.append(assigned_worker_id)
        if status is not None:
            parts.append("status=%s")
            vals.append(status)
        if not parts:
            return False
        vals.append(route_id)
        count = self.execute_query(
            f"UPDATE routes SET {', '.join(parts)} WHERE id=%s",
            vals,
        )
        return count > 0

    def delete_route(self, route_id) -> bool:
        count = self.execute_query("DELETE FROM routes WHERE id=%s", (route_id,))
        return count > 0

    def get_routes_for_worker(self, worker_id) -> List[Dict]:
        rows = self.execute_query(
            """SELECT r.id AS route_id, r.name AS route_name, r.description AS route_description,
                      r.status AS route_status, r.created_at AS creada_en, r.bags,
                      rc.customer_id, rc.order_sequence,
                      c.address AS customer_address, c.phone AS customer_phone,
                      c.name AS customer_name
               FROM routes r
               JOIN route_customers rc ON r.id = rc.route_id
               JOIN customers c ON rc.customer_id = c.id
               WHERE r.assigned_worker_id = %s
                 AND r.created_at::date = CURRENT_DATE""",
            (worker_id,),
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    def get_route_customers(self, route_id) -> List[Dict]:
        rows = self.execute_query(
            """SELECT c.id, c.name, c.address, c.phone, c.email, c.price_sale,
                      c.barcode, c.latitude, c.longitude, rc.order_sequence
               FROM route_customers rc
               JOIN customers c ON rc.customer_id = c.id
               WHERE rc.route_id = %s
               ORDER BY rc.order_sequence""",
            (route_id,),
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    # ─────────────── Deliveries ───────────────
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
    ) -> bool:
        import pytz

        # Obtener worker_id
        rows = self.execute_query(
            "SELECT id FROM users WHERE username=%s AND role='worker'",
            (worker_username,),
            fetch=True,
        )
        if not rows:
            return False
        worker_id = rows[0]["id"]

        tz = pytz.timezone("America/Mexico_City")
        now = datetime.now(tz)

        old_autocommit = self.connection.autocommit
        self.connection.autocommit = False
        try:
            cur = self.connection.cursor()
            cur.execute(
                """INSERT INTO deliveries
                   (customer_id, worker_id, bags_delivered, merma_bags, total_amount,
                    refrigerator_status, status_notes, cleaning_performed, cleaning_notes,
                    evidence_notes, delivery_date)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    customer_id,
                    worker_id,
                    bags_delivered,
                    merma_bags,
                    total_amount,
                    str(refrigerator_status.get("status", "")),
                    str(refrigerator_status.get("notes", "")),
                    cleaning_data.get("performed", False),
                    cleaning_data.get("notes", ""),
                    evidence_notes,
                    now,
                ),
            )
            note = (
                f"Estado refrigerador:{refrigerator_status.get('notes','')}|"
                f"Limpieza:{cleaning_data.get('notes','')}|Notas:{evidence_notes}"
            )
            cur.execute(
                """INSERT INTO sales (customer_id, worker_id, route_id, bags_delivered, total_amount, notes)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (customer_id, worker_id, route_id, bags_delivered, total_amount, note),
            )
            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            print(f"❌ Error registrando entrega: {e}")
            return False
        finally:
            self.connection.autocommit = old_autocommit

    # ─────────────── Sales ───────────────
    def add_sale(
        self,
        customer_id,
        worker_username,
        bags_delivered,
        unit_price=15.0,
        route_id=None,
    ) -> bool:
        rows = self.execute_query(
            "SELECT id FROM users WHERE username=%s",
            (worker_username,),
            fetch=True,
        )
        if not rows:
            return False
        worker_id = rows[0]["id"]
        total = bags_delivered * unit_price
        sid = str(uuid.uuid4())
        self.execute_query(
            """INSERT INTO sales (id, customer_id, worker_id, route_id, total_amount, bags_delivered)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (sid, customer_id, worker_id, route_id, total, bags_delivered),
        )
        return True

    def get_sales(self, limit=50) -> List[Dict]:
        rows = self.execute_query(
            """SELECT s.id, s.total_amount, s.bags_delivered, s.created_at,
                      c.name AS customer_name, c.address AS customer_address,
                      u.name AS worker_name
               FROM sales s
               JOIN customers c ON s.customer_id = c.id
               JOIN users u ON s.worker_id = u.id
               ORDER BY s.created_at DESC LIMIT %s""",
            (limit,),
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    def get_sales_by_period(self, period: str) -> List[Dict]:
        if period == "weekly":
            filt = "s.created_at >= CURRENT_DATE - INTERVAL '7 days'"
        elif period == "monthly":
            filt = "s.created_at >= CURRENT_DATE - INTERVAL '30 days'"
        else:
            filt = "TRUE"
        rows = self.execute_query(
            f"""SELECT s.id, s.total_amount, s.bags_delivered, s.created_at,
                       c.name AS customer_name, u.name AS worker_name
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                JOIN users u ON s.worker_id = u.id
                WHERE {filt}
                ORDER BY s.created_at DESC""",
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    # ─────────────── Trucks ───────────────
    def get_trucks(self) -> List[Dict]:
        rows = self.execute_query(
            """SELECT t.id, t.license_plate, t.brand, t.model, t.year,
                      t.capacity_kg, t.fuel_type, t.status, t.last_maintenance,
                      t.notes, t.created_at,
                      u.name AS assigned_worker_name, u.username AS assigned_worker_username
               FROM trucks t
               LEFT JOIN users u ON t.assigned_worker_id = u.id
               WHERE t.is_active = TRUE ORDER BY t.license_plate""",
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    def add_truck(
        self,
        license_plate,
        brand,
        model,
        year=None,
        capacity_kg=1000,
        fuel_type="gasoline",
        notes=None,
    ) -> bool:
        self.execute_query(
            """INSERT INTO trucks (id, license_plate, brand, model, year, capacity_kg, fuel_type, notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                str(uuid.uuid4()),
                license_plate,
                brand,
                model,
                year,
                capacity_kg,
                fuel_type,
                notes,
            ),
        )
        return True

    def assign_truck(self, truck_id, worker_id) -> bool:
        self.execute_query(
            "UPDATE trucks SET assigned_worker_id=NULL, status='available' WHERE assigned_worker_id=%s",
            (worker_id,),
        )
        count = self.execute_query(
            "UPDATE trucks SET assigned_worker_id=%s, status='in_use' WHERE id=%s AND status='available'",
            (worker_id, truck_id),
        )
        return count > 0

    def unassign_truck(self, truck_id) -> bool:
        count = self.execute_query(
            "UPDATE trucks SET assigned_worker_id=NULL, status='available' WHERE id=%s",
            (truck_id,),
        )
        return count > 0

    def update_truck_status(self, truck_id, status, notes=None) -> bool:
        if notes:
            count = self.execute_query(
                "UPDATE trucks SET status=%s, notes=%s WHERE id=%s",
                (status, notes, truck_id),
            )
        else:
            count = self.execute_query(
                "UPDATE trucks SET status=%s WHERE id=%s",
                (status, truck_id),
            )
        return count > 0

    def get_truck_by_worker(self, worker_id) -> Optional[Dict]:
        rows = self.execute_query(
            """SELECT t.id, t.license_plate, t.brand, t.model, t.year,
                      t.capacity_kg, t.fuel_type, t.status, t.last_maintenance, t.notes
               FROM trucks t
               WHERE t.assigned_worker_id = %s AND t.is_active = TRUE""",
            (worker_id,),
            fetch=True,
        )
        return self._serialize(rows[0]) if rows else None

    def get_available_trucks(self) -> List[Dict]:
        rows = self.execute_query(
            """SELECT id, license_plate, brand, model, capacity_kg
               FROM trucks WHERE status='available' AND is_active=TRUE ORDER BY license_plate""",
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    # ─────────────── Fridges ───────────────
    def get_fridges(self) -> List[Dict]:
        rows = self.execute_query(
            """SELECT f.id, f.customer_id, f.name, f.size, f.capacity, f.model,
                      f.created_at, c.name AS customer_name
               FROM fridge f
               JOIN customers c ON f.customer_id = c.id
               WHERE f.is_active = TRUE ORDER BY f.created_at DESC""",
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    def get_fridge_by_id(self, fridge_id) -> Optional[Dict]:
        rows = self.execute_query(
            """SELECT f.id, f.customer_id, f.name, f.size, f.capacity, f.model,
                      f.created_at, c.name AS customer_name
               FROM fridge f
               JOIN customers c ON f.customer_id = c.id
               WHERE f.id = %s AND f.is_active = TRUE""",
            (fridge_id,),
            fetch=True,
        )
        return self._serialize(rows[0]) if rows else None

    def add_fridge(self, customer_id, name, size, capacity, model) -> bool:
        self.execute_query(
            "INSERT INTO fridge (id, customer_id, name, size, capacity, model) VALUES (%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), customer_id, name, size, capacity, model),
        )
        return True

    def update_fridge(
        self, fridge_id, customer_id, name, size, capacity, model
    ) -> bool:
        count = self.execute_query(
            "UPDATE fridge SET customer_id=%s, name=%s, size=%s, capacity=%s, model=%s WHERE id=%s",
            (customer_id, name, size, capacity, model, fridge_id),
        )
        return count > 0

    def delete_fridge(self, fridge_id) -> bool:
        count = self.execute_query(
            "UPDATE fridge SET is_active=FALSE WHERE id=%s",
            (fridge_id,),
        )
        return count > 0

    def get_fridges_by_customer(self, customer_id) -> List[Dict]:
        rows = self.execute_query(
            """SELECT id, name, size, capacity, model, created_at
               FROM fridge WHERE customer_id=%s AND is_active=TRUE ORDER BY created_at DESC""",
            (customer_id,),
            fetch=True,
        )
        return [self._serialize(r) for r in rows]

    # ─────────────── Dashboard ───────────────
    def get_dashboard_stats(self) -> Dict:
        try:
            customers = self.execute_query(
                "SELECT COUNT(*) AS c FROM customers WHERE is_active=TRUE", fetch=True
            )
            workers = self.execute_query(
                "SELECT COUNT(*) AS c FROM users WHERE role='worker' AND is_active=TRUE",
                fetch=True,
            )
            sales = self.execute_query("SELECT COUNT(*) AS c FROM sales", fetch=True)
            revenue = self.execute_query(
                "SELECT COALESCE(SUM(total_amount),0) AS c FROM sales", fetch=True
            )
            trucks = self.execute_query(
                "SELECT COUNT(*) AS c FROM trucks WHERE is_active=TRUE", fetch=True
            )
            avail = self.execute_query(
                "SELECT COUNT(*) AS c FROM trucks WHERE status='available' AND is_active=TRUE",
                fetch=True,
            )
            fridges = self.execute_query(
                "SELECT COUNT(*) AS c FROM fridge WHERE is_active=TRUE", fetch=True
            )
            return {
                "total_customers": customers[0]["c"],
                "total_workers": workers[0]["c"],
                "total_sales": sales[0]["c"],
                "total_revenue": float(revenue[0]["c"]),
                "total_trucks": trucks[0]["c"],
                "available_trucks": avail[0]["c"],
                "total_fridges": fridges[0]["c"],
            }
        except Exception as e:
            print(f"❌ Error stats: {e}")
            return {
                "total_customers": 0,
                "total_workers": 0,
                "total_sales": 0,
                "total_revenue": 0.0,
                "total_trucks": 0,
                "available_trucks": 0,
                "total_fridges": 0,
            }

    # ─────────────── Serialización ───────────────
    @staticmethod
    def _serialize(row) -> Dict:
        """Convierte UUIDs, datetimes y Decimals a tipos JSON-serializables."""
        from decimal import Decimal

        d = dict(row)
        for k, v in d.items():
            if isinstance(v, uuid.UUID):
                d[k] = str(v)
            elif isinstance(v, datetime):
                d[k] = v.isoformat()
            elif isinstance(v, Decimal):
                d[k] = float(v)
        return d


# Instancia global
db = DatabaseManager()
