import flet as ft
import os
import subprocess
from dotenv import load_dotenv
from database import db_manager
from typing import Dict, List, Optional
from datetime import datetime

# Cargar variables de entorno
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


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
                        "Demo: admin/admin123 o worker1/worker123",
                        size=12,
                        color=ft.Colors.GREY,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )


class WorkerDashboard:
    def __init__(self, page: ft.Page, user: Dict, on_logout):
        self.page = page
        self.user = user
        # Solicitar permisos de cámara y habilitar acceso a la cámara
        if hasattr(self.page, "request_permissions"):
            self.page.request_permissions(["camera"])
        if hasattr(self.page, "CAMERA"):
            self.page.CAMERA = True  # Habilitar acceso a la cámara
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

    def generate_delivery_ticket(self, total_amount):
        """Genera el ticket de entrega"""
        ticket_data = {
            "customer_name": self.delivery_customer["name"],
            "customer_address": self.delivery_customer["address"],
            "bags_delivered": self.delivery_data["bags_delivered"],
            "merma_bags": self.delivery_data["merma_bags"],
            "price_per_bag": self.delivery_customer.get("price_sale", 0),
            "total_amount": total_amount,
            "worker_name": self.user["name"],
            "delivery_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "route_id": self.current_route_id,  # Incluir route_id en el ticket
        }

        # Mostrar ticket en un diálogo
        self.show_ticket_dialog(ticket_data)

    def show_ticket_dialog(self, ticket_data):
        """Muestra el ticket generado en un diálogo"""

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        ticket_content = ft.Column(
            [
                ft.Text(
                    "🧊 TICKET DE ENTREGA",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Divider(),
                ft.Text(f"Cliente: {ticket_data['customer_name']}", size=14),
                ft.Text(f"Dirección: {ticket_data['customer_address']}", size=12),
                ft.Text(f"Fecha: {ticket_data['delivery_date']}", size=12),
                ft.Text(f"Trabajador: {ticket_data['worker_name']}", size=12),
                # Mostrar información de la ruta si existe
                (
                    ft.Text(
                        f"Ruta ID: {ticket_data['route_id'] or 'Entrega directa'}",
                        size=12,
                        color=ft.Colors.BLUE,
                    )
                    if ticket_data.get("route_id")
                    else ft.Container()
                ),
                ft.Divider(),
                ft.Text(
                    f"Bolsas entregadas: {ticket_data['bags_delivered']}",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(f"Merma: {ticket_data['merma_bags']} bolsas", size=12),
                ft.Text(
                    f"Precio por bolsa: ${ticket_data['price_per_bag']:.2f}", size=12
                ),
                ft.Divider(),
                ft.Text(
                    f"TOTAL A PAGAR: ${ticket_data['total_amount']:.2f}",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.GREEN,
                ),
            ],
            spacing=5,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Ticket Generado"),
            content=ticket_content,
            actions=[
                ft.TextButton(
                    "Imprimir", on_click=lambda e: self.print_ticket(ticket_data)
                ),
                ft.TextButton("Cerrar", on_click=close_dialog),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # def print_ticket(self, ticket_data):
    #     """Simula la impresión del ticket"""
    #     self.show_success_message("Ticket enviado a impresora")

    # def show_tickets(self, e=None):
    #     self.current_view = "tickets"
    #     self.update_content()

    def show_truck(self, e=None):
        self.current_view = "truck"
        self.update_content()

    def simulate_barcode_scan(self, e):
        barcode = "ICE001234"
        bags_count = 10
        snack_bar = ft.SnackBar(
            content=ft.Text(f"Código escaneado: {barcode} - {bags_count} bolsas")
        )
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def use_camera(self, e):
        # Solicitar permiso para usar la cámara (compatible con desktop y móvil)
        if hasattr(self.page, "request_permissions"):
            self.page.request_permissions(["camera"])

        # Verificar si la cámara está disponible y el permiso fue concedido
        if hasattr(self.page, "CAMERA") and getattr(self.page, "CAMERA", False):
            self.page.camera = True
            self.page.update()

            # Mostrar información de la cámara si está disponible
            camera_info = getattr(self.page, "camera_info", None)
            if camera_info:
                info_text = f"Cámara: {camera_info.get('name', 'Desconocida')}"
            else:
                info_text = "Cámara lista para escanear"
                snack_bar = ft.SnackBar(
                    content=ft.Text(
                        f"{info_text}. Apunta al código de barras para escanear."
                    )
                )
        else:
            snack_bar = ft.SnackBar(
                content=ft.Text("Permiso de cámara no concedido o no disponible"),
                bgcolor=ft.Colors.RED,
            )
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def deliver_to_customer(self, customer_id: str):
        customers = db_manager.get_customers()
        customer = next((c for c in customers if c["id"] == customer_id), None)

        if not customer:
            return

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_delivery_dialog(e):
            bags = int(bags_field.value) if bags_field.value.isdigit() else 0
            if bags > 0:
                # Registrar venta en la base de datos
                success = db_manager.add_sale(
                    customer_id=customer_id,
                    worker_username=self.user["username"],
                    bags_delivered=bags,
                )

                dialog.open = False

                if success:
                    snack_bar = ft.SnackBar(
                        content=ft.Text(
                            f"Entrega registrada: {bags} bolsas a {customer['name']}"
                        ),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error registrando la entrega"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        bags_field = ft.TextField(
            label="Número de bolsas", width=200, keyboard_type=ft.KeyboardType.NUMBER
        )

        dialog = ft.AlertDialog(
            title=ft.Text(f"Entrega a {customer['name']}"),
            content=ft.Column(
                [
                    ft.Text(f"Dirección: {customer['address']}"),
                    ft.Container(height=10),
                    bags_field,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Confirmar", on_click=confirm_delivery_dialog),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def update_content(self):
        content = ft.Container()

        if self.current_view == "routes":
            routes = db_manager.get_routes_for_worker(worker_id=self.user["id"])
            routes_list_pending = []
            routes_list_completed = []
            # print(f"🔄 Rutas obtenidas: {routes}")

            # Contar cuántas rutas hay
            num_routes = len(routes)

            for route in routes:
                customers_info = []

                # Verificar si la ruta está completada
                if route["route_status"] == "completed":
                    routes_list_completed.append(
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.STORE),
                            title=ft.Text(
                                route["customer_name"],
                                color=ft.Colors.GREEN,  # Color verde para el texto
                            ),
                            subtitle=ft.Text(f"Estado: {route['route_status']}"),
                            enable_feedback=True,
                        )
                    )
                    continue  # Saltar al siguiente ciclo si la ruta está completada

                # Agregar información del cliente para rutas pendientes
                customers_info.append(
                    ft.ListTile(
                        title=ft.Text(
                            route["route_name"]
                        ),  # Asegúrate de que esto sea un control
                        subtitle=ft.Text(f"Estado: {route['route_status']}"),
                        enable_feedback=True,
                    )
                )

                # Agregar la expansión de la ruta pendiente
                routes_list_pending.append(
                    ft.ExpansionTile(
                        leading=ft.Icon(ft.Icons.LOCAL_SHIPPING),
                        title=ft.Text(
                            route["customer_name"]
                        ),  # Asegúrate de que esto sea un control
                        subtitle=ft.Text(
                            route["customer_address"]
                        ),  # Asegúrate de que esto sea un control
                        controls=[
                            *customers_info,
                            ft.ElevatedButton(
                                "Entregar pedido",
                                on_click=lambda e, rid=route[
                                    "route_id"
                                ]: self.show_scanner(
                                    rid
                                ),  # Pasar route_id correctamente
                                bgcolor=ft.Colors.GREEN,
                                color=ft.Colors.WHITE,
                                width=200,
                            ),
                        ],
                    )
                )

            # Función para actualizar el estado de la ruta
            def update_route_status(route_id, new_status):
                # Lógica para actualizar el estado de la ruta en la base de datos
                # ...

                # Después de actualizar, verifica si hay rutas completadas
                for route in routes:
                    if route["id"] == route_id:
                        route["route_status"] = (
                            new_status  # Actualiza el estado en la lista
                        )
                        break

                # Actualiza la interfaz de usuario si es necesario
                # Aquí puedes volver a construir la lista de rutas o actualizar el estado de los botones

            content = ft.Column(
                [
                    ft.Text("Mis Rutas Entregadas", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=20),
                    *(
                        routes_list_completed
                        if routes_list_completed
                        else [ft.Text("No hay rutas completadas")]
                    ),
                    ft.Text(
                        "Mis Rutas de Pendientes", size=24, weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(height=20),
                    *(
                        routes_list_pending
                        if routes_list_pending
                        else [ft.Text("No hay rutas asignadas")]
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "map":
            content = ft.Column(
                [
                    ft.Text("Mapa de Rutas", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=20),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.MAP, size=100, color=ft.Colors.BLUE),
                                ft.Text("Mapa interactivo de rutas"),
                                ft.Text("(Integración con Google Maps/OpenStreetMap)"),
                                ft.ElevatedButton(
                                    "Navegar a siguiente cliente",
                                    on_click=lambda e: None,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        height=400,
                        border=ft.border.all(1, ft.Colors.GREY),
                        border_radius=10,
                        alignment=ft.alignment.center,
                    ),
                ]
            )

        elif self.current_view == "scanner":
            # Escáner de código de barras mejorado
            manual_code_field = ft.TextField(
                label="Ingrese el código de barras",
                width=350,
                prefix_icon=ft.Icons.KEYBOARD,
                on_submit=lambda e: self.process_barcode_scan(e.control.value),
            )

            def on_camera_scan(e):
                # Simular escaneo por cámara (aquí integrarías la cámara real)
                simulated_barcode = (
                    "ICE001234"  # En producción, esto vendría de la cámara
                )
                self.process_barcode_scan(simulated_barcode)

            def on_manual_submit(e):
                self.process_barcode_scan(manual_code_field.value)

            # Mostrar información de la ruta actual si existe
            route_info = ft.Container()
            if self.current_route_id:
                route_info = ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                f"📍 Entrega para Ruta ID: {self.current_route_id}",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLUE,
                            ),
                            ft.Text(
                                "Esta entrega se asociará automáticamente a la ruta seleccionada",
                                size=12,
                                color=ft.Colors.GREY_700,
                            ),
                        ]
                    ),
                    padding=15,
                    bgcolor=ft.Colors.BLUE_50,
                    border_radius=10,
                    margin=ft.margin.only(bottom=20),
                )

            content = ft.Column(
                [
                    ft.Text(
                        "Escáner de Código de Barras",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(height=20),
                    route_info,  # Mostrar información de la ruta
                    # Opción 1: Escaneo por cámara
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.QR_CODE_SCANNER,
                                    size=80,
                                    color=ft.Colors.GREEN,
                                ),
                                ft.Text(
                                    "Opción 1: Escanear con Cámara",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.ElevatedButton(
                                    "Activar Cámara",
                                    on_click=on_camera_scan,
                                    bgcolor=ft.Colors.GREEN,
                                    color=ft.Colors.WHITE,
                                    width=200,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=20,
                        border=ft.border.all(2, ft.Colors.GREEN),
                        border_radius=10,
                        margin=ft.margin.only(bottom=20),
                    ),
                    # Opción 2: Ingreso manual
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.KEYBOARD, size=60, color=ft.Colors.BLUE
                                ),
                                ft.Text(
                                    "Opción 2: Ingreso Manual",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                manual_code_field,
                                ft.ElevatedButton(
                                    "Buscar Cliente",
                                    on_click=on_manual_submit,
                                    bgcolor=ft.Colors.BLUE,
                                    color=ft.Colors.WHITE,
                                    width=200,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=20,
                        border=ft.border.all(2, ft.Colors.BLUE),
                        border_radius=10,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "tickets":
            content = ft.Column(
                [
                    ft.Text("Generar Tickets", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=20),
                    ft.Text("Selecciona cliente y cantidad de bolsas:"),
                    ft.Container(height=10),
                    self.build_ticket_form(),
                ]
            )

        elif self.current_view == "truck":
            truck = db_manager.get_truck_by_worker(self.user["username"])

            if truck:
                content = ft.Column(
                    [
                        ft.Text(
                            "Mi Camión Asignado", size=24, weight=ft.FontWeight.BOLD
                        ),
                        ft.Container(height=20),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.LOCAL_SHIPPING,
                                                size=60,
                                                color=ft.Colors.BLUE,
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Text(
                                                        f"{truck['brand']} {truck['model']}",
                                                        size=20,
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                    ft.Text(
                                                        f"Placa: {truck['license_plate']}",
                                                        size=16,
                                                    ),
                                                    ft.Text(
                                                        f"Año: {truck['year'] or 'N/A'}",
                                                        size=14,
                                                        color=ft.Colors.GREY_700,
                                                    ),
                                                ],
                                                spacing=5,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.START,
                                    ),
                                    ft.Divider(),
                                    ft.Row(
                                        [
                                            ft.Column(
                                                [
                                                    ft.Text(
                                                        "Capacidad",
                                                        size=12,
                                                        color=ft.Colors.GREY_700,
                                                    ),
                                                    ft.Text(
                                                        f"{truck['capacity_kg']} kg",
                                                        size=16,
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                ]
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Text(
                                                        "Combustible",
                                                        size=12,
                                                        color=ft.Colors.GREY_700,
                                                    ),
                                                    ft.Text(
                                                        truck["fuel_type"].title(),
                                                        size=16,
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                ]
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Text(
                                                        "Estado",
                                                        size=12,
                                                        color=ft.Colors.GREY_700,
                                                    ),
                                                    ft.Text(
                                                        truck["status"]
                                                        .replace("_", " ")
                                                        .title(),
                                                        size=16,
                                                        weight=ft.FontWeight.BOLD,
                                                        color=(
                                                            ft.Colors.GREEN
                                                            if truck["status"]
                                                            == "in_use"
                                                            else ft.Colors.ORANGE
                                                        ),
                                                    ),
                                                ]
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                                    ),
                                    ft.Container(height=20),
                                    ft.Row(
                                        [
                                            ft.ElevatedButton(
                                                "Reportar Problema",
                                                icon=ft.Icons.REPORT_PROBLEM,
                                                on_click=lambda e: self.report_truck_issue(
                                                    truck["id"]
                                                ),
                                                bgcolor=ft.Colors.ORANGE,
                                            ),
                                            ft.ElevatedButton(
                                                "Mantenimiento",
                                                icon=ft.Icons.BUILD,
                                                on_click=lambda e: self.request_maintenance(
                                                    truck["id"]
                                                ),
                                                bgcolor=ft.Colors.BLUE,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                ]
                            ),
                            padding=30,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=15,
                            bgcolor=ft.Colors.WHITE,
                        ),
                        ft.Container(height=30),
                        ft.Text(
                            "Información Adicional", size=18, weight=ft.FontWeight.BOLD
                        ),
                        ft.Container(height=10),
                        ft.Text(
                            f"Último mantenimiento: {truck['last_maintenance'] or 'No registrado'}",
                            size=14,
                        ),
                        (
                            ft.Text(f"Notas: {truck['notes'] or 'Sin notas'}", size=14)
                            if truck["notes"]
                            else ft.Container()
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            else:
                content = ft.Column(
                    [
                        ft.Text("Mi Camión", size=24, weight=ft.FontWeight.BOLD),
                        ft.Container(height=50),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Icon(
                                        ft.Icons.NO_CRASH,
                                        size=100,
                                        color=ft.Colors.GREY,
                                    ),
                                    ft.Text(
                                        "No tienes un camión asignado",
                                        size=18,
                                        color=ft.Colors.GREY_700,
                                    ),
                                    ft.Text(
                                        "Contacta al administrador para solicitar la asignación de un vehículo",
                                        size=14,
                                        color=ft.Colors.GREY_600,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            height=300,
                            alignment=ft.alignment.center,
                        ),
                    ]
                )

        elif self.current_view == "delivery_process":
            # Vista del proceso de entrega con 3 pasos
            if not hasattr(self, "delivery_customer"):
                content = ft.Text("Error: No hay cliente seleccionado")
            else:
                content = self.build_delivery_process_content()

        self.content_area.content = content
        self.page.update()

    def build_delivery_process_content(self):
        """Construye el contenido para el proceso de entrega según el paso actual"""
        customer = self.delivery_customer

        # Header con información del cliente
        header = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        f"🧊 Proceso de Entrega", size=24, weight=ft.FontWeight.BOLD
                    ),
                    ft.Text(f"Cliente: {customer['name']}", size=18),
                    ft.Text(f"Dirección: {customer['address']}", size=14),
                    ft.Text(f"Teléfono: {customer['phone']}", size=14),
                    # Mostrar información de la ruta si existe
                    ft.Text(
                        f"Ruta ID: {self.current_route_id or 'Entrega directa'}",
                        size=14,
                        color=ft.Colors.BLUE,
                    ),
                ]
            ),
            padding=20,
            bgcolor=ft.Colors.BLUE_50,
            border_radius=10,
            margin=ft.margin.only(bottom=20),
        )

        # Indicador de progreso
        progress_indicator = ft.Row(
            [
                ft.Container(
                    content=ft.Text(
                        "1", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
                    ),
                    width=40,
                    height=40,
                    bgcolor=(
                        ft.Colors.GREEN if self.delivery_step >= 1 else ft.Colors.GREY
                    ),
                    border_radius=20,
                    alignment=ft.alignment.center,
                ),
                ft.Container(
                    width=50,
                    height=2,
                    bgcolor=(
                        ft.Colors.GREEN if self.delivery_step >= 2 else ft.Colors.GREY
                    ),
                ),
                ft.Container(
                    content=ft.Text(
                        "2", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
                    ),
                    width=40,
                    height=40,
                    bgcolor=(
                        ft.Colors.GREEN if self.delivery_step >= 2 else ft.Colors.GREY
                    ),
                    border_radius=20,
                    alignment=ft.alignment.center,
                ),
                ft.Container(
                    width=50,
                    height=2,
                    bgcolor=(
                        ft.Colors.GREEN if self.delivery_step >= 3 else ft.Colors.GREY
                    ),
                ),
                ft.Container(
                    content=ft.Text(
                        "3", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
                    ),
                    width=40,
                    height=40,
                    bgcolor=(
                        ft.Colors.GREEN if self.delivery_step >= 3 else ft.Colors.GREY
                    ),
                    border_radius=20,
                    alignment=ft.alignment.center,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        # Contenido según el paso actual
        if self.delivery_step == 1:
            step_content = self.build_step_1_content()
        elif self.delivery_step == 2:
            step_content = self.build_step_2_content()
        elif self.delivery_step == 3:
            step_content = self.build_step_3_content()
        else:
            step_content = ft.Text("Error en el proceso")

        return ft.Column(
            [
                header,
                progress_indicator,
                ft.Container(height=20),
                step_content,
                ft.Container(height=20),
                ft.ElevatedButton(
                    "Cancelar Proceso",
                    on_click=lambda e: self.show_scanner(),
                    bgcolor=ft.Colors.RED,
                    color=ft.Colors.WHITE,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def build_step_1_content(self):
        """Paso 1: Registro del estado del refrigerador"""
        status_options = ft.RadioGroup(
            content=ft.Column(
                [
                    ft.Radio(value="exelent", label="Excelente - Limpio y funcionando"),
                    ft.Radio(
                        value="good", label="Bueno - Funcionando con limpieza menor"
                    ),
                    ft.Radio(
                        value="needs_cleaning", label="Regular - Necesita limpieza"
                    ),
                    ft.Radio(
                        value="needs_repair", label="Malo - Requiere mantenimiento"
                    ),
                    ft.Radio(value="damaged", label="Descompuesto - No funciona"),
                ]
            )
        )

        notes_field = ft.TextField(
            label="Observaciones adicionales (opcional)",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=400,
        )

        def continue_step_1(e):
            if status_options.value:
                self.complete_step_1(status_options.value, notes_field.value)
            else:
                self.show_error_message(
                    "Por favor selecciona el estado del refrigerador"
                )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Paso 1: Estado del Refrigerador",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text("Selecciona el estado actual del refrigerador:", size=14),
                    ft.Container(height=10),
                    status_options,
                    ft.Container(height=20),
                    notes_field,
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Continuar al Paso 2",
                        on_click=continue_step_1,
                        bgcolor=ft.Colors.BLUE,
                        color=ft.Colors.WHITE,
                        width=200,
                    ),
                ]
            ),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=10,
        )

    def build_step_2_content(self):
        """Paso 2: Registro de limpieza del refrigerador"""
        cleaning_performed = ft.Checkbox(
            label="Se realizó limpieza del refrigerador", value=False
        )

        cleaning_notes_field = ft.TextField(
            label="Detalles de la limpieza realizada",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=400,
        )

        merma_field = ft.TextField(
            label="Cantidad de bolsas de merma",
            value="0",
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        def add_merma_dialog(e):
            def close_merma_dialog(e):
                merma_dialog.open = False
                self.page.update()

            def save_merma(e):
                try:
                    merma_amount = (
                        int(merma_amount_field.value) if merma_amount_field.value else 0
                    )
                    merma_field.value = str(merma_amount)
                    merma_dialog.open = False
                    self.page.update()
                    self.show_success_message(
                        f"Merma registrada: {merma_amount} bolsas"
                    )
                except ValueError:
                    self.show_error_message("Ingresa un número válido")

            merma_amount_field = ft.TextField(
                label="Cantidad de bolsas de merma",
                keyboard_type=ft.KeyboardType.NUMBER,
                width=200,
            )

            merma_reason_field = ft.TextField(
                label="Motivo de la merma", multiline=True, min_lines=2, width=300
            )

            merma_dialog = ft.AlertDialog(
                title=ft.Text("Registrar Merma"),
                content=ft.Column(
                    [
                        merma_amount_field,
                        merma_reason_field,
                    ],
                    tight=True,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=close_merma_dialog),
                    ft.TextButton("Guardar", on_click=save_merma),
                ],
            )

            self.page.dialog = merma_dialog
            merma_dialog.open = True
            self.page.update()

        def continue_step_2(e):
            try:
                merma_bags = int(merma_field.value) if merma_field.value else 0
                self.complete_step_2(
                    cleaning_performed.value, cleaning_notes_field.value, merma_bags
                )
            except ValueError:
                self.show_error_message("Ingresa un número válido para la merma")

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Paso 2: Limpieza del Refrigerador",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(height=10),
                    cleaning_performed,
                    ft.Container(height=10),
                    cleaning_notes_field,
                    ft.Container(height=20),
                    ft.Row(
                        [
                            merma_field,
                            ft.ElevatedButton(
                                "Agregar Merma",
                                on_click=add_merma_dialog,
                                bgcolor=ft.Colors.ORANGE,
                                color=ft.Colors.WHITE,
                            ),
                        ]
                    ),
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Continuar al Paso 3",
                        on_click=continue_step_2,
                        bgcolor=ft.Colors.BLUE,
                        color=ft.Colors.WHITE,
                        width=200,
                    ),
                ]
            ),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=10,
        )

    def build_step_3_content(self):
        """Paso 3: Evidencia de llenado y generación de ticket"""
        bags_field = ft.TextField(
            label="Número de bolsas entregadas",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
        )

        evidence_notes_field = ft.TextField(
            label="Notas de evidencia",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=400,
            hint_text="Describe el estado final del refrigerador después del llenado",
        )

        # Mostrar cálculo en tiempo real
        price_per_bag = float(self.delivery_customer.get("price_sale", 0))

        def update_total(e):
            try:
                bags = int(bags_field.value) if bags_field.value else 0
                total = bags * price_per_bag
                total_display.value = f"Total a pagar: ${total:.2f}"
                self.page.update()
            except ValueError:
                total_display.value = "Total a pagar: $0.00"
                self.page.update()

        bags_field.on_change = update_total

        total_display = ft.Text(
            f"Total a pagar: $0.00",
            size=18,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN,
        )

        def complete_delivery(e):
            if not bags_field.value or int(bags_field.value) <= 0:
                self.show_error_message("Ingresa un número válido de bolsas")
                return

            self.complete_step_3(bags_field.value, evidence_notes_field.value)

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Paso 3: Evidencia de Llenado",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text("Registra la entrega final y genera el ticket", size=14),
                    ft.Container(height=20),
                    ft.Text(f"Precio por bolsa: ${price_per_bag:.2f}", size=14),
                    ft.Container(height=10),
                    bags_field,
                    ft.Container(height=10),
                    total_display,
                    ft.Container(height=20),
                    evidence_notes_field,
                    ft.Container(height=20),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "📷 Tomar Foto",
                                on_click=lambda e: self.show_success_message(
                                    "Foto capturada (simulado)"
                                ),
                                bgcolor=ft.Colors.PURPLE,
                                color=ft.Colors.WHITE,
                            ),
                            ft.ElevatedButton(
                                "🎫 Generar Ticket",
                                on_click=complete_delivery,
                                bgcolor=ft.Colors.GREEN,
                                color=ft.Colors.WHITE,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                    ),
                ]
            ),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=10,
        )

    def report_truck_issue(self, truck_id: str):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def submit_report(e):
            if issue_field.value:
                success = db_manager.update_truck_status(
                    truck_id=truck_id,
                    status="maintenance",
                    notes=f"Problema reportado: {issue_field.value}",
                )

                dialog.open = False

                if success:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Problema reportado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                    self.update_content()  # Actualizar vista
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error reportando problema"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        issue_field = ft.TextField(
            label="Describe el problema",
            multiline=True,
            min_lines=3,
            max_lines=5,
            width=400,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Reportar Problema del Camión"),
            content=issue_field,
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Reportar", on_click=submit_report),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def request_maintenance(self, truck_id: str):
        success = db_manager.update_truck_status(
            truck_id=truck_id,
            status="maintenance",
            notes="Mantenimiento solicitado por el trabajador",
        )

        if success:
            snack_bar = ft.SnackBar(
                content=ft.Text("Solicitud de mantenimiento enviada"),
                bgcolor=ft.Colors.GREEN,
            )
            self.update_content()  # Actualizar vista
        else:
            snack_bar = ft.SnackBar(
                content=ft.Text("Error enviando solicitud"), bgcolor=ft.Colors.RED
            )

        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def build_ticket_form(self):
        customers = db_manager.get_customers()
        customer_dropdown = ft.Dropdown(
            label="Cliente",
            options=[
                ft.dropdown.Option(key=c["id"], text=c["name"]) for c in customers
            ],
            width=300,
        )

        bags_field = ft.TextField(
            label="Número de bolsas", width=200, keyboard_type=ft.KeyboardType.NUMBER
        )

        def generate_ticket_click(e):
            if customer_dropdown.value and bags_field.value:
                bags = int(bags_field.value) if bags_field.value.isdigit() else 0
                if bags > 0:
                    success = db_manager.add_sale(
                        customer_id=customer_dropdown.value,
                        worker_username=self.user["username"],
                        bags_delivered=bags,
                    )

                    if success:
                        snack_bar = ft.SnackBar(
                            content=ft.Text("Ticket generado exitosamente"),
                            bgcolor=ft.Colors.GREEN,
                        )
                    else:
                        snack_bar = ft.SnackBar(
                            content=ft.Text("Error generando ticket"),
                            bgcolor=ft.Colors.RED,
                        )

                    self.page.overlay.append(snack_bar)
                    snack_bar.open = True
                    self.page.update()

        return ft.Column(
            [
                customer_dropdown,
                bags_field,
                ft.Container(height=20),
                ft.ElevatedButton("Generar Ticket", on_click=generate_ticket_click),
            ]
        )

    def build(self):
        nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.ROUTE, label="Rutas"),
                ft.NavigationRailDestination(icon=ft.Icons.MAP, label="Mapa"),
                # ft.NavigationRailDestination(
                #     icon=ft.Icons.BARCODE_READER, label="Escáner"
                # ),
                # ft.NavigationRailDestination(icon=ft.Icons.RECEIPT, label="Tickets"),
                ft.NavigationRailDestination(
                    icon=ft.Icons.LOCAL_SHIPPING, label="Mi Camión"
                ),
            ],
            on_change=self.nav_changed,
        )

        self.content_area = ft.Container(expand=True, padding=20)

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        f"Bienvenido, {self.user['name']}",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.IconButton(
                        ft.Icons.LOGOUT,
                        on_click=lambda e: self.on_logout(),
                        tooltip="Cerrar Sesión",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=ft.Colors.BLUE_50,
        )

        self.update_content()

        return ft.Column(
            [
                header,
                ft.Row(
                    [nav_rail, ft.VerticalDivider(width=1), self.content_area],
                    expand=True,
                ),
            ],
            expand=True,
        )

    def nav_changed(self, e):
        views = [
            self.show_routes,
            self.show_map,
            # self.show_scanner,
            # self.show_tickets,
            self.show_truck,
        ]
        if 0 <= e.control.selected_index < len(views):
            views[e.control.selected_index]()


