# 🧊 Ice Delivery Manager App

Sistema completo de gestión de entregas de hielo desarrollado con Flet y PostgreSQL.

## 🚀 Características

### Para Administradores:
- 📊 **Dashboard Administrativo**: Vista general con estadísticas y métricas
- 👥 **Gestión de Clientes**: Agregar, editar y visualizar clientes
- 🏢 **Gestión de Trabajadores**: Administrar empleados y sus credenciales
- 🚛 **Gestión de Camiones**: Control de flota vehicular y asignaciones
- 💰 **Registro de Ventas**: Historial completo de todas las transacciones
- 📈 **Reportes**: Análisis de ventas por períodos (semanal/mensual)

### Para Trabajadores:
- 🗺️ **Rutas de Entrega**: Visualización de rutas asignadas con clientes
- 📦 **Registro de Entregas**: Captura rápida de bolsas entregadas por cliente
- 📱 **Escáner de Códigos**: Simulación de escaneo de códigos de barras
- 🧾 **Generación de Tickets**: Creación de comprobantes de venta
- 🚚 **Mi Camión**: Información del vehículo asignado y reportes de estado

## Configuración de Base de Datos

El sistema soporta PostgreSQL y SQLite como fallback. Configura las variables de entorno en `.env`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=erickmarin
DB_USER=erickmarin
DB_PASSWORD=erick123
```

## 🛠️ Instalación y Configuración

### Prerrequisitos
- Python 3.9 o superior
- Poetry (gestor de dependencias)
- PostgreSQL (opcional - incluye modo fallback)

### Instalación

1. **Instalar dependencias con Poetry**:
   ```bash
   poetry install
   ```

2. **Configurar base de datos** (opcional):
   ```bash
   # Copiar archivo de configuración
   cp .env.example .env
   
   # Editar .env con tus credenciales de PostgreSQL
   nano .env
   ```

### Ejecutar la aplicación

**Método recomendado - Aplicación de Escritorio**:
```bash
# Con Poetry (modo desktop forzado)
poetry run python src/main.py --desktop

# Con script incluido (modo desktop)
./run_app.sh
```

**Otros métodos**:
```bash
# Modo web
poetry run python src/main.py --web
./run_app_web.sh

# Detección automática de entorno
poetry run python src/main.py

# Con Flet CLI
poetry run flet run
poetry run flet run --web
```

### Acceso a la Aplicación
1. La aplicación se ejecuta en modo web en `http://127.0.0.1:8080`
2. Se abrirá automáticamente en tu navegador web
3. Si no se abre automáticamente, visita manualmente la URL

## 👤 Credenciales de Prueba

- **Administrador**: 
  - Usuario: `admin`
  - Contraseña: `admin123`
  
- **Trabajador**: 
  - Usuario: `worker1`
  - Contraseña: `worker123`

## 📱 Cómo Usar la Aplicación

### Funcionalidades del Administrador:
1. **Dashboard**: Visualiza métricas generales del negocio
2. **Gestión de Clientes**: 
   - Hacer clic en "Agregar Cliente"
   - Completar formulario con datos del cliente
3. **Gestión de Trabajadores**:
   - Agregar nuevos empleados con credenciales
   - Ver lista de trabajadores activos
4. **Gestión de Camiones**:
   - Registrar nuevos vehículos
   - Asignar camiones a trabajadores
   - Monitorear estado de la flota

### Funcionalidades del Trabajador:
1. **Rutas**: Ver clientes asignados en tu ruta
2. **Entregas**: 
   - Hacer clic en el ícono de entrega junto a cada cliente
   - Ingresar número de bolsas entregadas
   - Confirmar la entrega
3. **Mi Camión**: Ver información del vehículo asignado
4. **Reportes**: Generar reportes de problemas o solicitar mantenimiento

## 🔧 Solución de Problemas

### ❌ La aplicación no se abre en el navegador
- **Problema**: No tienes navegador instalado
- **Solución**: Instala Firefox: `sudo apt install firefox`
- **Alternativa**: Abre manualmente `http://127.0.0.1:8080` en cualquier navegador

### ❌ Error: ModuleNotFoundError: No module named 'database'
- **Problema**: El módulo database.py no existe o no se puede importar
- **Solución**: Ya está resuelto - el archivo `src/database.py` está incluido

### ❌ Error de conexión a la base de datos
- **Problema**: PostgreSQL no está configurado
- **Solución**: La app funciona en modo fallback con SQLite automáticamente
- **Para usar PostgreSQL**: Verifica que el servicio esté corriendo y las credenciales sean correctas

### ❌ Error al instalar dependencias
- **Problema**: Versión de Python incompatible
- **Solución**: Asegúrate de tener Python 3.9 o superior

## 📝 Estructura del Proyecto

```
FLET_python/
├── src/
│   ├── main.py          # Aplicación principal
│   └── database.py      # Gestor de base de datos
├── pyproject.toml       # Configuración de Poetry
├── .env.example         # Plantilla de variables de entorno
├── run_app.sh          # Script para ejecutar la app
└── README.md           # Este archivo
```

## Construcción de la aplicación

### Android

```bash
flet build apk -v
```

### iOS

```bash
flet build ipa -v
```

### Windows

```bash
flet build windows -v
```

### Linux

```bash
flet build linux -v
```

### macOS

```bash
flet build macos -v
```

Para más detalles sobre la construcción, consulta la [documentación de Flet](https://flet.dev/docs/).
