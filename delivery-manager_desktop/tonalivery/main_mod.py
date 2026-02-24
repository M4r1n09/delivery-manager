import flet as ft
import os
import subprocess
import sys
from dotenv import load_dotenv
from database import db_manager
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Función para determinar la ruta base cuando se ejecuta como script o como ejecutable
def get_base_path():
    if getattr(sys, 'frozen', False):
        # Si se está ejecutando como ejecutable compilado
        return os.path.dirname(sys.executable)
    else:
        # Si se está ejecutando como script .py
        return os.path.dirname(os.path.abspath(__file__))

# Cargar variables de entorno - buscar en múltiples ubicaciones
env_paths = [
    # 1. Mismo directorio que el ejecutable o script
    os.path.join(get_base_path(), ".env"),
    
    # 2. Directorio padre (estructura original)
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
    
    # 3. Ruta absoluta específica (como respaldo)
    "C:\\Users\\marin\\Documents\\PROJECTS\\app_desktop\\.env"
]

# Intentar cargar .env desde las diferentes rutas
env_loaded = False
for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        print(f"Cargando variables de entorno desde: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    print("ADVERTENCIA: No se pudo encontrar el archivo .env en ninguna ubicación.")
    print(f"Rutas buscadas: {env_paths}")


class LoginView:
    def __init__(self, page: ft.Page, on_login_success):
        self.page = page
        self.on_login_success = on_login_success
        self.username_field = ft.TextField(
            label="Usuario", width=300, prefix_icon=ft.Icons.PERSON
        )
        self.password_field = ft.TextField(
            label="Contraseña", password=True, width=300, prefix_icon=ft.Icons.LOCK
        )

    def login_clicked(self, e):
        user = db_manager.authenticate(
            self.username_field.value, self.password_field.value
        )
        if user:
            self.on_login_success(user)
        else:
            snack_bar = ft.SnackBar(
                content=ft.Text("Credenciales incorrectas"), bgcolor=ft.Colors.RED
            )
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()

    def build(self):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=50),
                    ft.Icon(ft.Icons.AC_UNIT, size=80, color=ft.Colors.BLUE),
                    ft.Text("Ice Delivery App", size=32, weight=ft.FontWeight.BOLD),
                    ft.Container(height=30),
                    self.username_field,
                    self.password_field,
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Iniciar Sesión",
                        on_click=self.login_clicked,
                        width=300,
                        height=50,
                    ),
                    ft.Container(height=20),
                    ft.Text(
                        "Demo: admin/admin123",
                        size=12,
                        color=ft.Colors.GREY,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )


# Resto del código original a partir de aquí...
class WorkerDashboard:
    def __init__(self, page: ft.Page, user: Dict, on_logout):
        self.page = page
        self.user = user
        self.on_logout = on_logout
        self.current_view = "routes"
        # Variable para almacenar el route_id actual
        self.current_route_id = None

    def show_routes(self, e=None):
        self.current_view = "routes"
        # Limpiar route_id cuando volvemos a rutas
        self.current_route_id = None
        self.update_content()

    def show_map(self, e=None):
        self.current_view = "map"
        self.update_content()

    def show_scanner(self, route_id=None):
        """Muestra el scanner, opcionalmente con un route_id específico"""
        self.current_view = "scanner"
        if route_id:
            self.current_route_id = route_id
            print(f"🔄 Scanner iniciado para ruta ID: {route_id}")
        self.update_content()

    def process_barcode_scan(self, barcode_value):
        """Procesa el código de barras escaneado o ingresado manualmente"""
        if not barcode_value or not barcode_value.strip():
            self.show_error_message("Por favor ingresa un código válido")
            return

        # Buscar cliente por código de barras en la base de datos
        customer = db_manager.get_customer_by_barcode(barcode_value.strip())

        if customer:
            # Inicializar el proceso de entrega
            self.start_delivery_process(customer)
        else:
            self.show_error_message(
                f"No se encontró cliente con el código: {barcode_value}"
            )

    def start_delivery_process(self, customer):
        """Inicia el proceso de entrega con 3 pasos secuenciales"""
        self.delivery_customer = customer
        self.delivery_step = 1
        self.delivery_data = {
            "refrigerator_status": None,
            "cleaning_data": None,
            "merma_bags": 0,
            "bags_delivered": 0,
            "evidence_photos": [],
        }
        self.show_delivery_process()

    def show_delivery_process(self):
        """Muestra la vista del proceso de entrega según el paso actual"""
        self.current_view = "delivery_process"
        self.update_content()

    def show_error_message(self, message):
        """Muestra mensaje de error"""
        snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED)
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def show_success_message(self, message):
        """Muestra mensaje de éxito"""
        snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.GREEN)
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def complete_step_1(self, refrigerator_status, notes=""):
        """Completa el paso 1: Estado del refrigerador"""
        self.delivery_data["refrigerator_status"] = {
            "status": refrigerator_status,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        }
        self.delivery_step = 2
        self.show_delivery_process()

    def complete_step_2(self, cleaning_performed, cleaning_notes="", merma_bags=0):
        """Completa el paso 2: Limpieza del refrigerador"""
        self.delivery_data["cleaning_data"] = {
            "performed": cleaning_performed,
            "notes": cleaning_notes,
            "timestamp": datetime.now().isoformat(),
        }
        self.delivery_data["merma_bags"] = int(merma_bags) if merma_bags else 0
        self.delivery_step = 3
        self.show_delivery_process()

    def complete_step_3(self, bags_delivered, evidence_notes=""):
        """Completa el paso 3: Evidencia de llenado y genera ticket"""
        self.delivery_data["bags_delivered"] = int(bags_delivered)
        self.delivery_data["evidence_notes"] = evidence_notes

        # Calcular total a pagar
        price_per_bag = float(self.delivery_customer.get("price_sale", 0))
        total_amount = self.delivery_data["bags_delivered"] * price_per_bag

        # Registrar la venta en la base de datos incluyendo route_id
        success = db_manager.add_delivery_record(
            customer_id=self.delivery_customer["id"],
            worker_username=self.user["username"],
            bags_delivered=self.delivery_data["bags_delivered"],
            merma_bags=self.delivery_data["merma_bags"],
            total_amount=total_amount,
            refrigerator_status=self.delivery_data["refrigerator_status"],
            cleaning_data=self.delivery_data["cleaning_data"],
            evidence_notes=evidence_notes,
            route_id=self.current_route_id,  # Incluir route_id aquí
        )

        if success:
            # Si hay route_id, actualizar el estado de la ruta
            if self.current_route_id:
                db_manager.update_route(
                    route_id=self.current_route_id, status="completed"
                )
                print(f"✅ Ruta {self.current_route_id} marcada como completada")

            # Generar y mostrar ticket
            self.generate_delivery_ticket(total_amount)
            self.show_success_message("Entrega registrada exitosamente")
            self.show_routes()
        else:
            self.show_error_message("Error al registrar la entrega")

# Continúa con el resto del código original...

# Función principal para iniciar la aplicación
def main(page: ft.Page):
    # Resto de tu código de inicialización de la aplicación...
    page.title = "TonaliVery - Ice Delivery App"
    # Y así sucesivamente...

# Punto de entrada del programa
if __name__ == "__main__":
    ft.app(target=main)