class AdminDashboard:
    def __init__(self, page: ft.Page, user: Dict, on_logout):
        self.page = page
        self.user = user
        self.on_logout = on_logout
        self.current_view = "overview"

    def show_overview(self, e=None):
        self.current_view = "overview"
        self.update_content()

    def show_routes(self, e=None):
        self.current_view = "routes"
        self.update_content()

    def show_customers(self, e=None):
        self.current_view = "customers"
        self.update_content()

    def show_workers(self, e=None):
        self.current_view = "workers"
        self.update_content()

    def show_sales(self, e=None):
        self.current_view = "sales"
        self.update_content()

    def show_reports(self, e=None):
        self.current_view = "reports"
        self.update_content()

    def show_trucks(self, e=None):
        self.current_view = "trucks"
        self.update_content()

    ############# Navigation Rail Change Handler #######################
    def add_route(self, e):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_route(e):
            if name_field.value and description_field.value:
                success = db_manager.add_route(
                    sequence_route=sequence_route.value,
                    name=name_field.value,
                    customer=customer_assign_field.value,
                    worker_assign=worker_assign_field.value,
                    status=status_field.value,
                    description=description_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Ruta agregada exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error agregando ruta"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        sequence_route = ft.Dropdown(
            label="Asignar Secuencia de Ruta",
            options=[
                ft.dropdown.Option(key=int(i), text=f"Ruta {i + 1}") for i in range(10)
            ],
            width=300,
        )
        name_field = ft.TextField(label="Nombre de la ruta", width=300)
        description_field = ft.TextField(
            label="Descripción", width=300, multiline=True, min_lines=2, max_lines=5
        )
        customer_assign_field = ft.Dropdown(
            label="Asignar a Cliente",
            options=[
                ft.dropdown.Option(key=c["id"], text=c["name"])
                for c in db_manager.get_customers()
            ],
            width=300,
        )
        worker_assign_field = ft.Dropdown(
            label="Asignar a Trabajador",
            options=[
                ft.dropdown.Option(key=w["id"], text=w["name"])
                for w in db_manager.get_workers()
            ],
            width=300,
        )
        status_field = ft.Dropdown(
            label="Estado de la Ruta",
            options=[
                ft.dropdown.Option("pending", "Pendiente"),
                ft.dropdown.Option("in_progress", "En Progreso"),
                ft.dropdown.Option("completed", "Completada"),
            ],
            width=300,
            value="pending",
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Agregar Nueva Ruta"),
            content=ft.Column(
                [
                    sequence_route,
                    name_field,
                    description_field,
                    customer_assign_field,
                    worker_assign_field,
                    status_field,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_route),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def edit_route_dialog(self, route_id):
        route = db_manager.get_route_by_id(route_id=route_id)
        print(route, "<<<", type(route))
        if not route or len(route) == 0:
            return False

        # Access the first element of the list
        route_data = route[0]

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_route(e):
            if route_name.value and route_status.value:
                success = db_manager.update_route(
                    route_id=route_id,
                    name=route_name.value,
                    description=route_description.value,
                    assigned_worker_id=route_worker.value,
                    status=route_status.value,
                )
                dialog.open = False
                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Ruta actualizada con éxito"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error actualizando la ruta"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        route_name = ft.TextField(
            label="Nombre de ruta", value=route_data["name"], width=300
        )
        route_description = ft.TextField(
            label="Descripción", value=route_data["description"], width=300
        )
        route_worker = ft.TextField(
            label="Trabajador asignado",
            value=route_data["assigned_worker_id"],
            width=300,
        )
        route_status = ft.TextField(
            label="Estado", value=route_data["status"], width=300
        )

        dialog = ft.AlertDialog(
            title="Editar ruta",
            content=ft.Column(
                [
                    route_name,
                    route_description,
                    route_worker,
                    route_status,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_route),
            ],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def delete_route_dialog(self, route_id):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_delete(e):
            success = db_manager.delete_route(route_id)
            dialog.open = False

            if success:
                self.update_content()
                snack_bar = ft.SnackBar(
                    content=ft.Text("Ruta eliminada exitosamente"),
                    bgcolor=ft.Colors.GREEN,
                )
            else:
                snack_bar = ft.SnackBar(
                    content=ft.Text("Error eliminando Ruta"),
                    bgcolor=ft.Colors.RED,
                )
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Eliminar Ruta"),
            content=ft.Text(
                "¿Estás seguro de que deseas eliminar esta Ruta?\nEsta acción no se puede deshacer."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Eliminar", on_click=confirm_delete),
            ],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    ####################### Customers Management #######################
    def add_customer(self, e):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_customer(e):
            if name_field.value and address_field.value and phone_field.value:
                success = db_manager.add_customer(
                    name=name_field.value,
                    address=address_field.value,
                    latitude=latitude_field.value,
                    longitude=longitude_field.value,
                    phone=phone_field.value,
                    email=email_field.value,
                    price_sale=sale_price_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Cliente agregado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                    print("✅ Cliente agregado exitosamente")
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error agregando cliente"),
                        bgcolor=ft.Colors.RED,
                    )
                    print("❌ Error agregando cliente")
                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        print("🔄 Agregando cliente... ")
        name_field = ft.TextField(label="Nombre del cliente", width=300)
        address_field = ft.TextField(label="Dirección", width=300)
        latitude_field = ft.TextField(
            label="Latitud (opcional)",
            value=0.0,
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        longitude_field = ft.TextField(
            label="Longitud (opcional)",
            value=0.0,
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        phone_field = ft.TextField(label="Teléfono", width=300)
        email_field = ft.TextField(label="Email (opcional)", width=300)
        sale_price_field = ft.TextField(
            label="Precio de venta",
            value="0.0",
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Agregar Nuevo Cliente"),
            content=ft.Column(
                [
                    name_field,
                    address_field,
                    latitude_field,
                    longitude_field,
                    phone_field,
                    email_field,
                    sale_price_field,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_customer),
            ],
        )
        print("🔄 Mostrando diálogo para agregar cliente")
        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def delete_customer_dialog(self, customer_id: str):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_delete(e):
            # REvisar si el customer_id es válido y eliminar el cliente (guarda y sube cambios antes de hacer copy page de la web)
            success = db_manager.delete_customer(customer_id)
            dialog.open = False

            if success:

                self.update_content()
                snack_bar = ft.SnackBar(
                    content=ft.Text("Cliente eliminado exitosamente"),
                    bgcolor=ft.Colors.GREEN,
                )
            else:
                snack_bar = ft.SnackBar(
                    content=ft.Text("Error eliminando cliente"), bgcolor=ft.Colors.RED
                )

            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Eliminar Cliente"),
            content=ft.Text(
                "¿Estás seguro de que deseas eliminar este cliente?\nEsta acción no se puede deshacer.\nY eliminará todas las ventas asociadas."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Eliminar", on_click=confirm_delete),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def edit_customer_dialog(self, customer_id: str):
        customer = db_manager.get_customer_by_id(customer_id)
        if not customer:
            return False

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_customer(e):
            if name_field.value and address_field.value and phone_field.value:
                success = db_manager.update_customer(
                    customer_id=customer_id,
                    name=name_field.value,
                    address=address_field.value,
                    latitude=latitude_field.value,
                    longitude=longitude_field.value,
                    phone=phone_field.value,
                    email=email_field.value,
                    price_sale=price_sale_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Cliente actualizado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error actualizando cliente"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        name_field = ft.TextField(
            label="Nombre del cliente", value=customer["name"], width=300
        )
        address_field = ft.TextField(
            label="Dirección", value=customer["address"], width=300
        )
        latitude_field = ft.TextField(
            label="Latitud (opcional)",
            value=customer.get("latitude", 0.0),
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        longitude_field = ft.TextField(
            label="Longitud (opcional)",
            value=customer.get("longitude", 0.0),
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        phone_field = ft.TextField(label="Teléfono", value=customer["phone"], width=300)
        email_field = ft.TextField(
            label="Email (opcional)", value=customer["email"], width=300
        )
        price_sale_field = ft.TextField(
            label="Precio de venta (opcional)",
            value=str(customer.get("price_sale", 0.0)),
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Editar Cliente"),
            content=ft.Column(
                [
                    name_field,
                    address_field,
                    latitude_field,
                    longitude_field,
                    phone_field,
                    email_field,
                    price_sale_field,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_customer),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    ####################### Workers Management #######################
    def add_worker(self, e):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_worker(e):
            if username_field.value and name_field.value and password_field.value:
                success = db_manager.add_worker(
                    username=username_field.value,
                    name=name_field.value,
                    password=password_field.value,
                    email=email_field.value,
                    phone=phone_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Trabajador agregado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error agregando trabajador"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        username_field = ft.TextField(label="Usuario", width=300)
        name_field = ft.TextField(label="Nombre completo", width=300)
        password_field = ft.TextField(label="Contraseña", width=300, password=True)
        email_field = ft.TextField(label="Email (opcional)", width=300)
        phone_field = ft.TextField(label="Teléfono (opcional)", width=300)

        dialog = ft.AlertDialog(
            title=ft.Text("Agregar Nuevo Trabajador"),
            content=ft.Column(
                [username_field, name_field, password_field, email_field, phone_field],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_worker),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def update_worker(self, worker_id: str):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_worker(e):
            if username_field.value and name_field.value:
                success = db_manager.update_worker(
                    worker_id=worker_id,
                    username=username_field.value,
                    name=name_field.value,
                    email=email_field.value,
                    phone=phone_field.value,
                    is_active=is_active_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Trabajador actualizado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error actualizando trabajador"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()
            else:
                snack_bar = ft.SnackBar(
                    content=ft.Text("Por favor completa todos los campos requeridos"),
                    bgcolor=ft.Colors.RED,
                )
                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        worker = db_manager.get_worker_by_id(worker_id)
        username_field = ft.TextField(
            label="Usuario", value=worker["username"], width=300
        )
        name_field = ft.TextField(
            label="Nombre completo", value=worker["name"], width=300
        )
        email_field = ft.TextField(
            label="Email (opcional)", value=worker["email"], width=300
        )
        phone_field = ft.TextField(
            label="Teléfono (opcional)", value=worker["phone"], width=300
        )
        is_active_field = ft.Checkbox(
            label="Activo",
            value=worker["is_active"],
            width=100,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Editar Trabajador"),
            content=ft.Column(
                [username_field, name_field, email_field, phone_field, is_active_field],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_worker),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def delete_worker_dialog(self, worker_id: str):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_delete(e):
            success = db_manager.delete_worker(worker_id)
            dialog.open = False

            if success:
                self.update_content()
                snack_bar = ft.SnackBar(
                    content=ft.Text("Trabajador eliminado exitosamente"),
                    bgcolor=ft.Colors.GREEN,
                )
            else:
                snack_bar = ft.SnackBar(
                    content=ft.Text("Error eliminando trabajador"),
                    bgcolor=ft.Colors.RED,
                )

            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Eliminar Trabajador"),
            content=ft.Text(
                "¿Estás seguro de que deseas eliminar este trabajador?\nEsta acción no se puede deshacer."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Eliminar", on_click=confirm_delete),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def activate_worker(self, worker_id: str):
        worker = db_manager.get_worker_by_id(worker_id)
        success = db_manager.update_worker(
            worker_id=worker_id,
            is_active=True,
            username=worker.get("username", ""),
            name=worker.get("name", ""),
            email=worker.get("email", ""),
            phone=worker.get("phone", ""),
        )
        if success:
            self.update_content()
            snack_bar = ft.SnackBar(
                content=ft.Text("Trabajador activado exitosamente"),
                bgcolor=ft.Colors.GREEN,
            )
        else:
            snack_bar = ft.SnackBar(
                content=ft.Text("Error activando trabajador"), bgcolor=ft.Colors.RED
            )

        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.add(snack_bar)
        self.page.update()

    ####################### Dashboard Content Update #######################
    def update_content(self):
        content = ft.Container()

        if self.current_view == "overview":
            stats = db_manager.get_dashboard_stats()

            content = ft.Column(
                [
                    ft.Text(
                        "Dashboard Administrativo", size=28, weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(height=20),
                    ft.Row(
                        [
                            self.create_metric_card(
                                "Clientes",
                                str(stats["total_customers"]),
                                ft.Icons.PEOPLE,
                                ft.Colors.BLUE,
                            ),
                            self.create_metric_card(
                                "Trabajadores",
                                str(stats["total_workers"]),
                                ft.Icons.WORK,
                                ft.Colors.GREEN,
                            ),
                            self.create_metric_card(
                                "Camiones",
                                str(stats["total_trucks"]),
                                ft.Icons.LOCAL_SHIPPING,
                                ft.Colors.PURPLE,
                            ),
                            self.create_metric_card(
                                "Disponibles",
                                str(stats["available_trucks"]),
                                ft.Icons.CHECK_CIRCLE,
                                ft.Colors.TEAL,
                            ),
                        ],
                        wrap=True,
                    ),
                    ft.Container(height=10),
                    ft.Row(
                        [
                            self.create_metric_card(
                                "Ventas",
                                str(stats["total_sales"]),
                                ft.Icons.SHOPPING_CART,
                                ft.Colors.ORANGE,
                            ),
                            self.create_metric_card(
                                "Ingresos",
                                f"${stats['total_revenue']:.2f}",
                                ft.Icons.ATTACH_MONEY,
                                ft.Colors.RED,
                            ),
                        ],
                        wrap=True,
                    ),
                    ft.Container(height=30),
                    ft.Text("Actividad Reciente", size=20, weight=ft.FontWeight.BOLD),
                    self.build_recent_activity(),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "routes":
            routes = db_manager.get_routes()
            routes_list = []

            for route in routes:
                routes_list.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.ROUTE),
                        title=ft.Text(route["name"]),
                        subtitle=ft.Text(f"Descripción: {route['description']}"),
                        trailing=ft.Row(
                            [
                                ft.IconButton(
                                    ft.Icons.EDIT,
                                    on_click=lambda e, rid=route[
                                        "id"
                                    ]: self.edit_route_dialog(rid),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE,
                                    on_click=lambda e, rid=route[
                                        "id"
                                    ]: self.delete_route_dialog(rid),
                                    icon_color=ft.Colors.RED,
                                ),
                            ],
                            tight=True,
                        ),
                    )
                )

            content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Gestión de Rutas", size=24, weight=ft.FontWeight.BOLD
                            ),
                            ft.ElevatedButton(
                                "Agregar Ruta",
                                on_click=self.add_route,
                                icon=ft.Icons.ADD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=20),
                    *routes_list,
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "customers":
            customers = db_manager.get_customers()
            customers_list = []

            for customer in customers:
                customers_list.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.STORE),
                        title=ft.Text(
                            f"{customer['name']}        $ {customer['price_sale']:.2f}"
                        ),
                        subtitle=ft.Text(
                            f"{customer['address']} - {customer['phone']}"
                        ),
                        trailing=ft.Row(
                            [
                                ft.IconButton(
                                    ft.Icons.EDIT,
                                    on_click=lambda e, cid=customer[
                                        "id"
                                    ]: self.edit_customer_dialog(cid),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE,
                                    on_click=lambda e, cid=customer[
                                        "id"
                                    ]: self.delete_customer_dialog(cid),
                                    icon_color=ft.Colors.RED,
                                ),
                            ],
                            tight=True,
                        ),
                    )
                )

            content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Gestión de Clientes",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.ElevatedButton(
                                "Agregar Cliente",
                                on_click=self.add_customer,
                                icon=ft.Icons.ADD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=20),
                    *customers_list,
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "workers":
            workers = db_manager.get_workers()
            workers_list_activate = []
            workers_list_deactivate = []

            for worker in workers:
                if worker["is_active"]:
                    workers_list_activate.append(
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.PERSON),
                            title=ft.Text(worker["name"]),
                            subtitle=ft.Text(f"Usuario: {worker['username']}"),
                            trailing=ft.Row(
                                [
                                    ft.IconButton(
                                        ft.Icons.EDIT,
                                        on_click=lambda e, wid=worker[
                                            "id"
                                        ]: self.update_worker(wid),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.DELETE,
                                        on_click=lambda e, wid=worker[
                                            "id"
                                        ]: self.delete_worker_dialog(wid),
                                        icon_color=ft.Colors.RED,
                                    ),
                                ],
                                tight=True,
                            ),
                        )
                    )
                else:
                    workers_list_deactivate.append(
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.PERSON_OFF),
                            title=ft.Text(worker["name"]),
                            subtitle=ft.Text(f"Usuario: {worker['username']}"),
                            trailing=ft.Row(
                                [
                                    ft.IconButton(
                                        ft.Icons.CHECK_CIRCLE,
                                        on_click=lambda e, wid=worker[
                                            "id"
                                        ]: self.activate_worker(wid),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.DELETE,
                                        on_click=lambda e, wid=worker[
                                            "id"
                                        ]: self.delete_worker_dialog(wid),
                                        icon_color=ft.Colors.RED,
                                    ),
                                ],
                                tight=True,
                            ),
                        )
                    )

            content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Gestión de Trabajadores",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.ElevatedButton(
                                "Agregar Trabajador",
                                on_click=self.add_worker,
                                icon=ft.Icons.ADD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=20),
                    ft.Text(
                        "Trabajadores Activos",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN,
                    ),
                    *workers_list_activate,
                    ft.Text(
                        "Trabajadores Inactivos",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.RED,
                    ),
                    *workers_list_deactivate,
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "sales":
            sales = db_manager.get_sales(limit=20)
            sales_list = []
            for sale in sales:
                sales_list.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.RECEIPT),
                        title=ft.Text(f"{sale['customer_name']}"),
                        subtitle=ft.Text(
                            f"Trabajador: {sale['worker_name']} - Bolsas: {sale.get('bags_delivered', 0)}"
                        ),
                        trailing=ft.Text(
                            f"${sale['total_amount']:.2f}", weight=ft.FontWeight.BOLD
                        ),
                    )
                )

            content = ft.Column(
                [
                    ft.Text("Registro de Ventas", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=20),
                    *(
                        sales_list
                        if sales_list
                        else [ft.Text("No hay ventas registradas")]
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "reports":
            weekly_sales = db_manager.get_sales_by_period("weekly")
            monthly_sales = db_manager.get_sales_by_period("monthly")

            weekly_revenue = sum(sale.get("total_amount", 0) for sale in weekly_sales)
            monthly_revenue = sum(sale.get("total_amount", 0) for sale in monthly_sales)

            content = ft.Column(
                [
                    ft.Text("Reportes de Ventas", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=20),
                    ft.Row(
                        [
                            self.create_report_card(
                                "Ventas Semanales",
                                len(weekly_sales),
                                f"${weekly_revenue:.2f}",
                            ),
                            self.create_report_card(
                                "Ventas Mensuales",
                                len(monthly_sales),
                                f"${monthly_revenue:.2f}",
                            ),
                        ]
                    ),
                    ft.Container(height=30),
                    ft.Text("Gráfico de Ventas", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.BAR_CHART, size=100, color=ft.Colors.BLUE
                                ),
                                ft.Text("Gráfico de ventas por período"),
                                ft.Text("(Integración con librerías de gráficos)"),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        height=300,
                        border=ft.border.all(1, ft.Colors.GREY),
                        border_radius=10,
                        alignment=ft.alignment.center,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        elif self.current_view == "trucks":
            trucks = db_manager.get_trucks()
            trucks_list = []

            for truck in trucks:
                status_color = {
                    "available": ft.Colors.GREEN,
                    "in_use": ft.Colors.BLUE,
                    "maintenance": ft.Colors.ORANGE,
                    "out_of_service": ft.Colors.RED,
                }.get(truck["status"], ft.Colors.GREY)

                trucks_list.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.LOCAL_SHIPPING,
                                                size=40,
                                                color=ft.Colors.BLUE,
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Text(
                                                        f"{truck['brand']} {truck['model']}",
                                                        size=16,
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                    ft.Text(
                                                        f"Placa: {truck['license_plate']}",
                                                        size=14,
                                                    ),
                                                    ft.Text(
                                                        f"Año: {truck['year'] or 'N/A'}",
                                                        size=12,
                                                        color=ft.Colors.GREY_700,
                                                    ),
                                                ],
                                                spacing=2,
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Container(
                                                        content=ft.Text(
                                                            truck["status"]
                                                            .replace("_", " ")
                                                            .title(),
                                                            size=12,
                                                            color=ft.Colors.WHITE,
                                                            weight=ft.FontWeight.BOLD,
                                                        ),
                                                        bgcolor=status_color,
                                                        padding=ft.padding.symmetric(
                                                            horizontal=8, vertical=4
                                                        ),
                                                        border_radius=10,
                                                    )
                                                ]
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Divider(height=1),
                                    ft.Row(
                                        [
                                            ft.Text(
                                                f"Capacidad: {truck['capacity_kg']} kg",
                                                size=12,
                                            ),
                                            ft.Text(
                                                f"Combustible: {truck['fuel_type'].title()}",
                                                size=12,
                                            ),
                                        ]
                                    ),
                                    ft.Text(
                                        f"Asignado a: {truck['assigned_worker_name'] or 'Sin asignar'}",
                                        size=12,
                                        color=(
                                            ft.Colors.BLUE
                                            if truck["assigned_worker_name"]
                                            else ft.Colors.GREY_700
                                        ),
                                    ),
                                    ft.Row(
                                        [
                                            ft.ElevatedButton(
                                                "Asignar",
                                                icon=ft.Icons.PERSON_ADD,
                                                on_click=lambda e, tid=truck[
                                                    "id"
                                                ]: self.assign_truck_dialog(tid),
                                                disabled=truck["status"] != "available",
                                            ),
                                            ft.ElevatedButton(
                                                "Editar",
                                                icon=ft.Icons.EDIT,
                                                on_click=lambda e, tid=truck[
                                                    "id"
                                                ]: self.edit_truck_dialog(tid),
                                            ),
                                            ft.IconButton(
                                                ft.Icons.DELETE,
                                                on_click=lambda e, tid=truck[
                                                    "id"
                                                ]: self.delete_truck(tid),
                                                icon_color=ft.Colors.RED,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                ],
                                spacing=10,
                            ),
                            padding=15,
                        ),
                        margin=ft.margin.only(bottom=10),
                    )
                )

            content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Gestión de Camiones",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.ElevatedButton(
                                "Agregar Camión",
                                on_click=self.add_truck,
                                icon=ft.Icons.ADD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=20),
                    *(
                        trucks_list
                        if trucks_list
                        else [ft.Text("No hay camiones registrados")]
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        ####################### Fridges Management #######################
        elif self.current_view == "fridges":
            fridges = db_manager.get_fridges()
            fridges_list = []

            for fridge in fridges:
                size_display = {
                    "small": "Pequeño",
                    "medium": "Mediano",
                    "large": "Grande",
                    "extra_large": "Extra Grande",
                }.get(fridge["size"], fridge["size"])

                fridges_list.append(
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.KITCHEN,
                                                size=40,
                                                color=ft.Colors.BLUE,
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Text(
                                                        fridge["name"],
                                                        size=16,
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                    ft.Text(
                                                        f"Cliente: {fridge['customer_name']}",
                                                        size=14,
                                                    ),
                                                    ft.Text(
                                                        f"Modelo: {fridge['model']}",
                                                        size=12,
                                                        color=ft.Colors.GREY_700,
                                                    ),
                                                ],
                                                spacing=2,
                                            ),
                                            ft.Column(
                                                [
                                                    ft.Container(
                                                        content=ft.Text(
                                                            size_display,
                                                            size=12,
                                                            color=ft.Colors.WHITE,
                                                            weight=ft.FontWeight.BOLD,
                                                        ),
                                                        bgcolor=ft.Colors.GREEN,
                                                        padding=ft.padding.symmetric(
                                                            horizontal=8, vertical=4
                                                        ),
                                                        border_radius=10,
                                                    )
                                                ]
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                    ft.Divider(height=1),
                                    ft.Row(
                                        [
                                            ft.Text(
                                                f"Capacidad: {fridge['capacity']} L",
                                                size=12,
                                            ),
                                            ft.Text(
                                                f"Registrado: {fridge['created_at']}",
                                                size=12,
                                                color=ft.Colors.GREY_600,
                                            ),
                                        ]
                                    ),
                                    ft.Row(
                                        [
                                            ft.ElevatedButton(
                                                "Ver Detalles",
                                                icon=ft.Icons.VISIBILITY,
                                                on_click=lambda e, fid=fridge[
                                                    "id"
                                                ]: self.view_fridge_details(fid),
                                                bgcolor=ft.Colors.BLUE,
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.ElevatedButton(
                                                "Editar",
                                                icon=ft.Icons.EDIT,
                                                on_click=lambda e, fid=fridge[
                                                    "id"
                                                ]: self.edit_fridge_dialog(fid),
                                                bgcolor=ft.Colors.ORANGE,
                                                color=ft.Colors.WHITE,
                                            ),
                                            ft.IconButton(
                                                ft.Icons.DELETE,
                                                on_click=lambda e, fid=fridge[
                                                    "id"
                                                ]: self.delete_fridge_dialog(fid),
                                                icon_color=ft.Colors.RED,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                ],
                                spacing=10,
                            ),
                            padding=15,
                        ),
                        margin=ft.margin.only(bottom=10),
                    )
                )

            content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Gestión de Refrigeradores",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.ElevatedButton(
                                "Agregar Refrigerador",
                                on_click=self.add_fridge,
                                icon=ft.Icons.ADD,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=20),
                    *(
                        fridges_list
                        if fridges_list
                        else [ft.Text("No hay refrigeradores registrados")]
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        self.content_area.content = content
        self.page.update()

    ####################### Trucks Management #######################
    def assign_truck_dialog(self, truck_id: str):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def assign_truck(e):
            if worker_dropdown.value:
                success = db_manager.assign_truck_to_worker(
                    truck_id, worker_dropdown.value
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Camión asignado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error asignando camión"), bgcolor=ft.Colors.RED
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        workers = db_manager.get_workers()
        worker_dropdown = ft.Dropdown(
            label="Seleccionar trabajador",
            width=300,
            options=[ft.dropdown.Option(w["id"], w["name"]) for w in workers],
        )

        dialog = ft.AlertDialog(
            title=ft.Text("Asignar Camión"),
            content=worker_dropdown,
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Asignar", on_click=assign_truck),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def edit_truck_dialog(self, truck_id: str):
        # Implementar edición de camión (similar a add_truck pero con datos precargados)
        snack_bar = ft.SnackBar(
            content=ft.Text("Función de edición en desarrollo"), bgcolor=ft.Colors.BLUE
        )
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.add(snack_bar)
        self.page.update()

    def add_truck(self, e):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_truck(e):
            if license_plate_field.value and brand_field.value and model_field.value:
                year = int(year_field.value) if year_field.value.isdigit() else None
                capacity = (
                    int(capacity_field.value)
                    if capacity_field.value.isdigit()
                    else 1000
                )

                success = db_manager.add_truck(
                    license_plate=license_plate_field.value,
                    brand=brand_field.value,
                    model=model_field.value,
                    year=year,
                    capacity_kg=capacity,
                    fuel_type=fuel_dropdown.value,
                    notes=notes_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Camión agregado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error agregando camión"), bgcolor=ft.Colors.RED
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        license_plate_field = ft.TextField(label="Placa", width=300)
        brand_field = ft.TextField(label="Marca", width=300)
        model_field = ft.TextField(label="Modelo", width=300)
        year_field = ft.TextField(
            label="Año", width=300, keyboard_type=ft.KeyboardType.NUMBER
        )
        capacity_field = ft.TextField(
            label="Capacidad (kg)",
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
            value="1000",
        )
        fuel_dropdown = ft.Dropdown(
            label="Tipo de combustible",
            width=300,
            options=[
                ft.dropdown.Option("gasoline", "Gasolina"),
                ft.dropdown.Option("diesel", "Diésel"),
                ft.dropdown.Option("electric", "Eléctrico"),
            ],
            value="gasoline",
        )
        notes_field = ft.TextField(label="Notas (opcional)", width=300, multiline=True)

        dialog = ft.AlertDialog(
            title=ft.Text("Agregar Nuevo Camión"),
            content=ft.Column(
                [
                    license_plate_field,
                    brand_field,
                    model_field,
                    year_field,
                    capacity_field,
                    fuel_dropdown,
                    notes_field,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_truck),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def delete_truck(self, truck_id: str):
        def confirm_delete(e):
            # Aquí implementarías la eliminación lógica (is_active = FALSE)
            dialog.open = False
            snack_bar = ft.SnackBar(
                content=ft.Text("Función de eliminación en desarrollo"),
                bgcolor=ft.Colors.ORANGE,
            )
            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.add(snack_bar)
            self.page.update()

        def cancel_delete(e):
            dialog.open = False
            self.page.add(
                ft.SnackBar(
                    content=ft.Text("Eliminación cancelada"), bgcolor=ft.Colors.GREY
                )
            )
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Confirmar Eliminación"),
            content=ft.Text("¿Estás seguro de que quieres eliminar este camión?"),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel_delete),
                ft.TextButton(
                    "Eliminar",
                    on_click=confirm_delete,
                    style=ft.ButtonStyle(color=ft.Colors.RED),
                ),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    ####################### Fridges Management #######################
    def add_fridge(self, e):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_fridge(e):
            if (
                customer_dropdown.value
                and name_field.value
                and size_field.value
                and capacity_field.value
                and model_field.value
            ):
                success = db_manager.add_fridge(
                    customer_id=customer_dropdown.value,
                    name=name_field.value,
                    size=size_field.value,
                    capacity=capacity_field.value,
                    model=model_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Refrigerador agregado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error agregando refrigerador"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        customers = db_manager.get_customers()
        customer_dropdown = ft.Dropdown(
            label="Cliente",
            options=[
                ft.dropdown.Option(key=c["id"], text=c["name"]) for c in customers
            ],
            width=300,
        )

        name_field = ft.TextField(label="Nombre del refrigerador", width=300)

        size_field = ft.Dropdown(
            label="Tamaño",
            options=[
                ft.dropdown.Option("small", "Pequeño"),
                ft.dropdown.Option("medium", "Mediano"),
                ft.dropdown.Option("large", "Grande"),
                ft.dropdown.Option("extra_large", "Extra Grande"),
            ],
            width=300,
        )

        capacity_field = ft.TextField(
            label="Capacidad (litros)", width=300, keyboard_type=ft.KeyboardType.NUMBER
        )

        model_field = ft.TextField(label="Modelo", width=300)

        dialog = ft.AlertDialog(
            title=ft.Text("Agregar Nuevo Refrigerador"),
            content=ft.Column(
                [
                    customer_dropdown,
                    name_field,
                    size_field,
                    capacity_field,
                    model_field,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_fridge),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def edit_fridge_dialog(self, fridge_id: str):
        fridge = db_manager.get_fridge_by_id(fridge_id)
        if not fridge:
            return

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def save_fridge(e):
            if (
                customer_dropdown.value
                and name_field.value
                and size_field.value
                and capacity_field.value
                and model_field.value
            ):
                success = db_manager.update_fridge(
                    fridge_id=fridge_id,
                    customer_id=customer_dropdown.value,
                    name=name_field.value,
                    size=size_field.value,
                    capacity=capacity_field.value,
                    model=model_field.value,
                )

                dialog.open = False

                if success:
                    self.update_content()
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Refrigerador actualizado exitosamente"),
                        bgcolor=ft.Colors.GREEN,
                    )
                else:
                    snack_bar = ft.SnackBar(
                        content=ft.Text("Error actualizando refrigerador"),
                        bgcolor=ft.Colors.RED,
                    )

                self.page.overlay.append(snack_bar)
                snack_bar.open = True
                self.page.update()

        customers = db_manager.get_customers()
        customer_dropdown = ft.Dropdown(
            label="Cliente",
            options=[
                ft.dropdown.Option(key=c["id"], text=c["name"]) for c in customers
            ],
            value=fridge["customer_id"],
            width=300,
        )

        name_field = ft.TextField(
            label="Nombre del refrigerador", value=fridge["name"], width=300
        )

        size_field = ft.Dropdown(
            label="Tamaño",
            options=[
                ft.dropdown.Option("small", "Pequeño"),
                ft.dropdown.Option("medium", "Mediano"),
                ft.dropdown.Option("large", "Grande"),
                ft.dropdown.Option("extra_large", "Extra Grande"),
            ],
            value=fridge["size"],
            width=300,
        )

        capacity_field = ft.TextField(
            label="Capacidad (litros)",
            value=str(fridge["capacity"]),
            width=300,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        model_field = ft.TextField(label="Modelo", value=fridge["model"], width=300)

        dialog = ft.AlertDialog(
            title=ft.Text("Editar Refrigerador"),
            content=ft.Column(
                [
                    customer_dropdown,
                    name_field,
                    size_field,
                    capacity_field,
                    model_field,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Guardar", on_click=save_fridge),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def delete_fridge_dialog(self, fridge_id: str):
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        def confirm_delete(e):
            success = db_manager.delete_fridge(fridge_id)
            dialog.open = False

            if success:
                self.update_content()
                snack_bar = ft.SnackBar(
                    content=ft.Text("Refrigerador eliminado exitosamente"),
                    bgcolor=ft.Colors.GREEN,
                )
            else:
                snack_bar = ft.SnackBar(
                    content=ft.Text("Error eliminando refrigerador"),
                    bgcolor=ft.Colors.RED,
                )

            self.page.overlay.append(snack_bar)
            snack_bar.open = True
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Eliminar Refrigerador"),
            content=ft.Text(
                "¿Estás seguro de que deseas eliminar este refrigerador?\n"
                "Esta acción no se puede deshacer."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=close_dialog),
                ft.TextButton("Eliminar", on_click=confirm_delete),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def view_fridge_details(self, fridge_id: str):
        fridge = db_manager.get_fridge_by_id(fridge_id)
        if not fridge:
            return

        def close_dialog(e):
            dialog.open = False
            self.page.update()

        # Obtener historial de entregas para este refrigerador
        deliveries = db_manager.get_deliveries_by_fridge(fridge_id)

        delivery_history = []
        for delivery in deliveries[:5]:  # Mostrar últimas 5 entregas
            delivery_history.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.DELIVERY_DINING, color=ft.Colors.GREEN),
                    title=ft.Text(f"Entrega: {delivery['bags_delivered']} bolsas"),
                    subtitle=ft.Text(
                        f"Fecha: {delivery['delivery_date']} - Trabajador: {delivery['worker_name']}"
                    ),
                    trailing=ft.Text(f"${delivery['total_amount']:.2f}"),
                )
            )

        size_display = {
            "small": "Pequeño",
            "medium": "Mediano",
            "large": "Grande",
            "extra_large": "Extra Grande",
        }.get(fridge["size"], fridge["size"])

        content = ft.Column(
            [
                ft.Text(
                    "Información del Refrigerador", size=18, weight=ft.FontWeight.BOLD
                ),
                ft.Divider(),
                ft.Text(f"Cliente: {fridge['customer_name']}", size=14),
                ft.Text(f"Nombre: {fridge['name']}", size=14),
                ft.Text(f"Tamaño: {size_display}", size=14),
                ft.Text(f"Capacidad: {fridge['capacity']} litros", size=14),
                ft.Text(f"Modelo: {fridge['model']}", size=14),
                ft.Text(
                    f"Fecha de registro: {fridge['created_at']}",
                    size=12,
                    color=ft.Colors.GREY_700,
                ),
                ft.Container(height=20),
                ft.Text("Historial de Entregas", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                *(
                    delivery_history
                    if delivery_history
                    else [
                        ft.Text("No hay entregas registradas", color=ft.Colors.GREY_600)
                    ]
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

        dialog = ft.AlertDialog(
            title=ft.Text(f"Detalles - {fridge['name']}"),
            content=ft.Container(content=content, width=500, height=400),
            actions=[
                ft.TextButton("Cerrar", on_click=close_dialog),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.add(dialog)
        self.page.update()

    def show_fridges(self, e=None):
        self.current_view = "fridges"
        self.update_content()

    ######################## Metric and Report Cards #######################
    def create_metric_card(self, title: str, value: str, icon, color):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, size=40, color=color),
                    ft.Text(value, size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(title, size=14, color=ft.Colors.GREY_700),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=150,
            height=120,
            padding=20,
            border_radius=10,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_300),
        )

    def create_report_card(self, title: str, count: int, revenue: str):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Cantidad: {count}", size=14),
                    ft.Text(
                        f"Ingresos: {revenue}",
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN,
                    ),
                ]
            ),
            width=200,
            padding=20,
            border_radius=10,
            bgcolor=ft.Colors.BLUE_50,
            border=ft.border.all(1, ft.Colors.BLUE_200),
        )

    ######################### Recent Activity Section #######################
    def build_recent_activity(self):
        sales = db_manager.get_sales(limit=5)
        if not sales:
            return ft.Text("No hay actividad reciente")

        activity_items = []
        for sale in sales:
            activity_items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.DELIVERY_DINING, color=ft.Colors.GREEN),
                    title=ft.Text(f"Entrega a {sale['customer_name']}"),
                    subtitle=ft.Text(
                        f"Por {sale['worker_name']} - {sale.get('bags_delivered', 0)} bolsas"
                    ),
                    trailing=ft.Text(f"${sale['total_amount']:.2f}"),
                )
            )

        return ft.Column(activity_items)

    ########################## Main Dashboard Class #########################
    def build(self):
        nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=95,
            min_extended_width=150,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.DASHBOARD, label="Dashboard"
                ),
                ft.NavigationRailDestination(icon=ft.Icons.ROUTE, label="Rutas"),
                ft.NavigationRailDestination(icon=ft.Icons.PEOPLE, label="Clientes"),
                ft.NavigationRailDestination(icon=ft.Icons.WORK, label="Trabajadores"),
                ft.NavigationRailDestination(
                    icon=ft.Icons.LOCAL_SHIPPING, label="Camiones"
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.KITCHEN, label="Refrigeradores"  # Agregar esta línea
                ),
                ft.NavigationRailDestination(
                    icon=ft.Icons.SHOPPING_CART, label="Ventas"
                ),
                ft.NavigationRailDestination(icon=ft.Icons.ANALYTICS, label="Reportes"),
            ],
            on_change=self.nav_changed,
        )

        self.content_area = ft.Container(expand=True, padding=20)

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        f"Panel Administrativo - {self.user['name']} - {self.user['role'].capitalize()}",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.IconButton(
                        ft.Icons.LOGOUT,
                        on_click=lambda e: self.on_logout(),
                        tooltip="Cerrar Sesión",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.symmetric(horizontal=20, vertical=10),
            bgcolor=ft.Colors.ORANGE_50,
        )

        self.update_content()

        return ft.Column(
            [
                header,
                ft.Row(
                    [nav_rail, ft.VerticalDivider(width=1), self.content_area],
                    expand=True,
                ),
            ],
            expand=True,
        )

    def nav_changed(self, e):
        views = [
            self.show_overview,
            self.show_routes,
            self.show_customers,
            self.show_workers,
            self.show_trucks,
            self.show_fridges,  # Agregar esta línea
            self.show_sales,
            self.show_reports,
        ]
        if 0 <= e.control.selected_index < len(views):
            views[e.control.selected_index]()


class IceDeliveryApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Ice Delivery App"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window_width = 1200
        self.page.window_height = 800
        self.current_user = None
        self.current_view = None
        self.show_login()

    def show_login(self):
        login_view = LoginView(self.page, self.on_login_success)
        self.page.clean()
        self.page.add(login_view.build())
        self.page.update()

    def on_login_success(self, user: Dict):
        self.current_user = user
        if user["role"] == "admin":
            self.show_admin_dashboard()
        else:
            self.show_worker_dashboard()

    def show_admin_dashboard(self):
        admin_dashboard = AdminDashboard(self.page, self.current_user, self.logout)
        self.current_view = admin_dashboard
        self.page.clean()
        self.page.add(admin_dashboard.build())
        self.page.update()

    def show_worker_dashboard(self):
        worker_dashboard = WorkerDashboard(self.page, self.current_user, self.logout)
        self.current_view = worker_dashboard
        self.page.clean()
        self.page.add(worker_dashboard.build())
        self.page.update()

    def logout(self):
        self.current_user = None
        self.current_view = None
        self.show_login()


def main(page: ft.Page):
    page.adaptive = True
    app = IceDeliveryApp(page)


def detect_environment():
    """Detecta si estamos en un entorno con soporte para ventanas de escritorio"""
    import subprocess
    import platform

    # Detectar el sistema operativo
    system = platform.system().lower()

    if system == "windows":
        # En Windows, siempre usar desktop si no se especifica otra cosa
        return "desktop"

    # Verificar si estamos en WSL (solo en Linux)
    if system == "linux":
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return "web"  # WSL generalmente no tiene soporte para ventanas
        except:
            pass

        # Verificar si tenemos DISPLAY y un servidor X funcionando
        if not os.getenv("DISPLAY"):
            return "web"

        # Verificar si podemos ejecutar aplicaciones gráficas
        try:
            subprocess.run(
                ["xdpyinfo"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            return "desktop"
        except:
            return "web"

    # Para macOS y otros sistemas, intentar desktop por defecto
    return "desktop"


if __name__ == "__main__":
    import sys

    try:
        print("🚀 Iniciando Ice Delivery App...")

        # Verificar argumentos de línea de comandos
        force_desktop = "--desktop" in sys.argv
        force_web = "--web" in sys.argv
        force_ios = "--ios" in sys.argv

        if force_ios:
            mode = "ios"
            print("📱 Modo iOS forzado por argumento")
        elif force_desktop:
            mode = "desktop"
            print("🗺️ Modo desktop forzado por argumento")
        elif force_web:
            mode = "web"
            print("🌍 Modo web forzado por argumento")
        else:
            # Detectar el mejor modo para ejecutar la aplicación
            mode = detect_environment()

        if mode == "desktop":
            print("🖥️ La aplicación se abrirá en una ventana de escritorio")
            print("")
            print("👤 Credenciales de prueba:")
            print("   Admin: admin / admin123")
            print("   Worker: worker1 / worker123")
            print("")
            print("⚡ Presiona Ctrl+C para detener la aplicación")
            print("")
            # Ejecutar en modo desktop
            ft.app(target=main)
        elif mode == "ios":
            print("📱 La aplicación se abrirá en modo iOS (AppView.IOS)")
            print("🌐 URL: http://127.0.0.1:8080")
            print("")
            print("👤 Credenciales de prueba:")
            print("   Admin: admin / admin123")
            print("   Worker: worker1 / worker123")
            print("")
            print("⚡ Presiona Ctrl+C para detener la aplicación")
            print("")
            print(
                "💬 Tip: Usa 'python src/main.py --desktop' para forzar modo escritorio"
            )
            print("")
            # Ejecutar en modo iOS
            ft.app(target=main, view=ft.AppView.FLET_APP, port=8080)
        else:
            print("🌐 La aplicación se abrirá en tu navegador web")
            print(
                "💻 Modo web habilitado (entorno sin soporte para ventanas de escritorio)"
            )
            print("🌐 URL: http://127.0.0.1:8080")
            print("")
            print("👤 Credenciales de prueba:")
            print("   Admin: admin / admin123")
            print("   Worker: worker1 / worker123")
            print("")
            print("⚡ Presiona Ctrl+C para detener la aplicación")
            print("")
            print(
                "💬 Tip: Usa 'python src/main.py --desktop' para forzar modo escritorio"
            )
            print("")
            # Ejecutar en modo web
            ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8080)
    finally:
        # Cerrar conexión a la base de datos al salir
        db_manager.close()
