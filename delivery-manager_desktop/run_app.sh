#!/bin/bash
echo "🚀 Iniciando Ice Delivery App..."
echo "🖥️ La aplicación se abrirá en una ventana de escritorio"
echo ""
echo "👤 Credenciales de prueba:"
echo "   Admin: admin / admin123"
echo "   Worker: worker1 / worker123"
echo ""
echo "💡 Opciones disponibles:"
echo "   --desktop: Forzar modo ventana de escritorio"
echo "   --web: Forzar modo navegador web"
echo ""
echo "⚡ Presiona Ctrl+C para detener la aplicación"
echo ""

cd "$(dirname "$0")"
poetry run python src/main.py --desktop
