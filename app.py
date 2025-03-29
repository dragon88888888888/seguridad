from flask import Flask, render_template, jsonify, request
import json
import os
import threading
import time
from datetime import datetime, timedelta
import logging
import traceback

# Importamos el grafo de LangGraph
try:
    from gguard import graph, State, supervisor_agent, scraper_agent, router_agent, reporter_agent
except ImportError:
    print("No se pudo importar LangGraph. Asegúrate de tener el archivo langgraph_security.py en el mismo directorio.")

# Configuración de logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("app.log"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Almacenamiento para datos históricos
HISTORICAL_DATA_FILE = "historical_data.json"
CURRENT_DATA_FILE = "security_data.json"
UPDATE_INTERVAL = 600  # 10 minutos en segundos

# Estructura para almacenar datos actuales e históricos
current_data = {
    "timestamp": "",
    "incidents": [],
    "main_incident": {},
    "analysis": {},
    "recommendations": [],
    "reports": {}
}

historical_data = []

# Función para cargar datos históricos
def load_historical_data():
    global historical_data
    try:
        if os.path.exists(HISTORICAL_DATA_FILE):
            with open(HISTORICAL_DATA_FILE, 'r', encoding='utf-8') as f:
                historical_data = json.load(f)
            logger.info(f"Datos históricos cargados: {len(historical_data)} registros")
        else:
            historical_data = []
            logger.info("No hay archivo de datos históricos, se inicia con lista vacía")
    except Exception as e:
        logger.error(f"Error al cargar datos históricos: {str(e)}")
        historical_data = []

