import flet as ft
import os
import sys
from dotenv import load_dotenv
import threading
from sync_service import sync_all_data, sync_if_needed

from database_mobile_simplified import db_manager
from typing import Dict, List, Optional
from datetime import datetime

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


class LoginView:
    def __init__(self, page: ft.Page, on_login_success):
        self.page = page
        self.on_login_success = on_login_success
        self.username_field = ft.TextField(
            label="Usuario",
            prefix_icon=ft.Icons.PERSON,
            expand=True,
            text_size=16,
            height=60,
        )
        self.password_field = ft.TextField(
            label="Contraseña",
            password=True,
            prefix_icon=ft.Icons.LOCK,
            expand=True,
            text_size=16,
            height=60,
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
                    ft.Container(height=100),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.AC_UNIT,
                                    size=80,
                                    color=ft.Colors.BLUE,
                                ),
                                ft.Text(
                                    "Ice Delivery",
                                    size=32,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.BLUE,
                                ),
                                ft.Text(
                                    "Sistema de Entrega de Hielo",
                                    size=16,
                                    color=ft.Colors.GREY_700,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        padding=ft.padding.all(20),
                    ),
                    ft.Container(height=40),
                    ft.Container(
                        content=ft.Column(
                            [
                                self.username_field,
                                ft.Container(height=16),
                                self.password_field,
                                ft.Container(height=24),
                                ft.ElevatedButton(
                                    "Iniciar Sesión",
                                    on_click=self.login_clicked,
                                    width=200,
                                    height=50,
                                    style=ft.ButtonStyle(
                                        bgcolor=ft.Colors.BLUE,
                                        color=ft.Colors.WHITE,
                                        text_style=ft.TextStyle(
                                            size=16, weight=ft.FontWeight.BOLD
                                        ),
                                    ),
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0,
                        ),
                        padding=ft.padding.symmetric(horizontal=40),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_center,
                end=ft.alignment.bottom_center,
                colors=[ft.Colors.BLUE_50, ft.Colors.WHITE],
            ),
            expand=True,
        )


class WorkerDashboard:
    def __init__(self, page: ft.Page, user: Dict, on_logout):
        self.page = page
        self.user = user
        self.on_logout = on_logout
        self.current_view = "routes"
        self.current_route_id = None
        self.delivery_customer = None
        self.delivery_step = 1
        self.delivery_data = {}
        print("delivery_data:", self.delivery_data)
        self.bags_to_delivered = 0
        self.bags_delivered = 0
        self.shrink_bags = 0
        self.assigned_truck = self.get_assigned_truck()

    def get_assigned_truck(self):
        """Check if worker has an assigned truck"""
        try:
            truck_info = db_manager.get_worker_truck(self.user["id"])
            return truck_info if truck_info else None
        except:
            return None

    def show_routes(self, e=None):
        self.current_view = "routes"
        self.current_route_id = None
        self.update_content()

    def show_maps(self, route_id=None):
        self.current_view = "maps"
        if route_id:
            self.current_route_id = route_id
        self.update_content()

    def show_truck(self, route_id=None):
        self.current_view = "trucks"
        self.update_content()

    def process_barcode_scan(self, barcode_value, id_customer):
        if not barcode_value or not barcode_value.strip():
            self.show_error_message("Por favor ingresa un código válido")
            return

        customer = db_manager.get_customer_by_barcode(barcode_value.strip())
        if customer and customer["id"] == id_customer:
            self.close_dialog()
            self.update_content()
            self.start_delivery_process(customer)
        else:
            self.show_error_message(
                f"No se encontró cliente con el código: {barcode_value} o no es la ruta correcta"
            )

    def start_delivery_process(self, customer):
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
        self.current_view = "delivery_process"
        self.update_content()

    def show_error_message(self, message):
        snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED)
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def show_success_message(self, message):
        snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.GREEN)
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def update_content(self):
        if self.current_view == "routes":
            self.content_area.content = self.build_routes()
        elif self.current_view == "maps":
            self.content_area.content = self.build_maps()
        elif self.current_view == "trucks":
            self.content_area.content = self.build_truck_view()
        elif self.current_view == "delivery_process":
            self.content_area.content = self.build_delivery_process()

        self.page.update()

    def build_routes(self):
        routes = db_manager.get_routes()

        if not routes:
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.ROUTE, size=64, color=ft.Colors.GREY_400),
                        ft.Text(
                            "No hay rutas asignadas",
                            size=18,
                            color=ft.Colors.GREY_600,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16,
                ),
                padding=ft.padding.all(40),
                alignment=ft.alignment.center,
            )

        route_cards = []
        # print("Rutas obtenidas:", routes)
        for route in routes:
            # customers = db_manager.get_route_customers()
            print(route)
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.ROUTE, color=ft.Colors.BLUE),
                                    ft.Text(
                                        f"Ruta para {route['customer_name']}",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Container(expand=True),
                                    ft.Chip(
                                        label=ft.Text(route["status"]),
                                        bgcolor=(
                                            ft.Colors.GREEN_100
                                            if route["status"] == "completed"
                                            else ft.Colors.GREY_100
                                        ),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.START,
                            ),
                            ft.Divider(height=1),
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.PEOPLE,
                                        size=16,
                                        color=ft.Colors.GREY_600,
                                    ),
                                    ft.Text(
                                        f" clientes",  # {len(customers)}
                                        color=ft.Colors.GREY_600,
                                    ),
                                    ft.Container(width=20),
                                    ft.Icon(
                                        ft.Icons.ACCESS_TIME,
                                        size=16,
                                        color=ft.Colors.GREY_600,
                                    ),
                                ],
                            ),
                            ft.Container(height=8),
                        ]
                        + (
                            [
                                ft.Row(
                                    [
                                        ft.ElevatedButton(
                                            "Ver Mapa",
                                            icon=ft.Icons.MAP,
                                            on_click=lambda e, r_id=route[
                                                "id"
                                            ]: self.show_maps(r_id),
                                            style=ft.ButtonStyle(
                                                bgcolor=ft.Colors.BLUE_100
                                            ),
                                            disabled=True,  # REVISAR False
                                        ),
                                        ft.Container(width=8),
                                        ft.ElevatedButton(
                                            "Entregar",
                                            icon=ft.Icons.LOCAL_SHIPPING,
                                            on_click=lambda e, r_id=route[
                                                "id"
                                            ]: self.show_barcode_scanner(r_id),
                                            style=ft.ButtonStyle(
                                                bgcolor=ft.Colors.GREEN_100
                                            ),
                                        ),
                                    ],
                                ),
                            ]
                            if route["status"] == "pending"
                            else []
                        ),
                    ),
                    padding=ft.padding.all(16),
                ),
                elevation=2,
            )
            route_cards.append(card)
            self.bags_to_delivered += int(route.get("bags", 0))

        return ft.Column(
            [
                ft.Text("Mis Rutas", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(height=16),
                *route_cards,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
        )

    def show_barcode_scanner(self, route_id):
        self.current_route_id = route_id
        customer_id = db_manager.get_route_customer_by_id(route_id)
        print("Customer ID:", customer_id)
        barcode_field = ft.TextField(
            label="Código de barras del cliente",
            prefix_icon=ft.Icons.QR_CODE,
            expand=True,
            autofocus=True,
        )

        def scan_barcode(e):
            self.process_barcode_scan(barcode_field.value, id_customer=customer_id)

        scanner_dialog = ft.AlertDialog(
            title=ft.Text("Escanear Cliente"),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Ingresa o escanea el código del cliente:"),
                        barcode_field,
                    ],
                    tight=True,
                ),
                width=300,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.close_dialog()),
                ft.ElevatedButton("Escanear", on_click=scan_barcode),
            ],
        )

        self.page.overlay.append(scanner_dialog)
        scanner_dialog.open = True
        # self.close_dialog()
        self.page.update()

    def close_dialog(self):
        if self.page.overlay:
            self.page.overlay[-1].open = False
            self.page.overlay.pop()
            self.page.update()
            self.update_content()

    def build_maps(self):
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
        return content

    def build_truck_view(self):
        if not self.assigned_truck:
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.LOCAL_SHIPPING, size=64, color=ft.Colors.GREY_400
                        ),
                        ft.Text(
                            "No tienes un camión asignado",
                            size=18,
                            color=ft.Colors.GREY_600,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "Contacta a tu supervisor para obtener asignación",
                            size=14,
                            color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16,
                ),
                padding=ft.padding.all(40),
                alignment=ft.alignment.center,
            )

        truck = self.assigned_truck
        return ft.Column(
            [
                ft.Text("Mi Camión", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(height=20),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(
                                            ft.Icons.LOCAL_SHIPPING,
                                            size=48,
                                            color=ft.Colors.BLUE,
                                        ),
                                        ft.Container(width=16),
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    f"Camión #{truck.get('truck_number', 'N/A')}",
                                                    size=20,
                                                    weight=ft.FontWeight.BOLD,
                                                ),
                                                ft.Text(
                                                    f"Placa: {truck.get('license_plate', 'N/A')}",
                                                    color=ft.Colors.GREY_600,
                                                ),
                                                ft.Text(
                                                    f"Modelo: {truck.get('model', 'N/A')}",
                                                    color=ft.Colors.GREY_600,
                                                ),
                                            ],
                                            expand=True,
                                        ),
                                    ],
                                ),
                                ft.Divider(),
                                ft.Row(
                                    [
                                        self.create_truck_info_card(
                                            "Capacidad",
                                            f"{truck.get('capacity', 0)} kg",
                                            ft.Icons.SCALE,
                                            ft.Colors.BLUE,
                                        ),
                                        self.create_truck_info_card(
                                            "Combustible",
                                            f"{truck.get('fuel_level', 0)}%",
                                            ft.Icons.LOCAL_GAS_STATION,
                                            ft.Colors.ORANGE,
                                        ),
                                    ],
                                ),
                                ft.Container(height=10),
                                ft.Row(
                                    [
                                        self.create_truck_info_card(
                                            "Estado",
                                            truck.get("status", "Desconocido"),
                                            ft.Icons.INFO,
                                            (
                                                ft.Colors.GREEN
                                                if truck.get("status") == "Operativo"
                                                else ft.Colors.RED
                                            ),
                                        ),
                                        self.create_truck_info_card(
                                            "Kilometraje",
                                            f"{truck.get('mileage', 0):,} km",
                                            ft.Icons.SPEED,
                                            ft.Colors.PURPLE,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        padding=ft.padding.all(20),
                    ),
                    elevation=2,
                ),
            ],
        )

    def create_truck_info_card(self, title, value, icon, color):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(icon, color=color, size=24),
                    ft.Text(title, size=12, color=ft.Colors.GREY_600),
                    ft.Text(value, size=16, weight=ft.FontWeight.BOLD),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            bgcolor=ft.Colors.GREY_50,
            border_radius=8,
            padding=ft.padding.all(12),
            expand=True,
        )

    def build_delivery_process(self):
        if not self.delivery_customer:
            return ft.Text("No hay proceso de entrega activo")

        customer = self.delivery_customer

        steps = [
            {"title": "Verificar Refrigerador", "icon": ft.Icons.KITCHEN},
            {"title": "Registrar Limpieza", "icon": ft.Icons.CLEANING_SERVICES},
            {"title": "Registrar Merma", "icon": ft.Icons.INVENTORY},
            {"title": "Entregar Pedido", "icon": ft.Icons.LOCAL_SHIPPING},
            {"title": "Tomar Evidencia", "icon": ft.Icons.CAMERA_ALT},
            {"title": "Finalizar Entrega", "icon": ft.Icons.CHECK_CIRCLE},
        ]
        print("Despues de steps")
        # Contenedores para comentarios y entradas
        comentarios_refrigerador = ft.TextField(
            label="Comentarios sobre el refrigerador",
            multiline=True,
            visible=self.delivery_step == 1,
        )
        print("Comentarios")
        comentarios_limpieza = ft.TextField(
            label="Comentarios sobre la limpieza",
            multiline=True,
            visible=self.delivery_step == 2,
        )
        print("Limpieza")
        cantidad_merma = ft.TextField(
            label="Cantidad de merma encontrada", visible=self.delivery_step == 3
        )
        print("Cantidad merma")
        cantidad_entregar = ft.TextField(
            label="Cantidad a entregar", visible=self.delivery_step == 4
        )
        print("cantidad entrega")
        boton_tomar_evidencia = ft.ElevatedButton(
            "Tomar Foto", on_click=self.take_photo, visible=self.delivery_step == 5
        )
        print("Boton")

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.ARROW_BACK,
                            on_click=self.show_routes,
                            tooltip="Volver",
                            icon_color=ft.Colors.BLACK,
                        ),
                        ft.Text(
                            "Proceso de Entrega", size=20, weight=ft.FontWeight.BOLD
                        ),
                    ]
                ),
                ft.Container(height=16),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Cliente:", weight=ft.FontWeight.BOLD),
                                ft.Text(customer["name"], size=16),
                                ft.Text(customer["address"], color=ft.Colors.GREY_700),
                            ],
                            spacing=4,
                        ),
                        padding=ft.padding.all(16),
                    ),
                    elevation=2,
                ),
                ft.Container(height=16),
                ft.Text(
                    f"Paso {self.delivery_step} de {len(steps)}",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=8),
                *[
                    ft.Card(
                        content=ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        step["icon"],
                                        color=(
                                            ft.Colors.GREEN
                                            if i < self.delivery_step - 1
                                            else (
                                                ft.Colors.BLUE
                                                if i == self.delivery_step - 1
                                                else ft.Colors.GREY_400
                                            )
                                        ),
                                    ),
                                    ft.Text(
                                        step["title"],
                                        expand=True,
                                        color=(
                                            ft.Colors.GREEN
                                            if i < self.delivery_step - 1
                                            else (
                                                ft.Colors.BLACK
                                                if i == self.delivery_step - 1
                                                else ft.Colors.GREY_400
                                            )
                                        ),
                                    ),
                                    ft.Icon(
                                        ft.Icons.CHECK_CIRCLE,
                                        color=(
                                            ft.Colors.GREEN
                                            if i < self.delivery_step - 1
                                            else ft.Colors.TRANSPARENT
                                        ),
                                    ),
                                ]
                            ),
                            padding=ft.padding.all(12),
                        ),
                        elevation=1 if i == self.delivery_step - 1 else 0,
                        color=(
                            ft.Colors.BLUE_50 if i == self.delivery_step - 1 else None
                        ),
                    )
                    for i, step in enumerate(steps)
                ],
                ft.Container(height=20),
                # Agregar los campos de texto según el paso actual
                comentarios_refrigerador,
                comentarios_limpieza,
                cantidad_merma,
                cantidad_entregar,
                boton_tomar_evidencia,
                ft.ElevatedButton(
                    "Continuar",
                    on_click=self.next_delivery_step,
                    width=200,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE),
                ),
                ft.Container(height=16),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def take_photo(self, e):
        # Lógica para tomar una foto
        pass

    def next_delivery_step(self, e):
        print(f"next_step: {e}")
        if self.delivery_step < 6:
            if self.delivery_step == 1:  # Verificar Refrigerador
                comments = e.comentarios_refrigerador.value
                print(comments)
                # db_manager.register_refrigerator_comments(customer_id, comments)
            elif self.delivery_step == 2:  # Registrar Limpieza
                comments = e.comentarios_limpieza.value
                print(comments)
                # db_manager.register_cleaning_comments(customer_id, comments)
            elif self.delivery_step == 3:  # Registrar Merma
                cantidad = e.cantidad_merma.value
                print(cantidad)
                # db_manager.register_merma(customer_id, cantidad)
            elif self.delivery_step == 4:  # Entregar Pedido
                cantidad = e.cantidad_entregar.value
                print(cantidad)
                # db_manager.register_delivery_quantity(customer_id, cantidad)
            self.delivery_step += 1
            self.update_content()
        else:
            self.complete_delivery()

    def complete_delivery(self):
        # Aquí se guardaría la entrega en la base de datos
        self.show_success_message("Entrega completada exitosamente")
        self.delivery_customer = None
        self.delivery_step = 1
        self.show_routes()

    def build(self):
        # def sync_clicked(sync):
        #     # Mostrar loading
        #     snack = ft.SnackBar(
        #         content=ft.Text("Sincronizando datos..."), bgcolor=ft.Colors.BLUE
        #     )
        #     self.page.overlay.append(snack)
        #     snack.open = True
        #     self.page.update()

        #     def do_sync():
        #         result = sync_all_data()

        #         def show_result():
        #             # Cerrar snack de carga
        #             snack.open = False

        #             if result["success"]:
        #                 msg = f"Datos actualizados: {', '.join(result['synced'])}"
        #                 color = ft.Colors.GREEN
        #             else:
        #                 msg = f"Errores: {', '.join(result['errors'])}"
        #                 color = ft.Colors.RED

        #             snack2 = ft.SnackBar(content=ft.Text(msg), bgcolor=color)
        #             self.page.overlay.append(snack2)
        #             snack2.open = True
        #             self.update_content()
        #             self.page.update()

        #         # Llamar directamente - Flet maneja thread-safety internamente
        #         show_result()

        #     threading.Thread(target=do_sync, daemon=True).start()

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        f"Hola, {self.user['name']}", size=18, weight=ft.FontWeight.BOLD
                    ),
                    # ft.IconButton(
                    #     ft.Icons.SYNC,
                    #     on_click=sync_clicked,
                    #     tooltip="Sincronizar datos",
                    # ),
                    ft.IconButton(
                        ft.Icons.LOGOUT,
                        on_click=lambda e: self.on_logout(),
                        tooltip="Cerrar Sesión",
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=ft.padding.all(16),
            bgcolor=ft.Colors.BLUE_50,
        )

        self.content_area = ft.Container(
            expand=True,
            padding=ft.padding.only(left=16, right=16, top=16, bottom=80),
        )

        bottom_nav = ft.Container(
            content=ft.NavigationBar(
                destinations=[
                    ft.NavigationBarDestination(icon=ft.Icons.ROUTE, label="Rutas"),
                    ft.NavigationBarDestination(icon=ft.Icons.MAP, label="Mapas"),
                    ft.NavigationBarDestination(
                        icon=ft.Icons.LOCAL_SHIPPING, label="Mi Camión"
                    ),
                ],
                on_change=lambda e: (
                    self.show_routes()
                    if e.control.selected_index == 0
                    else (
                        self.show_truck()
                        if e.control.selected_index == 2
                        else self.show_maps()
                    )
                ),
            ),
            bgcolor=ft.Colors.WHITE,
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.GREY_300)),
        )

        self.update_content()

        return ft.Stack(
            [
                ft.Column(
                    [
                        header,
                        self.content_area,
                    ],
                    expand=True,
                    spacing=0,
                ),
                ft.Container(
                    content=bottom_nav,
                    alignment=ft.alignment.bottom_center,
                    left=0,
                    right=0,
                    bottom=0,
                ),
            ],
            expand=True,
        )


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

    def show_workers(self, e=None):
        self.current_view = "workers"
        self.update_content()

    def show_customers(self, e=None):
        self.current_view = "customers"
        self.update_content()

    def show_sales(self, e=None):
        self.current_view = "sales"
        self.update_content()

    def update_content(self):
        if self.current_view == "overview":
            self.content_area.content = self.build_overview()
        elif self.current_view == "routes":
            self.content_area.content = self.build_routes()
        elif self.current_view == "workers":
            self.content_area.content = self.build_workers()
        elif self.current_view == "customers":
            self.content_area.content = self.build_customers()
        elif self.current_view == "sales":
            self.content_area.content = self.build_sales()

        self.page.update()

    def build_overview(self):
        stats = db_manager.get_dashboard_stats()

        return ft.Column(
            [
                ft.Text("Dashboard Admin", size=24, weight=ft.FontWeight.BOLD),
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
                    ]
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
                            f"${stats['total_revenue']:,.2f}",
                            ft.Icons.ATTACH_MONEY,
                            ft.Colors.PURPLE,
                        ),
                    ]
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def create_metric_card(self, title: str, value: str, icon, color):
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(icon, color=color, size=24),
                                ft.Container(expand=True),
                            ]
                        ),
                        ft.Text(value, size=24, weight=ft.FontWeight.BOLD),
                        ft.Text(title, size=14, color=ft.Colors.GREY_600),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.all(16),
                width=160,
                height=120,
            ),
            elevation=2,
        )

    def build_routes(self):
        routes = db_manager.get_routes()
        if not routes:
            return ft.Column(
                [
                    ft.Text("Gestión de Rutas", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=32),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.ROUTE,
                                    size=64,
                                    color=ft.Colors.GREY_400,
                                ),
                                ft.Text(
                                    "No hay rutas asignadas",
                                    size=18,
                                    color=ft.Colors.GREY_600,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    "Las rutas aparecerán aquí una vez que sean creadas",
                                    size=14,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=16,
                        ),
                        padding=ft.padding.all(40),
                        alignment=ft.alignment.center,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Gestión de Rutas", size=24, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                    ]
                ),
                ft.Container(height=16),
                *[
                    ft.Card(
                        content=ft.Container(
                            content=ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(
                                                f"Ruta #{route['id']}",
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"Trabajador: {route.get('worker_name', 'Sin asignar')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                f"Estado: {route['status']}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                f"Cliente: {route.get('customer_name', 'N/A')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                f"Fecha: {route.get('created_at', 'N/A')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                        ],
                                        expand=True,
                                    ),
                                    ft.Container(
                                        content=ft.Icon(
                                            ft.Icons.VISIBILITY,
                                            color=ft.Colors.GREY_400,
                                            tooltip="Solo lectura",
                                        ),
                                        padding=ft.padding.all(8),
                                    ),
                                ]
                            ),
                            padding=ft.padding.all(16),
                        ),
                        elevation=1,
                    )
                    for route in routes
                ],
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def build_customers(self):
        customers = db_manager.get_customers()

        if not customers:
            return ft.Column(
                [
                    ft.Text("Gestión de Clientes", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=32),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.PERSON_OFF,
                                    size=64,
                                    color=ft.Colors.GREY_400,
                                ),
                                ft.Text(
                                    "No hay clientes registrados",
                                    size=18,
                                    color=ft.Colors.GREY_600,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    "Los clientes aparecerán aquí una vez que sean registrados",
                                    size=14,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=16,
                        ),
                        padding=ft.padding.all(40),
                        alignment=ft.alignment.center,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Gestión de Clientes", size=24, weight=ft.FontWeight.BOLD
                        ),
                        ft.Container(expand=True),
                    ]
                ),
                ft.Container(height=16),
                *[
                    ft.Card(
                        content=ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.PERSON, color=ft.Colors.BLUE),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                customer["name"],
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                customer["address"],
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                f"Teléfono: {customer.get('phone', 'N/A')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                f"Código: {customer.get('barcode', 'N/A')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                        ],
                                        expand=True,
                                        spacing=2,
                                    ),
                                    ft.Container(
                                        content=ft.Icon(
                                            ft.Icons.VISIBILITY,
                                            color=ft.Colors.GREY_400,
                                            tooltip="Solo lectura",
                                        ),
                                        padding=ft.padding.all(8),
                                    ),
                                ]
                            ),
                            padding=ft.padding.all(16),
                        ),
                        elevation=1,
                    )
                    for customer in customers
                ],
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def build_sales(self):
        sales = db_manager.get_sales()

        if not sales:
            return ft.Column(
                [
                    ft.Text("Reporte de Ventas", size=24, weight=ft.FontWeight.BOLD),
                    ft.Container(height=32),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.SHOPPING_CART_OUTLINED,
                                    size=64,
                                    color=ft.Colors.GREY_400,
                                ),
                                ft.Text(
                                    "No hay ventas registradas",
                                    size=18,
                                    color=ft.Colors.GREY_600,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    "Las ventas aparecerán aquí una vez que se realicen entregas",
                                    size=14,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=16,
                        ),
                        padding=ft.padding.all(40),
                        alignment=ft.alignment.center,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )

        return ft.Column(
            [
                ft.Text("Reporte de Ventas", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(height=16),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Resumen del Día",
                                    size=18,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.Divider(),
                                ft.Row(
                                    [
                                        ft.Text("Ventas totales:", expand=True),
                                        ft.Text(
                                            f"${sum(sale.get('amount', 0) for sale in sales):.2f}",
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    [
                                        ft.Text("Bolsas vendidas:", expand=True),
                                        ft.Text(
                                            f"{sum(sale.get('quantity', 0) for sale in sales)}",
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ]
                                ),
                                ft.Row(
                                    [
                                        ft.Text("Clientes atendidos:", expand=True),
                                        ft.Text(
                                            f"{len(sales)}", weight=ft.FontWeight.BOLD
                                        ),
                                    ]
                                ),
                            ],
                            spacing=8,
                        ),
                        padding=ft.padding.all(16),
                    ),
                    elevation=2,
                ),
                ft.Container(height=16),
                ft.Text("Ventas Recientes", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                *[
                    ft.Card(
                        content=ft.Container(
                            content=ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(
                                                sale.get("customer_name", "Cliente"),
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"Cantidad: {sale.get('quantity', 0)} bolsas",
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                sale.get("date", ""),
                                                color=ft.Colors.GREY_600,
                                            ),
                                        ],
                                        expand=True,
                                        spacing=2,
                                    ),
                                    ft.Text(
                                        f"${sale.get('amount', 0):.2f}",
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ]
                            ),
                            padding=ft.padding.all(12),
                        ),
                        elevation=1,
                    )
                    for sale in sales
                ],
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def build_workers(self):
        workers = db_manager.get_workers()
        if not workers:
            return ft.Column(
                [
                    ft.Text(
                        "Gestión de Trabajadores", size=24, weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(height=32),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(
                                    ft.Icons.WORK_OFF,
                                    size=64,
                                    color=ft.Colors.GREY_400,
                                ),
                                ft.Text(
                                    "No hay trabajadores registrados",
                                    size=18,
                                    color=ft.Colors.GREY_600,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                ft.Text(
                                    "Los trabajadores aparecerán aquí una vez que sean registrados",
                                    size=14,
                                    color=ft.Colors.GREY_500,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=16,
                        ),
                        padding=ft.padding.all(40),
                        alignment=ft.alignment.center,
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
            )
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Gestión de Trabajadores",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(expand=True),
                    ]
                ),
                ft.Container(height=16),
                *[
                    ft.Card(
                        content=ft.Container(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.WORK, color=ft.Colors.GREEN),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                worker["name"],
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"Email: {worker.get('email', 'N/A')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                f"Teléfono: {worker.get('phone', 'N/A')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                            ft.Text(
                                                f"Rol: {worker.get('role', 'N/A')}",
                                                color=ft.Colors.GREY_600,
                                            ),
                                        ],
                                        expand=True,
                                        spacing=2,
                                    ),
                                    ft.Container(
                                        content=ft.Icon(
                                            ft.Icons.VISIBILITY,
                                            color=ft.Colors.GREY_400,
                                            tooltip="Solo lectura",
                                        ),
                                        padding=ft.padding.all(8),
                                    ),
                                ]
                            ),
                            padding=ft.padding.all(16),
                        ),
                        elevation=1,
                    )
                    for worker in workers
                ],
            ],
            scroll=ft.ScrollMode.AUTO,
        )

    def show_success_message(self, message):
        snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.GREEN)
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()

    def build(self):
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        f"Admin - {self.user['name']}",
                        size=18,
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
            padding=ft.padding.all(16),
            bgcolor=ft.Colors.ORANGE_50,
        )

        self.content_area = ft.Container(
            expand=True,
            padding=ft.padding.only(
                left=16, right=16, top=16, bottom=80
            ),  # Added bottom padding
        )

        bottom_nav = ft.Container(
            content=ft.NavigationBar(
                destinations=[
                    ft.NavigationBarDestination(
                        icon=ft.Icons.DASHBOARD, label="Dashboard"
                    ),
                    ft.NavigationBarDestination(icon=ft.Icons.ROUTE, label="Rutas"),
                    ft.NavigationBarDestination(
                        icon=ft.Icons.WORK, label="Trabajadores"
                    ),
                    ft.NavigationBarDestination(icon=ft.Icons.PEOPLE, label="Clientes"),
                    ft.NavigationBarDestination(
                        icon=ft.Icons.SHOPPING_CART, label="Ventas"
                    ),
                ],
                on_change=self.nav_changed,
            ),
            bgcolor=ft.Colors.WHITE,
            border=ft.border.only(top=ft.BorderSide(1, ft.Colors.GREY_300)),
        )

        self.update_content()

        return ft.Stack(
            [
                # Main content
                ft.Column(
                    [
                        header,
                        self.content_area,
                    ],
                    expand=True,
                    spacing=0,
                ),
                ft.Container(
                    content=bottom_nav,
                    alignment=ft.alignment.bottom_center,
                    left=0,
                    right=0,
                    bottom=0,
                ),
            ],
            expand=True,
        )

    def nav_changed(self, e):
        selected_index = e.control.selected_index
        if selected_index == 0:
            self.show_overview()
        elif selected_index == 1:
            self.show_routes()
        elif selected_index == 2:
            self.show_workers()
        elif selected_index == 3:
            self.show_customers()
        elif selected_index == 4:
            self.show_sales()


class IceDeliveryApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Ice Delivery Mobile"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.adaptive = True
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
    page.theme_mode = ft.ThemeMode.LIGHT
    app = IceDeliveryApp(page)

    # === SYNC AUTOMATICA AL INICIAR ===
    def auto_sync():
        result = sync_if_needed()
        if result:
            print(f"Sync automatica: {result}")
            # Actualizar UI si es necesario
            page.update()

    # Ejecutar sync en background para no bloquear la UI
    threading.Thread(target=auto_sync, daemon=True).start()


if __name__ == "__main__":
    print("📱 Iniciando Ice Delivery Mobile App...")
    ft.app(target=main)
