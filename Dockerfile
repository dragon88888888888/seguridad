FROM python:3.12.5

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt primero para aprovechar la cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Crear directorios de datos si no existen
RUN mkdir -p /app/data

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV TIMEOUT=300
ENV WORKERS=1
ENV WORKER_CLASS=gthread
ENV THREADS=4

# Exponer puerto
EXPOSE 8080

# Comando para iniciar la aplicación con timeouts ajustados
CMD gunicorn --bind 0.0.0.0:$PORT \
    --timeout $TIMEOUT \
    --workers $WORKERS \
    --worker-class $WORKER_CLASS \
    --threads $THREADS \
    --log-level info \
    --preload \
    app:app