FROM python:3.12-slim

# Instalar uv
ENV UV_SYSTEM=1
RUN pip install uv

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencia
COPY pyproject.toml ./

# Instalar dependencias
RUN uv sync

# Copiar código fuente
COPY . .

# Exponer puerto
EXPOSE 9000

# Comando para ejecutar
CMD ["uv", "run", "python", "main.py"]