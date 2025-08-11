import psycopg2
from psycopg2.extras import RealDictCursor
import os
from typing import Dict, List, Optional
import hashlib
import uuid
from datetime import datetime
from dotenv import load_dotenv
import barcode
import pytz
from datetime import datetime

# from barcode.writer import ImageWriter
import re

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


class DatabaseManager:
    def __init__(self):
        # Configuración de la base de datos
        self.connection_params = {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT"),
            "database": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }
        self.connection = None
        if self.connect():
            self.create_tables()
            self.insert_initial_data()
        else:
            print("❌ Error conectando a la base de datos, cerrando app.")

    ##################### CONEXIÓN A LA BASE DE DATOS ####################
    def connect(self):
        """Establece conexión con la base de datos"""
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            self.connection.autocommit = True
            print("✅ Conexión exitosa a la base de datos")
            return True
        except Exception as e:
            print(f"❌ Error conectando a la base de datos: {e}")
            return False

    def create_tables(self):
        """Crea las tablas necesarias"""
        tables_sql = """
        -- Tabla de usuarios
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'worker')),
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            phone VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        );

        -- Tabla de clientes
        CREATE TABLE IF NOT EXISTS customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            address TEXT NOT NULL,
            phone VARCHAR(20) NOT NULL,
            email VARCHAR(100),
            price_sale FLOAT DEFAULT 00.0,
            latitude DECIMAL(9,6),
            longitude DECIMAL(10,7),
            barcode VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        );

        -- Tabla de refrigeradores
        CREATE TABLE IF NOT EXISTS fridge (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            size VARCHAR(50) NOT NULL,
            capacity VARCHAR(50) NOT NULL,
            model VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        );

        --Tabla de entregas
        CREATE TABLE IF NOT EXISTS deliveries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            worker_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            bags_delivered INTEGER NOT NULL CHECK (bags_delivered >= 0),
            merma_bags INTEGER NOT NULL CHECK (merma_bags >= 0) DEFAULT 0,
            total_amount DECIMAL(10, 2) NOT NULL CHECK (total_amount >= 0),
            refrigerator_status VARCHAR(50) NOT NULL CHECK (refrigerator_status IN ('exelent',  'good', 'needs_cleaning', 'needs_repair', 'damaged')),
            status_notes TEXT,
            cleaning_performed BOOLEAN NOT NULL DEFAULT FALSE,
            cleaning_notes TEXT,
            evidence_notes TEXT,
            delivery_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Tabla de rutas
        CREATE TABLE IF NOT EXISTS routes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            description TEXT,
            assigned_worker_id UUID REFERENCES users(id),
            status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Tabla de relación ruta-cliente
        CREATE TABLE IF NOT EXISTS route_customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            route_id UUID REFERENCES routes(id) ON DELETE CASCADE,
            customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
            order_sequence INTEGER NOT NULL,
            UNIQUE(route_id, customer_id)
        );

        -- Tabla de productos
        CREATE TABLE IF NOT EXISTS products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            description TEXT,
            price DECIMAL(10, 2) NOT NULL,
            unit VARCHAR(20) DEFAULT 'bag',
            barcode VARCHAR(50) UNIQUE,
            is_active BOOLEAN DEFAULT TRUE
        );

        -- Tabla de ventas
        CREATE TABLE IF NOT EXISTS sales (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID REFERENCES customers(id),
            worker_id UUID REFERENCES users(id),
            route_id UUID REFERENCES routes(id),
            total_amount DECIMAL(10, 2) NOT NULL,
            bags_delivered INTEGER NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Tabla de items de venta
        CREATE TABLE IF NOT EXISTS sale_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sale_id UUID REFERENCES sales(id) ON DELETE CASCADE,
            product_id UUID REFERENCES products(id),
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            subtotal DECIMAL(10, 2) NOT NULL
        );

        -- Tabla de inventario
        CREATE TABLE IF NOT EXISTS inventory (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID REFERENCES products(id),
            quantity INTEGER NOT NULL,
            location VARCHAR(50) DEFAULT 'warehouse',
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, location)
        );

        -- Tabla de camiones
        CREATE TABLE IF NOT EXISTS trucks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            license_plate VARCHAR(20) UNIQUE NOT NULL,
            brand VARCHAR(50) NOT NULL,
            model VARCHAR(50) NOT NULL,
            year INTEGER,
            capacity_kg INTEGER DEFAULT 1000,
            fuel_type VARCHAR(20) DEFAULT 'gasoline' CHECK (fuel_type IN ('gasoline', 'diesel', 'electric')),
            status VARCHAR(20) DEFAULT 'available' CHECK (status IN ('available', 'in_use', 'maintenance', 'out_of_service')),
            assigned_worker_id UUID REFERENCES users(id),
            last_maintenance DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        );

        -- Índices para camiones
        CREATE INDEX IF NOT EXISTS idx_trucks_license_plate ON trucks(license_plate);
        CREATE INDEX IF NOT EXISTS idx_trucks_assigned_worker ON trucks(assigned_worker_id);
        CREATE INDEX IF NOT EXISTS idx_trucks_status ON trucks(status);

        -- Índices para mejorar el rendimiento
        CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at);
        CREATE INDEX IF NOT EXISTS idx_sales_worker_id ON sales(worker_id);
        CREATE INDEX IF NOT EXISTS idx_sales_customer_id ON sales(customer_id);
        CREATE INDEX IF NOT EXISTS idx_route_customers_route_id ON route_customers(route_id);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(tables_sql)
            print("✅ Tablas creadas exitosamente")
        except Exception as e:
            print(f"❌ Error creando tablas: {e}")

    def insert_initial_data(self):
        """Inserta datos iniciales si no existen"""
        try:
            cursor = self.connection.cursor()

            # Verificar si ya existen datos
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]

            if user_count == 0:
                # Hash de contraseñas
                admin_password = self.hash_password("admin123")
                # worker_password = self.hash_password("worker123")

                # Insertar usuarios iniciales
                cursor.execute(
                    """
                    INSERT INTO users (id, username, password_hash, role, name) VALUES 
                    (%s, 'admin', %s, 'admin', 'Administrador')
                """,
                    (
                        str(uuid.uuid4()),
                        admin_password,
                    ),
                )

                print("✅ Datos iniciales insertados")

        except Exception as e:
            print(f"❌ Error insertando datos iniciales: {e}")

    def hash_password(self, password: str) -> str:
        """Hash de contraseña usando SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Autentica un usuario"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            hashed_password = self.hash_password(password)

            cursor.execute(
                """
                SELECT id, username, role, name, email, phone 
                FROM users 
                WHERE username = %s AND password_hash = %s AND is_active = TRUE
            """,
                (username, hashed_password),
            )

            user = cursor.fetchone()
            return dict(user) if user else None

        except Exception as e:
            print(f"❌ Error en autenticación: {e}")
            return None

    ###################### RUTAS #####################
    def get_routes(self) -> List[Dict]:
        """Obtiene todas las rutas activas"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT r.id, r.name, r.description, r.status, 
                       u.name as assigned_worker_name, u.username as assigned_worker_username
                FROM routes r
                LEFT JOIN users u ON r.assigned_worker_id = u.id
                WHERE r.status = 'pending' OR r.status = 'in_progress'
                ORDER BY r.name
            """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error obteniendo rutas: {e}")
            return []

    def get_route_by_id(self, route_id: uuid) -> Optional[Dict]:
        """Obtiene todas las rutas activas"""
        print(f"route_id: {route_id}")
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                f"""
                SELECT name, description, assigned_worker_id, status
                    FROM routes WHERE id = '{route_id}';
            """
            )
            return cursor.fetchall()
        except Exception as e:
            print(f"❌ Error obteniendo ruta: {e}")
            return []

    def add_route(
        self,
        sequence_route: int,
        name: str,
        customer: uuid,
        worker_assign: uuid,
        status: str,
        description: str = None,
    ) -> bool:
        """Agrega una nueva ruta"""
        try:
            now_created = datetime.now()
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO routes (id, name, description,assigned_worker_id, status, created_at) 
                VALUES (%s, %s, %s,%s,%s, %s)
                RETURNING id
            """,
                (
                    str(uuid.uuid4()),
                    name,
                    description,
                    worker_assign,
                    status,
                    now_created,
                ),
            )
            result = cursor.fetchone()
            route_id = result[0]
            cursor.execute(
                """
                INSERT INTO route_customers (id, route_id, customer_id, order_sequence) 
                VALUES (%s, %s, %s, %s)
            """,
                (
                    str(uuid.uuid4()),
                    route_id,
                    customer,
                    sequence_route,
                ),
            )
            return True
        except Exception as e:
            print(f"❌ Error agregando ruta: {e}")
            return False

    def update_route(
        self,
        route_id,
        name: str = None,
        description: str = None,
        assigned_worker_id: uuid = None,
        status: str = None,
    ):
        try:
            if not route_id:
                print(f"❌ Error obteniendo ruta: {route_id}")
                return False

            # Inicializa la lista de columnas a actualizar y los valores
            set_clause = []
            values = []

            # Verifica cada parámetro y agrega a la cláusula de actualización si no es None
            if name is not None:
                set_clause.append("name = %s")
                values.append(name)
            if description is not None:
                set_clause.append("description = %s")
                values.append(description)
            if assigned_worker_id is not None:
                set_clause.append("assigned_worker_id = %s")
                values.append(assigned_worker_id)
            if status is not None:
                set_clause.append("status = %s")
                values.append(status)

            # Si no hay columnas para actualizar, retorna False
            if not set_clause:
                print("❌ No hay datos para actualizar.")
                return False

            # Construye la consulta SQL
            query = f"UPDATE routes SET {', '.join(set_clause)} WHERE id = %s"
            values.append(route_id)  # Agrega el route_id al final de los valores

            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()  # Asegúrate de hacer commit si es necesario
            return True
        except Exception as e:
            print(f"❌ Error actualizando ruta: {e}")
            return False

    def delete_route(self, route_id):
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                f"""
                DELETE FROM routes WHERE id = '{route_id}';
            """
            )
            print("✅ Ruta eliminada exitosamente")
            return True

        except Exception as e:
            print(f"❌ Error obteniendo rutas: {e}")
            return []

    ##################### CLIENTES #####################
    def _generate_barcode(
        self, customer_name: str, address: str, output_folder="barcodes"
    ):
        """
        Genera un código de barras para un cliente basado en sus datos de refrigerador.

        Args:
            customer_name (str): Nombre del cliente (se simplificará)
            address (str):

        Returns:
            str: Nombre del archivo de código de barras generado
        """
        # Preprocesar el nombre del cliente (remover espacios y caracteres especiales)
        clean_name = re.sub(r"[^a-zA-Z0-9]", "", customer_name)[:6].upper()
        clean_address = re.sub(r"[^a-zA-Z0-9]", "", address)[:6].upper()
        # Crear el texto para el código de barras
        barcode_data = f"{clean_name}-{clean_address}"

        # Generar el código (Code128 puede codificar letras y números)
        code = barcode.Code128(barcode_data)
        # Crear directorio si no existe
        # import os
        # os.makedirs(os.getenv("PATH_CUSTOMERS"), exist_ok=True)

        # # Guardar el código como imagen
        # filename = f"{clean_name}_{clean_address}".replace(" ", "_")
        # filepath = os.path.join(output_folder, filename)
        # print(filename)
        # print(filepath)
        # code.save(filepath)
        # print(code)
        return code

    def get_customers(self) -> List[Dict]:
        """Obtiene todos los clientes activos"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT id, name, address, phone, email, latitude, longitude, price_sale 
                FROM customers 
                WHERE is_active = TRUE 
                ORDER BY name
            """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error obteniendo clientes: {e}")
            return []

    def get_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        """Obtiene un cliente por su ID"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT id, name, address, phone, email, latitude, longitude, price_sale 
                FROM customers 
                WHERE id = %s AND is_active = TRUE
            """,
                (customer_id,),
            )
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            print(f"❌ Error obteniendo cliente: {e}")
            return None

    def add_customer(
        self,
        name: str,
        address: str,
        phone: str,
        email: str = None,
        price_sale: float = 0.0,
        latitude: float = 0.0,
        longitude: float = 0.0,
    ) -> bool:
        """Agrega un nuevo cliente"""
        try:
            code_ = self._generate_barcode(customer_name=name, address=address)
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO customers (id, name, address, latitude, longitude, phone, email, price_sale, barcode, is_active) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            """,
                (
                    str(uuid.uuid4()),
                    name,
                    address,
                    latitude,
                    longitude,
                    phone,
                    email,
                    price_sale,
                    str(code_),
                ),
            )
            return True
        except Exception as e:
            print(f"❌ Error agregando cliente: {e}")
            return False

    def update_customer(
        self,
        customer_id: str,
        name: str,
        address: str,
        latitude: float = 0.0,
        longitude: float = 0.0,
        phone: str = None,
        email: str = None,
        price_sale: float = 0.0,
    ) -> bool:
        """Actualiza los datos de un cliente"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE customers 
                SET name = %s, address = %s, latitude = %s, longitude=%s, phone = %s, email = %s, price_sale = %s 
                WHERE id = %s AND is_active = TRUE
            """,
                (
                    name,
                    address,
                    latitude,
                    longitude,
                    phone,
                    email,
                    price_sale,
                    customer_id,
                ),
            )
            return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error actualizando cliente: {e}")
            return False

    def delete_customer(self, customer_id: str) -> bool:
        """Elimina al customer"""
        try:
            cursor = self.connection.cursor()
            print("🔄 Eliminando registros vinculados... ")
            cursor.execute(
                f"""
                DELETE FROM sales
                           WHERE customer_id='{customer_id}';
            """
            )
            print("🔄 Eliminando cliente...")
            cursor.execute(
                f"""
                DELETE FROM customers
                           WHERE id='{customer_id}';
            """
            )
            print("✅ Cliente eliminado exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error eliminando cliente: {e}")
            return False

    ##################### TRABAJADORES #####################
    def get_workers(self) -> List[Dict]:
        """Obtiene todos los trabajadores"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT id, username, name, email, phone, created_at, is_active 
                FROM users 
                WHERE role = 'worker' 
                ORDER BY name
            """
                # AND is_active = TRUE
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error obteniendo trabajadores: {e}")
            return []

    def add_worker(
        self,
        username: str,
        name: str,
        password: str,
        email: str = None,
        phone: str = None,
    ) -> bool:
        """Agrega un nuevo trabajador"""
        try:
            cursor = self.connection.cursor()
            hashed_password = self.hash_password(password)
            cursor.execute(
                """
                INSERT INTO users (id, username, password_hash, role, name, email, phone, is_active) 
                VALUES (%s, %s, %s, 'worker', %s, %s, %s, TRUE)
            """,
                (
                    str(uuid.uuid4()),
                    username,
                    hashed_password,
                    name,
                    email,
                    phone,
                ),
            )
            return True
        except Exception as e:
            print(f"❌ Error agregando trabajador: {e}")
            return False

    def get_worker_by_id(self, worker_id: str) -> Optional[Dict]:
        """Obtiene un trabajador por su nombre de usuario"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT id, username, name, email, phone, is_active 
                FROM users 
                WHERE id = %s AND role = 'worker'
            """,
                (worker_id,),
            )
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            print(f"❌ Error obteniendo trabajador: {e}")
            return None

    def update_worker(
        self,
        worker_id: str,
        username: str,
        name: str,
        email: str = "",
        phone: str = "",
        is_active: bool = True,
    ) -> bool:
        """Actualiza los datos de un trabajador"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE users 
                SET id=%s, username=%s, name=%s, email=%s, phone=%s, is_active=%s 
                WHERE id = %s AND role = 'worker'
            """,
                (worker_id, username, name, email, phone, is_active, worker_id),
            )
            return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error actualizando trabajador: {e}")
            return False

    def delete_worker(self, worker_id: str) -> bool:
        """Elimina a un trabajador"""
        try:
            cursor = self.connection.cursor()
            print("🔄 Eliminando registros vinculados... ")
            cursor.execute(
                f"""
                DELETE FROM sales
                           WHERE worker_id='{worker_id}';
            """
            )
            print("🔄 Eliminando trabajador...")
            cursor.execute(
                f"""
                DELETE FROM users
                           WHERE id='{worker_id}' AND role='worker';
            """
            )
            print("✅ Trabajador eliminado exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error eliminando trabajador: {e}")
            return False

    def get_routes_for_worker(self, worker_id: uuid) -> List[Dict]:
        """Obtiene las rutas asignadas a un trabajador"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
            SELECT 
                r.id AS route_id,
                r.name AS route_name,
                r.description AS route_description,
                r.status AS route_status,
                r.created_at AS creada_en,
                rc.customer_id,
                rc.order_sequence,
                c.address AS customer_address,
                c.phone AS customer_phone,
                c.name AS customer_name
            FROM 
                routes r
            JOIN 
                route_customers rc ON r.id = rc.route_id
            JOIN 
                customers c ON rc.customer_id = c.id
            WHERE 
                r.assigned_worker_id = %s 
                AND r.created_at::date = CURRENT_DATE;
            """,
                (worker_id,),
            )
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            result_dicts = [dict(zip(columns, row)) for row in results]
            return result_dicts
        except Exception as e:
            print(f"❌ Error obteniendo rutas: {e}")
            return []

    def get_customer_by_barcode(self, barcode):
        """Busca un cliente por su código de barras"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT id, name, address, phone, email, price_sale, barcode, latitude, longitude
                FROM customers 
                WHERE barcode = %s AND is_active = TRUE
            """,
                (barcode,),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "address": result[2],
                    "phone": result[3],
                    "email": result[4],
                    "price_sale": result[5] or 0.0,
                    "barcode": result[6],
                    "latitude": result[7],
                    "longitude": result[8],
                }
            return None
        except Exception as e:
            print(f"Error buscando cliente por barcode: {e}")
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
        """Registra un record completo de entrega con todos los pasos"""
        try:
            cursor = self.connection.cursor()

            # Obtener worker_id
            cursor.execute(
                "SELECT id FROM users WHERE username = %s AND role = 'worker'",
                (worker_username,),
            )
            worker_result = cursor.fetchone()
            if not worker_result:
                return False
            worker_id = worker_result[0]
            # Insertar registro de entrega

            # Assuming you have already defined customer_id, worker_id, etc.
            tz = pytz.timezone("America/Mexico_City")
            current_time = datetime.now(tz)

            cursor.execute(
                """
                INSERT INTO deliveries (
                    customer_id, worker_id, bags_delivered, merma_bags, total_amount,
                    refrigerator_status, status_notes, cleaning_performed, cleaning_notes,
                    evidence_notes, delivery_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    customer_id,
                    worker_id,
                    bags_delivered,
                    merma_bags,
                    total_amount,
                    str(refrigerator_status["status"]),
                    str(refrigerator_status["notes"]),
                    cleaning_data["performed"],
                    cleaning_data["notes"],
                    evidence_notes,
                    current_time,
                ),
            )
            # También insertar en la tabla de ventas para compatibilidad
            finally_note = f"Estado de refrigerador:{str(refrigerator_status['notes'])}|Limpieza de refrigerador: {cleaning_data['notes']}|Notas finales: {evidence_notes}"
            cursor.execute(
                """
                INSERT INTO sales (customer_id, worker_id, route_id, bags_delivered, total_amount, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    customer_id,
                    worker_id,
                    route_id,
                    bags_delivered,
                    total_amount,
                    finally_note,
                ),
            )
            customer = self.get_customer_by_id(customer_id=customer_id)
            if self.add_sale(
                customer_id=customer_id,
                worker_username=worker_id,
                bags_delivered=bags_delivered,
                route_id=route_id,
                unit_price=customer.get("price_sale", 0),
            ):
                print(f"✅ Venta agregada correctamente.")
            self.connection.commit()
            return True

        except Exception as e:
            print(f"Error registrando entrega: {e}")
            self.connection.rollback()
            return False

    def create_deliveries_table(self):
        """Crea la tabla de entregas si no existe"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    bags_delivered INTEGER NOT NULL,
                    merma_bags INTEGER DEFAULT 0,
                    total_amount REAL NOT NULL,
                    refrigerator_status TEXT,
                    cleaning_performed BOOLEAN DEFAULT 0,
                    cleaning_notes TEXT,
                    evidence_notes TEXT,
                    delivery_date DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers (id),
                    FOREIGN KEY (worker_id) REFERENCES workers (id)
                )
            """
            )

            # Agregar columna barcode a customers si no existe
            cursor.execute("PRAGMA table_info(customers)")
            columns = [column[1] for column in cursor.fetchall()]

            if "barcode" not in columns:
                cursor.execute("ALTER TABLE customers ADD COLUMN barcode TEXT")
                # Generar códigos de barras automáticos para clientes existentes
                cursor.execute("SELECT id FROM customers")
                customers = cursor.fetchall()
                for customer in customers:
                    barcode = f"ICE{customer[0]:06d}"
                    cursor.execute(
                        "UPDATE customers SET barcode = ? WHERE id = ?",
                        (barcode, customer[0]),
                    )

            self.connection.commit()
            return True

        except Exception as e:
            print(f"Error creando tabla de entregas: {e}")
            return False

    ###################### REFRIGERADOR ######################
    def create_fridge_table(self):
        """Crea la tabla de refrigeradores si no existe"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS fridge (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    size TEXT NOT NULL,
                    capacity TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (customer_id) REFERENCES customers (id)
                )
            """
            )
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error creando tabla de refrigeradores: {e}")
            return False

    def add_fridge(self, customer_id, name, size, capacity, model):
        """Agrega un nuevo refrigerador"""
        try:
            cursor = self.connection.cursor()
            fridge_id = str(uuid.uuid4())

            cursor.execute(
                """
                INSERT INTO fridge (id, customer_id, name, size, capacity, model)
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (fridge_id, customer_id, name, size, capacity, model),
            )

            self.connection.commit()
            return True
        except Exception as e:
            print(f"Error agregando refrigerador: {e}")
            return False

    def get_fridges(self):
        """Obtiene todos los refrigeradores activos con información del cliente"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT f.id, f.customer_id, f.name, f.size, f.capacity, f.model, 
                       f.created_at, c.name as customer_name
                FROM fridge f
                JOIN customers c ON f.customer_id = c.id
                WHERE f.is_active = TRUE
                ORDER BY f.created_at DESC
            """
            )

            fridges = []
            for row in cursor.fetchall():
                fridges.append(
                    {
                        "id": row[0],
                        "customer_id": row[1],
                        "name": row[2],
                        "size": row[3],
                        "capacity": row[4],
                        "model": row[5],
                        "created_at": row[6],
                        "customer_name": row[7],
                    }
                )
            return fridges
        except Exception as e:
            print(f"Error obteniendo refrigeradores: {e}")
            return []

    def get_fridge_by_id(self, fridge_id):
        """Obtiene un refrigerador por su ID"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT f.id, f.customer_id, f.name, f.size, f.capacity, f.model, 
                       f.created_at, c.name as customer_name
                FROM fridge f
                JOIN customers c ON f.customer_id = c.id
                WHERE f.id = %s AND f.is_active = TRUE
            """,
                (fridge_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "customer_id": row[1],
                    "name": row[2],
                    "size": row[3],
                    "capacity": row[4],
                    "model": row[5],
                    "created_at": row[6],
                    "customer_name": row[7],
                }
            return None
        except Exception as e:
            print(f"Error obteniendo refrigerador: {e}")
            return None

    def update_fridge(self, fridge_id, customer_id, name, size, capacity, model):
        """Actualiza un refrigerador"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE fridge 
                SET customer_id = %s, name = %s, size = %s, capacity = %s, model = %s
                WHERE id = %s
            """,
                (customer_id, name, size, capacity, model, fridge_id),
            )

            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error actualizando refrigerador: {e}")
            return False

    def delete_fridge(self, fridge_id):
        """Elimina un refrigerador (eliminación lógica)"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE fridge SET is_active = FALSE WHERE id = %s
            """,
                (fridge_id,),
            )

            self.connection.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error eliminando refrigerador: {e}")
            return False

    def get_fridges_by_customer(self, customer_id):
        """Obtiene todos los refrigeradores de un cliente específico"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT id, name, size, capacity, model, created_at
                FROM fridge
                WHERE customer_id = %s AND is_active = TRUE
                ORDER BY created_at DESC
            """,
                (customer_id,),
            )

            fridges = []
            for row in cursor.fetchall():
                fridges.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "size": row[2],
                        "capacity": row[3],
                        "model": row[4],
                        "created_at": row[5],
                    }
                )
            return fridges
        except Exception as e:
            print(f"Error obteniendo refrigeradores del cliente: {e}")
            return []

    def get_deliveries_by_fridge(self, fridge_id):
        """Obtiene el historial de entregas para un refrigerador específico"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT d.id, d.bags_delivered, d.total_amount, d.delivery_date,
                       w.name as worker_name, c.name as customer_name
                FROM deliveries d
                JOIN users w ON d.worker_id = w.id
                JOIN customers c ON d.customer_id = c.id
                JOIN fridge f ON d.customer_id = f.customer_id
                WHERE f.id = %s
                ORDER BY d.delivery_date DESC
                LIMIT 10
            """,
                (fridge_id,),
            )

            deliveries = []
            for row in cursor.fetchall():
                deliveries.append(
                    {
                        "id": row[0],
                        "bags_delivered": row[1],
                        "total_amount": row[2],
                        "delivery_date": row[3],
                        "worker_name": row[4],
                        "customer_name": row[5],
                    }
                )
            return deliveries
        except Exception as e:
            print(f"Error obteniendo entregas del refrigerador: {e}")
            return []

    def get_dashboard_stats(self):
        """Obtiene estadísticas para el dashboard incluyendo refrigeradores"""
        try:
            cursor = self.connection.cursor()

            # Estadísticas existentes
            cursor.execute("SELECT COUNT(*) FROM customers WHERE is_active = TRUE")
            total_customers = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM workers WHERE is_active = TRUE")
            total_workers = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trucks WHERE is_active = TRUE")
            total_trucks = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM trucks WHERE status = 'available' AND is_active = TRUE"
            )
            available_trucks = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sales")
            total_sales = cursor.fetchone()[0]

            cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales")
            total_revenue = cursor.fetchone()[0]

            # Nueva estadística de refrigeradores
            cursor.execute("SELECT COUNT(*) FROM fridge WHERE is_active = TRUE")
            total_fridges = cursor.fetchone()[0]

            return {
                "total_customers": total_customers,
                "total_workers": total_workers,
                "total_trucks": total_trucks,
                "available_trucks": available_trucks,
                "total_sales": total_sales,
                "total_revenue": total_revenue,
                "total_fridges": total_fridges,  # Agregar esta línea
            }
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            return {
                "total_customers": 0,
                "total_workers": 0,
                "total_trucks": 0,
                "available_trucks": 0,
                "total_sales": 0,
                "total_revenue": 0,
                "total_fridges": 0,
            }

    ###################### VENTAS #####################
    def add_sale(
        self,
        customer_id: str,
        worker_username: str,
        bags_delivered: int,
        unit_price: float = 15.0,
        route_id: str = None,
    ) -> bool:
        """Registra una nueva venta"""
        try:
            cursor = self.connection.cursor()

            # Obtener worker_id
            cursor.execute(
                "SELECT id FROM users WHERE username = %s", (worker_username,)
            )
            worker_result = cursor.fetchone()
            if not worker_result:
                return False
            worker_id = worker_result[0]

            # Obtener product_id (asumimos el primer producto de hielo)
            cursor.execute("SELECT id FROM products WHERE barcode = 'ICE001' LIMIT 1")
            product_result = cursor.fetchone()
            if not product_result:
                return False
            product_id = product_result[0]

            total_amount = bags_delivered * unit_price
            sale_id = str(uuid.uuid4())

            # Insertar venta
            cursor.execute(
                """
                INSERT INTO sales (id, customer_id, worker_id, route_id, total_amount,bags_delivered) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    sale_id,
                    customer_id,
                    worker_id,
                    route_id,
                    total_amount,
                    bags_delivered,
                ),
            )

            # Insertar item de venta
            cursor.execute(
                """
                INSERT INTO sale_items (id, sale_id, product_id, quantity, unit_price, subtotal) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """,
                (
                    str(uuid.uuid4()),
                    sale_id,
                    product_id,
                    bags_delivered,
                    unit_price,
                    total_amount,
                ),
            )

            return True
        except Exception as e:
            print(f"❌ Error registrando venta: {e}")
            return False

    def get_sales(self, limit: int = 50) -> List[Dict]:
        """Obtiene las ventas más recientes"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT s.id, s.total_amount, s.bags_delivered, s.created_at,
                       c.name as customer_name, c.address as customer_address,
                       u.name as worker_name,
                       si.quantity as bag_delivered
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                JOIN users u ON s.worker_id = u.id
                LEFT JOIN sale_items si ON s.id = si.sale_id
                ORDER BY s.created_at DESC
                LIMIT %s
            """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error obteniendo ventas: {e}")
            return []

    def get_sales_by_period(self, period: str) -> List[Dict]:
        """Obtiene ventas por período (weekly, monthly)"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)

            if period == "weekly":
                date_filter = "s.created_at >= CURRENT_DATE - INTERVAL '7 days'"
            elif period == "monthly":
                date_filter = "s.created_at >= CURRENT_DATE - INTERVAL '30 days'"
            else:
                date_filter = "TRUE"

            cursor.execute(
                f"""
                SELECT s.id, s.total_amount, s.created_at,
                       c.name as customer_name,
                       u.name as worker_name,
                       si.quantity as bags_delivered
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                JOIN users u ON s.worker_id = u.id
                LEFT JOIN sale_items si ON s.id = si.sale_id
                WHERE {date_filter}
                ORDER BY s.created_at DESC
            """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error obteniendo ventas por período: {e}")
            return []

    ####################### CAMIONES #####################
    def get_dashboard_stats(self) -> Dict:
        """Obtiene estadísticas para el dashboard"""
        try:
            cursor = self.connection.cursor()

            # Total clientes
            cursor.execute("SELECT COUNT(*) FROM customers WHERE is_active = TRUE")
            total_customers = cursor.fetchone()[0]

            # Total trabajadores
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'worker' AND is_active = TRUE"
            )
            total_workers = cursor.fetchone()[0]

            # Total ventas
            cursor.execute("SELECT COUNT(*) FROM sales")
            total_sales = cursor.fetchone()[0]

            # Ingresos totales
            cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales")
            total_revenue = cursor.fetchone()[0]

            # Total camiones
            cursor.execute("SELECT COUNT(*) FROM trucks WHERE is_active = TRUE")
            total_trucks = cursor.fetchone()[0]

            # Camiones disponibles
            cursor.execute(
                "SELECT COUNT(*) FROM trucks WHERE status = 'available' AND is_active = TRUE"
            )
            available_trucks = cursor.fetchone()[0]

            return {
                "total_customers": total_customers,
                "total_workers": total_workers,
                "total_sales": total_sales,
                "total_revenue": float(total_revenue),
                "total_trucks": total_trucks,
                "available_trucks": available_trucks,
            }
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            return {
                "total_customers": 0,
                "total_workers": 0,
                "total_sales": 0,
                "total_revenue": 0.0,
            }

    def get_trucks(self) -> List[Dict]:
        """Obtiene todos los camiones"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT t.id, t.license_plate, t.brand, t.model, t.year, 
                        t.capacity_kg, t.fuel_type, t.status, t.last_maintenance, 
                        t.notes, t.created_at,
                        u.name as assigned_worker_name, u.username as assigned_worker_username
            FROM trucks t
            LEFT JOIN users u ON t.assigned_worker_id = u.id
            WHERE t.is_active = TRUE
            ORDER BY t.license_plate
        """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error obteniendo camiones: {e}")
            return []

    def add_truck(
        self,
        license_plate: str,
        brand: str,
        model: str,
        year: int = None,
        capacity_kg: int = 1000,
        fuel_type: str = "gasoline",
        notes: str = None,
    ) -> bool:
        """Agrega un nuevo camión"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO trucks (id, license_plate, brand, model, year, capacity_kg, fuel_type, notes) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
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
        except Exception as e:
            print(f"❌ Error agregando camión: {e}")
            return False

    def assign_truck_to_worker(self, truck_id: str, worker_id: str) -> bool:
        """Asigna un camión a un trabajador"""
        try:
            cursor = self.connection.cursor()

            # Primero, liberar cualquier camión que tenga asignado el trabajador
            cursor.execute(
                """
                UPDATE trucks SET assigned_worker_id = NULL, status = 'available' 
                WHERE assigned_worker_id = %s
            """,
                (worker_id,),
            )

            # Luego, asignar el nuevo camión
            cursor.execute(
                """
                UPDATE trucks SET assigned_worker_id = %s, status = 'in_use' 
                WHERE id = %s AND status = 'available'
            """,
                (worker_id, truck_id),
            )

            return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error asignando camión: {e}")
            return False

    def unassign_truck(self, truck_id: str) -> bool:
        """Desasigna un camión de un trabajador"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE trucks SET assigned_worker_id = NULL, status = 'available' 
                WHERE id = %s
            """,
                (truck_id,),
            )
            return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error desasignando camión: {e}")
            return False

    def get_truck_by_worker(self, worker_username: str) -> Optional[Dict]:
        """Obtiene el camión asignado a un trabajador"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT t.id, t.license_plate, t.brand, t.model, t.year, 
                       t.capacity_kg, t.fuel_type, t.status, t.last_maintenance, t.notes
            FROM trucks t
            JOIN users u ON t.assigned_worker_id = u.id
            WHERE u.username = %s AND t.is_active = TRUE
        """,
                (worker_username,),
            )

            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            print(f"❌ Error obteniendo camión del trabajador: {e}")
            return None

    def update_truck_status(
        self, truck_id: str, status: str, notes: str = None
    ) -> bool:
        """Actualiza el estado de un camión"""
        try:
            cursor = self.connection.cursor()
            if notes:
                cursor.execute(
                    """
                    UPDATE trucks SET status = %s, notes = %s 
                    WHERE id = %s
                """,
                    (status, notes, truck_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE trucks SET status = %s 
                    WHERE id = %s
                """,
                    (status, truck_id),
                )
            return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error actualizando estado del camión: {e}")
            return False

    def get_available_trucks(self) -> List[Dict]:
        """Obtiene camiones disponibles para asignar"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute(
                """
                SELECT id, license_plate, brand, model, capacity_kg
            FROM trucks 
            WHERE status = 'available' AND is_active = TRUE
            ORDER BY license_plate
        """
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error obteniendo camiones disponibles: {e}")
            return []

    ######################## CIERRE DE CONEXIÓN #####################
    def close(self):
        """Cierra la conexión a la base de datos"""
        if self.connection:
            self.connection.close()
            print("🔌 Conexión a la base de datos cerrada")


print("🔄 Inicializando gestor de base de datos...")
# Instancia global del gestor de base de datos
db_manager = DatabaseManager()
