#!/bin/bash
echo "🚀 Iniciando Ice Delivery App..."
echo "🌐 La aplicación se abrirá en tu navegador web"
echo "🌐 URL: http://127.0.0.1:8080"
echo ""
echo "👤 Credenciales de prueba:"
echo "   Admin: admin / admin123"
echo "   Worker: worker1 / worker123"
echo ""
echo "⚡ Presiona Ctrl+C para detener la aplicación"
echo ""

cd "$(dirname "$0")"
poetry run python src/main.py --web