# Función para guardar datos históricos
def save_historical_data():
    try:
        with open(HISTORICAL_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(historical_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Datos históricos guardados: {len(historical_data)} registros")
    except Exception as e:
        logger.error(f"Error al guardar datos históricos: {str(e)}")

# Función para cargar datos actuales
def load_current_data():
    global current_data
    try:
        if os.path.exists(CURRENT_DATA_FILE):
            with open(CURRENT_DATA_FILE, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
            logger.info(f"Datos actuales cargados, timestamp: {current_data.get('timestamp', 'desconocido')}")
        else:
            logger.warning("No hay archivo de datos actuales")
    except Exception as e:
        logger.error(f"Error al cargar datos actuales: {str(e)}")

# Función para ejecutar el grafo de LangGraph
def run_langgraph_analysis():
    try:
        logger.info("Iniciando análisis con LangGraph...")
        initial_state = {"start_signal": "Y", "raw_data": None, "all_incidents": []}
        result = graph.invoke(initial_state)
        logger.info("Análisis con LangGraph completado")
        
        # Cargar los datos generados por LangGraph
        load_current_data()
        
        # Añadir datos actuales al historial evitando duplicados
        if current_data and current_data.get("timestamp") and current_data.get("incidents"):
            # Verificar si los incidentes son realmente nuevos (no solo por timestamp)
            is_new_data = True
            
            # Crear un conjunto de "huellas digitales" de incidentes actuales
            current_incident_signatures = set()
            for incident in current_data.get("incidents", []):
                # Garantizar que todos los valores son strings antes de usar slicing
                titulo = str(incident.get('titulo', '')) if incident.get('titulo') is not None else ''
                lugar = str(incident.get('lugar', '')) if incident.get('lugar') is not None else ''
                tipo = str(incident.get('tipo', '')) if incident.get('tipo') is not None else ''
                
                # Crear una firma única combinando título, lugar y tipo
                # Garantizar que todos los valores son strings antes de usar slicing
                titulo = str(incident.get('titulo', '')) if incident.get('titulo') is not None else ''
                lugar = str(incident.get('lugar', '')) if incident.get('lugar') is not None else ''
                tipo = str(incident.get('tipo', '')) if incident.get('tipo') is not None else ''
                                
                # Crear una firma única combinando título, lugar y tipo
                signature = f"{titulo[:50]}|{lugar[:30]}|{tipo}"
                current_incident_signatures.add(signature)
            
            # Verificar los últimos 3 registros históricos para evitar duplicados recientes
            for recent_entry in historical_data[:3]:
                recent_signatures = set()
                for incident in recent_entry.get("incidents", []):
                    titulo = str(incident.get('titulo', '')) if incident.get('titulo') is not None else ''
                    lugar = str(incident.get('lugar', '')) if incident.get('lugar') is not None else ''
                    tipo = str(incident.get('tipo', '')) if incident.get('tipo') is not None else ''
                                    
                    # Crear una firma única combinando título, lugar y tipo
                    signature = f"{titulo[:50]}|{lugar[:30]}|{tipo}"
                    recent_signatures.add(signature)
                
                # Si más del 80% de los incidentes son iguales, considerar como duplicado
                if recent_signatures and len(current_incident_signatures.intersection(recent_signatures)) / len(current_incident_signatures) > 0.8:
                    is_new_data = False
                    logger.info("Datos similares ya existen en el historial reciente, no se añadirán")
                    break
            
            # Si son datos nuevos, añadirlos al historial
            if is_new_data:
                historical_data.insert(0, current_data.copy())  # Añadir al principio (más reciente)
                # Mantener solo los últimos 100 registros para evitar que el archivo crezca demasiado
                if len(historical_data) > 100:
                    historical_data.pop()
                save_historical_data()
                logger.info("Nuevos datos añadidos al historial")
        
        return True
    except Exception as e:
        logger.error(f"Error al ejecutar LangGraph: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# Función para actualización periódica
def periodic_update():
    while True:
        try:
            logger.info("Iniciando actualización periódica...")
            run_langgraph_analysis()
            logger.info(f"Actualización completada. Próxima actualización en {UPDATE_INTERVAL} segundos")
            time.sleep(UPDATE_INTERVAL)
        except Exception as e:
            logger.error(f"Error en actualización periódica: {str(e)}")
            logger.error(traceback.format_exc())
            time.sleep(60)  # Esperar un minuto antes de reintentar en caso de error

from datetime import datetime, timedelta
import uuid

# Variables globales adicionales
CITIZEN_REPORTS_FILE = "citizen_reports.json"
citizen_reports = []

# Función para cargar reportes ciudadanos
def load_citizen_reports():
    global citizen_reports
    try:
        if os.path.exists(CITIZEN_REPORTS_FILE):
            with open(CITIZEN_REPORTS_FILE, 'r', encoding='utf-8') as f:
                citizen_reports = json.load(f)
            
            # Filtrar solo reportes de las últimas 24 horas
            one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
            citizen_reports = [report for report in citizen_reports if report.get("timestamp", "") >= one_day_ago]
            
            logger.info(f"Reportes ciudadanos cargados: {len(citizen_reports)} reportes")
        else:
            citizen_reports = []
            logger.info("No hay archivo de reportes ciudadanos, se inicia con lista vacía")
    except Exception as e:
        logger.error(f"Error al cargar reportes ciudadanos: {str(e)}")
        citizen_reports = []

# Función para guardar reportes ciudadanos
def save_citizen_reports():
    try:
        with open(CITIZEN_REPORTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(citizen_reports, f, ensure_ascii=False, indent=2)
        logger.info(f"Reportes ciudadanos guardados: {len(citizen_reports)} reportes")
    except Exception as e:
        logger.error(f"Error al guardar reportes ciudadanos: {str(e)}")

# Añadir esta función a la inicialización de la aplicación
def initialize_app():
    # Código existente...
    load_historical_data()
    load_current_data()
    load_citizen_reports()  # Cargar reportes ciudadanos
    
    # Iniciar hilo de actualización periódica
    update_thread = threading.Thread(target=periodic_update, daemon=True)
    update_thread.start()
    logger.info("Hilo de actualización periódica iniciado")
    
# Rutas de la aplicación Flask
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/security_data', methods=['GET'])
def get_security_data():
    load_current_data()
    
    # Si no hay datos actuales o están vacíos, usar el más reciente del historial
    if not current_data or not current_data.get("incidents"):
        logger.info("No hay datos actuales, usando datos del historial")
        if historical_data and len(historical_data) > 0:
            return jsonify(historical_data[0])  # Devolver el más reciente
    
    return jsonify(current_data)

@app.route('/api/latest_news', methods=['GET'])
def get_latest_news():
    """Devuelve las últimas 3 noticias del historial combinado"""
    # Cargar datos actuales y históricos
    load_current_data()
    
    # Combinar incidentes actuales con históricos
    all_incidents = []
    
    # Añadir incidentes actuales si existen
    if current_data and current_data.get("incidents"):
        all_incidents.extend(current_data.get("incidents"))
    
    # Añadir incidentes históricos
    for entry in historical_data[:5]:  # Revisar en los últimos 5 registros históricos
        if entry and entry.get("incidents"):
            for incident in entry.get("incidents"):
                # Comprobar si este incidente ya está en la lista (evitar duplicados)
                is_duplicate = False
                for existing in all_incidents:
                    if (existing.get("titulo") == incident.get("titulo") or 
                        (existing.get("lugar") == incident.get("lugar") and 
                         existing.get("tipo") == incident.get("tipo"))):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    all_incidents.append(incident)
    
    # Ordenar por fecha (si está disponible) y tomar los 3 más recientes
    try:
        # Intentar ordenar por fecha, pero podría fallar si los formatos no son consistentes
        all_incidents.sort(key=lambda x: x.get("fecha_incidente", ""), reverse=True)
    except:
        # Si falla, no ordenar
        pass
    
    latest_three = all_incidents[:3]
    
    return jsonify({
        "latest_news": latest_three,
        "total_count": len(all_incidents)
    })

@app.route('/api/historical_data', methods=['GET'])
def get_historical_data():
    days = request.args.get('days', default=7, type=int)
    
    # Filtrar datos por fecha
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    filtered_data = [item for item in historical_data if item.get("timestamp", "") >= cutoff_date]
    
    return jsonify(filtered_data)

@app.route('/api/incident_types', methods=['GET'])
def get_incident_types():
    # Conteo de tipos de incidentes desde los datos históricos
    incident_types = {}
    for data in historical_data:
        for incident in data.get("incidents", []):
            incident_type = incident.get("tipo", "desconocido")
            if incident_type in incident_types:
                incident_types[incident_type] += 1
            else:
                incident_types[incident_type] = 1
    
    return jsonify(incident_types)

@app.route('/api/heatmap_data', methods=['GET'])
def get_heatmap_data():
    # Datos para el mapa de calor (todas las coordenadas)
    heatmap_points = []
    for data in historical_data:
        for incident in data.get("incidents", []):
            coords = incident.get("coordenadas")
            if coords and coords.get("lat") and coords.get("lng"):
                # Añadir intensidad basada en la gravedad
                intensity = 1
                if incident.get("gravedad") == "alta":
                    intensity = 1.5
                elif incident.get("gravedad") == "crítica":
                    intensity = 2.0
                
                heatmap_points.append({
                    "lat": coords.get("lat"),
                    "lng": coords.get("lng"),
                    "intensity": intensity
                })
    
    return jsonify(heatmap_points)

@app.route('/api/trigger_update', methods=['POST'])
def trigger_update():
    success = run_langgraph_analysis()
    return jsonify({"success": success})

# Inicialización
def initialize_app():
    # Cargar datos existentes
    load_historical_data()
    load_current_data()
    
    # Iniciar hilo de actualización periódica
    update_thread = threading.Thread(target=periodic_update, daemon=True)
    update_thread.start()
    logger.info("Hilo de actualización periódica iniciado")


@app.route('/report')
def report():
    # Página para reportes ciudadanos
    return render_template('report.html')

@app.route('/api/citizen-reports', methods=['GET'])
def get_citizen_reports():
    # API para obtener reportes ciudadanos
    # Opcional: Filtrar por período de tiempo
    days = request.args.get('days', default=1, type=int)
    
    if days > 0:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        filtered_reports = [report for report in citizen_reports if report.get("timestamp", "") >= cutoff_date]
    else:
        filtered_reports = citizen_reports
    
    return jsonify(filtered_reports)

@app.route('/api/citizen-reports', methods=['POST'])
def add_citizen_report():
    # API para añadir un nuevo reporte ciudadano
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data or not isinstance(data, dict):
            return jsonify({"success": False, "error": "Datos inválidos"}), 400
        
        required_fields = ["description", "latitude", "longitude"]
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Campo requerido: {field}"}), 400
        
        # Crear reporte
        new_report = {
            "id": str(uuid.uuid4())[:8],  # ID único corto
            "timestamp": datetime.now().isoformat(),
            "description": data["description"],
            "tipo": data.get("incident_type", "reporte_ciudadano"),
            "coordenadas": {
                "lat": data["latitude"],
                "lng": data["longitude"]
            },
            "lugar": data.get("location_name", "Ubicación reportada por ciudadano"),
            "source": "citizen",
            "verified": False
        }
        
        # Añadir campos opcionales si están presentes
        optional_fields = ["name", "contact", "severity", "images"]
        for field in optional_fields:
            if field in data:
                new_report[field] = data[field]
        
        # Guardar reporte
        citizen_reports.append(new_report)
        save_citizen_reports()
        
        return jsonify({
            "success": True,
            "message": "Reporte guardado correctamente",
            "report_id": new_report["id"]
        })
    
    except Exception as e:
        logger.error(f"Error al guardar reporte ciudadano: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/all-incidents', methods=['GET'])
def get_all_incidents():
    # Combinar incidentes del sistema con reportes ciudadanos para visualización en mapa
    load_citizen_reports()
    # Cargar datos actuales
    load_current_data()
    
    # Inicializar lista combinada
    all_incidents = []
    
    # Añadir incidentes del sistema
    system_incidents = []
    if current_data and "incidents" in current_data:
        system_incidents = current_data.get("incidents", [])
    
    # Añadir incidentes del historial (últimas 24 horas)
    one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
    for entry in historical_data:
        if entry.get("timestamp", "") >= one_day_ago and "incidents" in entry:
            for incident in entry.get("incidents", []):
                # Verificar si es un incidente nuevo (no duplicado)
                is_new = True
                for existing in system_incidents:
                    if (existing.get("titulo") == incident.get("titulo") and 
                        existing.get("lugar") == incident.get("lugar")):
                        is_new = False
                        break
                
                if is_new:
                    system_incidents.append(incident)
    
    # Preparar todos los incidentes del sistema
    for incident in system_incidents:
        if incident.get("coordenadas") and incident["coordenadas"].get("lat") and incident["coordenadas"].get("lng"):
            all_incidents.append({
                "id": incident.get("id", str(uuid.uuid4())[:8]),
                "title": incident.get("titulo") or incident.get("noticia") or "Incidente sin título",
                "description": incident.get("resumen") or "Sin descripción",
                "type": incident.get("tipo") or incident.get("tipo_incidente") or "desconocido",
                "location": incident.get("lugar") or "Ubicación no especificada",
                "timestamp": incident.get("fecha_incidente") or datetime.now().strftime("%d/%m/%Y"),
                "time": incident.get("hora_incidente") or "",
                "severity": incident.get("gravedad") or "media",
                "coordinates": incident["coordenadas"],
                "source": "system",
                "url": incident.get("url", "")
            })
    
    # Añadir reportes ciudadanos
    for report in citizen_reports:
        if report.get("coordenadas") and report["coordenadas"].get("lat") and report["coordenadas"].get("lng"):
            all_incidents.append({
                "id": report.get("id", str(uuid.uuid4())[:8]),
                "title": "Reporte ciudadano: " + report.get("tipo", "Incidente").replace("_", " ").title(),
                "description": report.get("description") or "Sin descripción",
                "type": report.get("tipo") or "reporte_ciudadano",
                "location": report.get("lugar") or "Ubicación reportada por ciudadano",
                "timestamp": datetime.fromisoformat(report.get("timestamp")).strftime("%d/%m/%Y") if report.get("timestamp") else datetime.now().strftime("%d/%m/%Y"),
                "time": "",
                "severity": report.get("severity") or "media",
                "coordinates": report["coordenadas"],
                "source": "citizen",
                "verified": report.get("verified", False),
                "reporter_name": report.get("name", "Anónimo")
            })
    
    return jsonify(all_incidents)

if __name__ == '__main__':
    initialize_app()
    # Si no existen datos actuales, ejecutar LangGraph una vez al inicio
    if not current_data.get("timestamp"):
        run_langgraph_analysis()
    
    app.run(debug=True, use_reloader=False)  # Desactivar reloader para evitar duplicar hilos