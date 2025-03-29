# langgraph_security.py
# Este módulo adapta el código de LangGraph original para su uso con Flask

import os
import json
import re
import requests
import time
from datetime import datetime
from typing import TypedDict, Dict, List, Optional, Annotated
import logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.tools.tavily_search import TavilySearchResults

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Estado del subgrafo
class SubgraphState(TypedDict):
    iteration: int
    urgency: Optional[str]
    incident_type: Annotated[Optional[str], "merge"]
    coordinates: Annotated[Optional[Dict[str, float]], "merge"]
    analysis: Optional[Dict]
    confidence: Optional[float]
    predictions: Optional[Dict]
    recommendations: Optional[List[str]]
    incident_data: Optional[Dict]

# Estado del grafo principal
class State(TypedDict):
    start_signal: str
    raw_data: Optional[List[Dict]]
    urgency: Optional[str]
    incident_type: Optional[str]
    coordinates: Optional[Dict[str, float]]
    analysis: Optional[Dict]
    confidence: Optional[float]
    predictions: Optional[Dict]
    recommendations: Optional[List[str]]
    reports: Optional[Dict]
    incident_data: Optional[Dict]
    all_incidents: Optional[List[Dict]]

# Inicializar el LLM
def initialize_llm(temperature=0.7):
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("La clave de la API de Google no está definida")
    
    return ChatGoogleGenerativeAI(
        google_api_key=google_api_key,
        model="gemini-2.0-flash-lite",
        temperature=temperature
    )

# Limpiar respuesta del LLM
def clean_llm_response(response_text):
    return re.sub(r'```json\s*|\s*```', '', response_text).strip()

# Extraer contenido del artículo
def extract_article_content(soup):
    # Extraer párrafos
    paragraphs = soup.find_all('p')
    if paragraphs:
        valid_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        if valid_paragraphs:
            return " ".join(valid_paragraphs)
    
    # Extraer del artículo
    article = soup.find('article')
    if article:
        for tag in article.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        return article.get_text(separator=' ', strip=True)
    
    # Extraer del div principal
    main_content = soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'article' in x.lower()))
    if main_content:
        for tag in main_content.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        return main_content.get_text(separator=' ', strip=True)
    
    return ""

# Consultar el LLM
def query_llm(prompt, temperature=0.7):
    llm = initialize_llm(temperature)
    response = llm.invoke([HumanMessage(content=prompt)])
    cleaned_response = clean_llm_response(response.content)
    
    try:
        return json.loads(cleaned_response)
    except json.JSONDecodeError:
        return {"error": "No se pudo parsear la respuesta", "text": cleaned_response}

# Geocodificar un lugar usando OpenCage
def geocode_location(place):
    """Geocodifica una ubicación en Querétaro."""
    if not place or place == "No especificado":
        return None, None
        
    # Asegurarse de que estamos trabajando con una cadena
    if isinstance(place, list):
        place = place[0] if place else "No especificado"
    
    # Asegurarse de que el contexto sea Querétaro, México
    if "Querétaro" not in place:
        query = f"{place}, Querétaro, México"
    else:
        query = f"{place}, México"
    
    try:
        api_key = os.getenv("OPENCAGE_API_KEY", "0cd277781a214ffc99f6fac5f756f680")
        encoded_query = requests.utils.quote(query)
        url = f"https://api.opencagedata.com/geocode/v1/json?q={encoded_query}&key={api_key}&language=es&limit=1"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if response.status_code == 200 and data.get("results") and len(data["results"]) > 0:
            result = data["results"][0]
            logger.info(f"Geocodificación exitosa para '{place}'")
            return result["geometry"]["lat"], result["geometry"]["lng"]
        
        logger.warning(f"No se encontraron resultados de geocodificación para '{place}'")
        return None, None
    
    except Exception as e:
        logger.error(f"Error geocodificando '{place}': {e}")
        return None, None

# --- Agentes del grafo principal ---

def supervisor_agent(state: State) -> State:
    """Monitorea la salud del sistema y supervisa agentes clave."""
    logger.info("Supervisor Agent: Iniciando supervisión del sistema...")
    
    # Verificar variables de entorno necesarias
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("API Key de Google no encontrada")
        raise ValueError("API Key de Google no configurada")
    
    # Verificar conectividad
    try:
        requests.get("https://www.google.com", timeout=5)
    except:
        logger.error("No hay conexión a internet")
        raise ConnectionError("No se puede conectar a internet")
    
    # Inicializar lista para almacenar todos los incidentes procesados
    state["all_incidents"] = []
    
    return state

def scraper_agent(state: State) -> State:
    """Monitorea noticias de seguridad usando Tavily Search API."""
    logger.info("Scraper Agent: Recolectando datos de noticias con Tavily...")
    
    try:
        # Inicializar Tavily Search
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            raise ValueError("La clave de API de Tavily no está definida")
        
        tavily_search = TavilySearchResults(
            api_key=tavily_api_key,
            max_results=5,
            search_depth="advanced"
        )
        
        # Realizar búsqueda específica para noticias recientes de policía en Querétaro
        search_query = "noticias recientes policía Querétaro últimas 24 horas seguridad"
        
        search_results = tavily_search.invoke({
            "query": search_query,
            "max_results": 5
        })
        
        # Preparar lista para almacenar noticias procesadas
        news_data = []
        
        # Procesar cada resultado de la búsqueda
        for idx, result in enumerate(search_results):
            try:
                title = result.get("title", "Noticia sin título")
                url = result.get("url", "")
                snippet = result.get("content", "")
                                
                
                logger.info(f"Procesando artículo: {title}")
                
                # Hacer solicitud al artículo para obtener contenido completo
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                article_response = requests.get(url, headers=headers, timeout=15)
                article_soup = BeautifulSoup(article_response.content, 'html.parser')
                
                # Extraer fecha de publicación
                date_elem = article_soup.find('span', class_=lambda x: x and 'Typography' in x)
                date_text = date_elem.get_text(strip=True) if date_elem else "Fecha no encontrada"
                
                # Extraer contenido completo
                content = extract_article_content(article_soup)
                
                # Si el contenido es muy corto, usar el snippet de Tavily
                if len(content) < 100:
                    content = snippet
                    
                # Extraer datos estructurados utilizando LLM con contexto enriquecido
                structured_data_prompt = f"""
                Analiza esta noticia policiaca de Querétaro, México y extrae información precisa sobre el incidente principal.
                
                TÍTULO: {title}
                FECHA DE PUBLICACIÓN: {date_text}
                URL: {url}
                
                CONTENIDO:
                {content}
                
                Extrae EXCLUSIVAMENTE un único incidente principal con los siguientes datos exactos:
                1. lugar_exacto: Ubicación específica donde ocurrió el incidente (nombre exacto de colonia, calle o punto de referencia)
                2. fecha_incidente: Fecha del incidente (formato DD/MM/YYYY si se menciona)
                3. hora_incidente: Hora aproximada (formato HH:MM si se menciona)
                4. tipo_incidente: Categoría precisa (homicidio, robo, secuestro, asalto, accidente vial, etc.)
                5. gravedad: Nivel de gravedad (baja, media, alta, crítica)
                6. resumen_conciso: Párrafo breve que resume el incidente principal
                7. impacto_vial: Si el incidente afecta alguna vialidad, nombra la vialidad específica o indica "ninguna"
                
                Responde ÚNICAMENTE en formato JSON con estos campos exactos. Extrae solo datos mencionados explícitamente.
                Si algún dato no está disponible, asigna null (no inventes datos ni uses "No especificado").
                """
                
                # Consultar al LLM con temperatura baja para mayor precisión
                details = query_llm(structured_data_prompt, temperature=0.1)
                
                # Validar respuesta
                if not isinstance(details, dict):
                    logger.warning(f"Respuesta LLM no válida para {title}: {details}")
                    continue
                
                # Crear objeto de noticia con estructura simplificada
                news_item = {
                    "id": idx,
                    "noticia": title,
                    "url": url,
                    "fecha_publicacion": date_text,
                    "lugar": details.get("lugar_exacto"),
                    "fecha_incidente": details.get("fecha_incidente"),
                    "hora_incidente": details.get("hora_incidente"),
                    "tipo_incidente": details.get("tipo_incidente"),
                    "gravedad": details.get("gravedad"),
                    "resumen": details.get("resumen_conciso"),
                    "impacto_vial": details.get("impacto_vial"),
                    "contenido_completo": content
                }
                
                # Geocodificar inmediatamente para verificar validez del lugar
                lugar = details.get("lugar_exacto", "")
                if lugar:
                    lat, lng = geocode_location(lugar)
                    if lat and lng:
                        logger.info(f"Geocodificación exitosa para {lugar}: {lat}, {lng}")
                    else:
                        logger.warning(f"No se pudo geocodificar {lugar}")
                
                news_data.append(news_item)
                logger.info(f"Scraper Agent: Extraída noticia #{idx} - '{title}' - Lugar: {news_item['lugar']}")
                
            except Exception as e:
                logger.error(f"Scraper Agent: Error al procesar artículo: {str(e)}")
                continue
        
        # Guardar los datos
        state["raw_data"] = news_data
        
    except Exception as e:
        logger.error(f"Scraper Agent: Error general: {str(e)}")
        state["raw_data"] = []
    
    return state

def router_agent(state: State) -> State:
    """Enruta eventos según su urgencia y decide el siguiente paso."""
    logger.info("Router Agent: Evaluando datos para determinar urgencia...")
    
    if not state["raw_data"] or len(state["raw_data"]) == 0:
        logger.info("Router Agent: No hay datos para analizar, marcando como irrelevante")
        state["urgency"] = "irrelevant"
        return state
    
    # Preparar los datos de incidentes para el prompt
    incidents_data = []
    for incident in state["raw_data"]:
        # Crear versión limpia para el prompt
        incident_clean = {
            "id": incident.get("id", 0),
            "titulo": incident.get("noticia", ""),
            "lugar": incident.get("lugar", "No especificado"),
            "fecha": incident.get("fecha_incidente", "No especificada"),
            "hora": incident.get("hora_incidente", "No especificada"),
            "tipo": incident.get("tipo_incidente", "No especificado"),
            "gravedad": incident.get("gravedad", "No especificada"),
            "resumen": incident.get("resumen", "No disponible"),
            "impacto_vial": incident.get("impacto_vial", "No especificado")
        }
        incidents_data.append(incident_clean)
    
    # Verificar que haya datos a procesar
    if not incidents_data:
        logger.info("Router Agent: Datos vacíos después de limpieza, marcando como irrelevante")
        state["urgency"] = "irrelevant"
        return state
        
    # Mejorar el prompt para la selección de incidente
    routing_prompt = f"""
    Analiza estos {len(incidents_data)} incidentes de seguridad y selecciona el más urgente o relevante,
    priorizando aquellos que afectan vialidades o rutas de tránsito:
    
    {json.dumps(incidents_data, ensure_ascii=False)}
    
    CRITERIOS DE SELECCIÓN (por prioridad):
    1. Incidentes que afecten directamente vialidades (bloqueos, accidentes)
    2. Incidentes con impacto en la seguridad de conductores o transeúntes
    3. Gravedad del incidente
    4. Actualidad (fecha/hora reciente)
    
    Determina:
    1. El ID del incidente más urgente para vialidades (campo "id" de cada incidente)
    2. El nivel de urgencia (critical, high, standard, low, irrelevant)
    3. Justificación breve de tu selección
    
    Responde en JSON con campos: "selected_id", "urgency", "justification"
    """
    
    # Consultar al LLM
    result = query_llm(routing_prompt, temperature=0.2)
    
    # Extraer el ID seleccionado
    selected_id = result.get("selected_id", 0)
    
    # Encontrar el incidente correspondiente
    selected_incident = None
    for incident in state["raw_data"]:
        if incident.get("id", 0) == selected_id:
            selected_incident = incident
            break
    
    # Si no se encuentra, usar el primero
    if not selected_incident and state["raw_data"]:
        selected_incident = state["raw_data"][0]
        logger.warning(f"Router Agent: No se encontró incidente con ID {selected_id}, usando el primero")
    
    # Guardar el incidente seleccionado y su urgencia
    if selected_incident:
        state["incident_data"] = selected_incident
        state["urgency"] = result.get("urgency", "standard")
    else:
        logger.warning("Router Agent: No hay incidentes disponibles")
        state["incident_data"] = {}
        state["urgency"] = "irrelevant"
    
    # Procesar geocodificación para cada incidente individualmente
    processed_incidents = []
    for incident in state["raw_data"]:
        # Obtener lugar como cadena simple (no lista)
        lugar = incident.get("lugar", "No especificado")
        
        # Geocodificar el lugar
        lat, lng = geocode_location(lugar)
        
        # Crear versión procesada del incidente
        processed = {
            "titulo": incident.get("noticia", ""),
            "url": incident.get("url", ""),
            "lugar": lugar,
            "fecha": incident.get("fecha_incidente", ""),
            "hora": incident.get("hora_incidente", ""),
            "tipo": incident.get("tipo_incidente", ""),
            "gravedad": incident.get("gravedad", ""),
            "resumen": incident.get("resumen", ""),
            "impacto_vial": incident.get("impacto_vial", ""),
            "coordenadas": {"lat": lat, "lng": lng} if lat and lng else None
        }
        
        processed_incidents.append(processed)
        logger.info(f"Router Agent: Geocodificado lugar '{lugar}' -> {lat}, {lng}")
    
    # Guardar todos los incidentes procesados
    state["all_incidents"] = processed_incidents
    
    # Registrar la decisión
    logger.info(f"Router Agent: Seleccionado incidente ID {selected_id} con urgencia {state['urgency']}")
    logger.info(f"Router Agent: Procesados {len(processed_incidents)} incidentes para mapa de calor")
    
    return state

def reporter_agent(state: State) -> State:
    """Genera reportes para diferentes audiencias."""
    logger.info("Reporter Agent: Creando reportes para diferentes audiencias...")
    
    if not state.get("incident_data") or not state.get("all_incidents"):
        logger.warning("Reporter Agent: No hay suficientes datos para generar reportes")
        state["reports"] = {}
        return state
    
    # Crear versiones limpias de los datos (sin contenido completo)
    main_incident = {k: v for k, v in state.get("incident_data", {}).items() if k != 'contenido_completo'}
    all_incidents = state.get("all_incidents", [])[:3]  # Limitar a 3 para el prompt
    
    # Crear prompt para generar reportes con enfoque en vialidades
    reporting_prompt = f"""
    Genera reportes para diferentes audiencias basados en estos datos de seguridad vial:
    
    INCIDENTE PRINCIPAL:
    {json.dumps(main_incident, ensure_ascii=False)}
    
    TODOS LOS INCIDENTES RECIENTES ({len(state.get("all_incidents", []))}):
    {json.dumps(all_incidents, ensure_ascii=False)}
    
    ANÁLISIS:
    - Tipo de incidente: {state.get("incident_type", "No clasificado")}
    - Coordenadas: {state.get("coordinates", {})}
    - Análisis de impacto: {state.get("analysis", {}).get("impact", "No disponible")}
    - Predicciones: {state.get("predictions", {}).get("risk_level", "No disponible")}
    - Recomendaciones: {state.get("recommendations", ["No disponibles"])[:2]}
    
    Genera tres tipos de reporte:
    
    1. "authorities": Informe técnico para autoridades de tránsito y seguridad
    2. "citizens": Información y advertencias para conductores y transeúntes
    3. "media": Nota informativa destacando el impacto en las vialidades
    
    Cada reporte debe incluir información específica sobre:
    - Cuáles rutas o vialidades se ven afectadas
    - Recomendaciones de rutas alternativas
    - Tiempos estimados de afectación
    
    Responde en JSON con estos tres campos exactos.
    """
    
    reports = query_llm(reporting_prompt, temperature=0.4)
    
    # Verificar y guardar los reportes
    if isinstance(reports, dict) and "authorities" in reports and "citizens" in reports and "media" in reports:
        state["reports"] = reports
    else:
        logger.warning("Reporter Agent: Formato de reportes incorrecto, usando valores por defecto")
        state["reports"] = {
            "authorities": {"error": "No se pudo generar el reporte técnico"},
            "citizens": {"error": "No se pudo generar la alerta ciudadana"},
            "media": {"error": "No se pudo generar la nota informativa"}
        }
    
    # Guardar datos para la interfaz web
    try:
        incident_clean = {k: v for k, v in state.get("incident_data", {}).items() if k != 'contenido_completo'}
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "incidents": state.get("all_incidents", []),
            "main_incident": incident_clean,
            "analysis": state.get("analysis", {}),
            "recommendations": state.get("recommendations", []),
            "reports": state.get("reports", {})
        }
        
        with open("security_data.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info("Reporter Agent: Datos guardados en security_data.json")
    except Exception as e:
        logger.error(f"Reporter Agent: Error guardando datos: {str(e)}")
    
    return state

# --- Agentes del subgrafo ---

def classifier_agent(state: SubgraphState) -> SubgraphState:
    """Clasifica el tipo de incidente."""
    logger.info(f"Classifier Agent: Clasificando incidente con urgencia {state['urgency']}")
    
    incident_data = state.get("incident_data", {})
    if not incident_data:
        logger.warning("Classifier Agent: No hay datos de incidente para clasificar")
        state["incident_type"] = "desconocido"
        return state
    
    # Extraer contenido para clasificación
    content = incident_data.get("contenido_completo", "")
    title = incident_data.get("noticia", "")
    initial_type = incident_data.get("tipo_incidente", "")
    
    classification_prompt = f"""
    Clasifica este incidente de seguridad en UNA de estas categorías EXACTAS:
    - homicidio_doloso
    - homicidio_culposo
    - secuestro
    - extorsión
    - robo_casa
    - robo_vehículo
    - robo_transeúnte
    - robo_negocio
    - violencia_familiar
    - violación
    - narcomenudeo
    - lesiones_dolosas
    - fraude
    - amenazas
    - accidente_vial
    - bloqueo_vial
    - otro
    
    Título: {title}
    Clasificación inicial: {initial_type}
    Contenido: {content[:2000]}
    
    Responde en JSON con un solo campo "incident_type" con la categoría exacta.
    """
    
    result = query_llm(classification_prompt, temperature=0.1)
    
    # Extraer y guardar el tipo de incidente
    incident_type = result.get("incident_type", initial_type)
    state["incident_type"] = incident_type.lower() if incident_type else "otro"
    
    return state

def geo_spatial_agent(state: SubgraphState) -> SubgraphState:
    """Determina coordenadas del incidente."""
    logger.info(f"GeoSpatial Agent: Geolocalizando {state.get('incident_type', 'incidente no clasificado')}")
    
    incident_data = state.get("incident_data", {})
    if not incident_data:
        logger.warning("GeoSpatial Agent: No hay datos de incidente para geolocalizar")
        state["coordinates"] = {"lat": None, "lng": None}
        return state
    
    # Extraer el lugar mencionado
    lugar = incident_data.get("lugar", "No especificado")
    
    # Si el lugar no es específico, intentar extraerlo del contenido
    if lugar == "No especificado" or not lugar:
        content = incident_data.get("contenido_completo", "")
        location_prompt = f"""
        Extrae el lugar exacto donde ocurrió este incidente en Querétaro.
        Busca nombres de colonias, calles, cruces o puntos de referencia.
        Si hay múltiples lugares, selecciona el más específico donde ocurrió el hecho.
        
        Contenido: {content[:3000]}
        
        Responde SOLO con el nombre del lugar, sin explicaciones.
        """
        
        location_result = initialize_llm(temperature=0.1).invoke([HumanMessage(content=location_prompt)])
        lugar = location_result.content.strip()
    
    # Geocodificar el lugar usando OpenCage
    lat, lng = geocode_location(lugar)
    
    # Si no se encuentran coordenadas, intentar con información del impacto vial
    if (lat is None or lng is None) and "impacto_vial" in incident_data:
        vial_info = incident_data.get("impacto_vial", "")
        if vial_info and vial_info != "No especificado":
            lat, lng = geocode_location(vial_info)
    
    # Guardar las coordenadas
    state["coordinates"] = {"lat": lat, "lng": lng}
    
    return state

def analytics_agent(state: SubgraphState) -> SubgraphState:
    """Realiza análisis profundo del incidente."""
    logger.info(f"Analytics Agent: Analizando {state['incident_type']} en {state['coordinates']}")
    
    incident_data = state.get("incident_data", {})
    incident_type = state.get("incident_type", "desconocido")
    coordinates = state.get("coordinates", {})
    
    if not incident_data or not coordinates.get("lat"):
        logger.warning("Analytics Agent: Datos insuficientes para análisis")
        state["analysis"] = {"pattern": "No hay datos suficientes para análisis", "impact": "desconocido"}
        return state
    
    # Crear prompt para análisis con enfoque en vialidades
    analytics_prompt = f"""
    Analiza este incidente de seguridad con enfoque en su impacto vial:
    
    DATOS:
    - Tipo: {incident_type}
    - Lugar: {incident_data.get("lugar", "No especificado")}
    - Fecha: {incident_data.get("fecha_incidente", "No especificada")}
    - Hora: {incident_data.get("hora_incidente", "No especificada")}
    - Resumen: {incident_data.get("resumen", "No disponible")}
    - Impacto vial: {incident_data.get("impacto_vial", "No especificado")}
    
    Genera un análisis con:
    - "pattern": patrones temporales o espaciales relacionados con este tipo de incidente
    - "impact": impacto en vialidades y tránsito (bajo, moderado, alto, severo)
    - "risk_factors": factores que contribuyeron al incidente
    - "affected_routes": vías o rutas afectadas por el incidente
    - "estimated_duration": duración estimada del impacto en vialidades
    
    Responde en JSON con estos campos exactos.
    """
    
    analysis = query_llm(analytics_prompt, temperature=0.4)
    
    # Guardar el análisis
    state["analysis"] = analysis
    
    return state

def evaluator_agent(state: SubgraphState) -> SubgraphState:
    """Evalúa la calidad del análisis."""
    logger.info(f"Evaluator Agent: Evaluando análisis")
    
    incident_data = state.get("incident_data", {})
    analysis = state.get("analysis", {})
    
    if not incident_data or not analysis:
        logger.warning("Evaluator Agent: Datos insuficientes para evaluación")
        state["confidence"] = 0.3
        return state
    
    # Preparar versión limpia del incidente para el prompt
    incident_clean = {k: v for k, v in incident_data.items() if k != 'contenido_completo'}
    
    # Crear prompt para evaluación de confianza
    evaluation_prompt = f"""
    Evalúa la confianza en este análisis de incidente de seguridad:
    
    DATOS DEL INCIDENTE:
    {json.dumps(incident_clean, ensure_ascii=False)}
    
    ANÁLISIS REALIZADO:
    {json.dumps(analysis, ensure_ascii=False)}
    
    Considera factores como:
    - Completitud de información del incidente
    - Coherencia del análisis
    - Confiabilidad de la fuente
    - Precisión de la ubicación
    - Claridad del impacto vial
    
    Genera un valor de confianza entre 0.0 y 1.0 donde:
    - 0.0-0.3: Datos y análisis de baja confianza
    - 0.4-0.6: Confianza moderada
    - 0.7-0.8: Alta confianza
    - 0.9-1.0: Confianza muy alta
    
    Responde en JSON con campo "confidence" (valor numérico) y "justification" (razones).
    """
    
    result = query_llm(evaluation_prompt, temperature=0.3)
    
    # Extraer y guardar la confianza
    confidence = result.get("confidence", 0.5)
    # Asegurar que sea un valor numérico
    if not isinstance(confidence, (int, float)):
        try:
            confidence = float(confidence)
        except:
            confidence = 0.5
    
    state["confidence"] = round(confidence, 2)
    
    return state

def predictive_agent(state: SubgraphState) -> SubgraphState:
    """Genera predicciones basadas en el análisis."""
    logger.info(f"Predictive Agent: Generando predicciones con confianza {state['confidence']}")
    
    incident_type = state.get("incident_type", "desconocido")
    incident_data = state.get("incident_data", {})
    analysis = state.get("analysis", {})
    confidence = state.get("confidence", 0.5)
    
    if not incident_data or confidence < 0.3:
        logger.warning("Predictive Agent: Confianza insuficiente para predicciones")
        state["predictions"] = {"risk_level": "No determinado", "duration": "No aplicable"}
        return state
    
    # Crear prompt para predicciones con enfoque en vialidades
    predictive_prompt = f"""
    Genera predicciones para este incidente de seguridad con enfoque en impacto vial:
    
    DATOS:
    - Tipo: {incident_type}
    - Lugar: {incident_data.get("lugar", "")}
    - Fecha/Hora: {incident_data.get("fecha_incidente", "")} a las {incident_data.get("hora_incidente", "")}
    - Impacto vial: {incident_data.get("impacto_vial", "")}
    - Análisis de patrones: {analysis.get("pattern", "")}
    - Rutas afectadas: {analysis.get("affected_routes", "")}
    - Confianza en los datos: {confidence}
    
    Genera predicciones con estos campos exactos:
    - "risk_level": nivel de riesgo vial (bajo, moderado, elevado, crítico)
    - "duration": duración estimada del impacto vial (en horas específicas)
    - "congestion_probability": probabilidad de congestionamiento (0-100%)
    - "alternative_routes": sugerencias de rutas alternativas específicas
    - "best_times": mejores horarios para circular por la zona afectada
    
    Responde en JSON.
    """
    
    predictions = query_llm(predictive_prompt, temperature=0.4)
    
    # Guardar las predicciones
    state["predictions"] = predictions
    
    return state

def recommender_agent(state: SubgraphState) -> SubgraphState:
    """Genera recomendaciones de rutas alternativas."""
    logger.info(f"Recommender Agent: Generando recomendaciones específicas de rutas alternativas")
    
    # Extraer datos relevantes
    incident_type = state.get("incident_type", "desconocido")
    predictions = state.get("predictions", {})
    analysis = state.get("analysis", {})
    coordinates = state.get("coordinates", {})
    incident_data = state.get("incident_data", {})
    
    # Validar disponibilidad de datos
    if not predictions or not coordinates.get("lat"):
        logger.warning("Recommender Agent: Datos insuficientes para recomendaciones")
        state["recommendations"] = ["No hay suficientes datos para recomendar rutas alternativas"]
        state["iteration"] = state.get("iteration", 0) + 1
        return state
    
    # Base de datos simplificada de vialidades de Querétaro
    qro_main_roads = {
        "5 de Febrero": {
            "type": "avenida", 
            "connections": ["Constituyentes", "Universidad", "Ezequiel Montes"],
            "zones": ["Centro", "San Francisquito"]
        },
        "Constituyentes": {
            "type": "avenida", 
            "connections": ["5 de Febrero", "Zaragoza", "Bernardo Quintana"],
            "zones": ["Centro", "Álamos"]
        },
        "Bernardo Quintana": {
            "type": "boulevard", 
            "connections": ["Constituyentes", "Luis Pasteur", "Prolongación Tecnológico"],
            "zones": ["Álamos", "Del Valle", "Juriquilla"]
        }
    }
    
    # Obtener lugar del incidente
    incident_location = incident_data.get("lugar", "No especificado")
    if not isinstance(incident_location, str):
        incident_location = str(incident_location) if incident_location else "No especificado"
    
    # Prompt para recomendaciones
    recommender_prompt = f"""
    Genera recomendaciones ESPECÍFICAS para este incidente vial en Querétaro:
    
    DATOS DEL INCIDENTE:
    - Tipo: {incident_type}
    - Lugar exacto: {incident_location}
    - Coordenadas: Latitud {coordinates.get("lat")}, Longitud {coordinates.get("lng")}
    - Nivel de riesgo vial: {predictions.get("risk_level", "No especificado")}
    - Rutas afectadas: {analysis.get("affected_routes", "No especificadas")}
    
    Proporciona 5 recomendaciones diferentes y específicas para conductores.
    Usa EXCLUSIVAMENTE nombres reales de avenidas, calles y colonias de Querétaro.
    
    Responde ÚNICAMENTE con una lista JSON de recomendaciones.
    """
    
    # Consultar al LLM
    try:
        result = query_llm(recommender_prompt, temperature=0.4)
    except Exception as e:
        logger.error(f"Error consultando al LLM: {str(e)}")
        result = ["Error al generar recomendaciones. Utilice rutas alternativas principales."]
    
    # Extraer recomendaciones
    if isinstance(result, list):
        recommendations = result
    elif isinstance(result, dict) and "recommendations" in result:
        recommendations = result["recommendations"]
    else:
        recommendations = ["No se pudieron generar recomendaciones específicas"]
    
    # Guardar recomendaciones
    state["recommendations"] = recommendations
    
    # Incrementar contador de iteraciones
    state["iteration"] = state.get("iteration", 0) + 1
    
    return state

# --- Funciones para el subgrafo ---

def invocador_subgrafo(state: State) -> State:
    """Invoca el subgrafo de análisis."""
    logger.info("Invocando subgrafo de análisis...")
    
    # Preparar estado inicial del subgrafo
    subgraph_initial_state = {
        "iteration": 0,
        "urgency": state["urgency"],
        "incident_type": None,
        "coordinates": None,
        "analysis": None,
        "confidence": None,
        "predictions": None,
        "recommendations": None,
        "incident_data": state.get("incident_data", {})
    }
    
    # Invocar el subgrafo
    subgraph_result = subgraph.invoke(subgraph_initial_state)
    
    # Transferir resultados del subgrafo al estado principal
    result = {
        "incident_type": subgraph_result["incident_type"],
        "coordinates": subgraph_result["coordinates"],
        "analysis": subgraph_result["analysis"],
        "confidence": subgraph_result["confidence"],
        "predictions": subgraph_result["predictions"],
        "recommendations": subgraph_result["recommendations"]
    }
    
    return result

# --- Construir grafo principal ---

graph_builder = StateGraph(State)
graph_builder.add_node("supervisor", supervisor_agent)
graph_builder.add_node("scraper", scraper_agent)
graph_builder.add_node("router", router_agent)
graph_builder.add_node("subgrafo_analisis", invocador_subgrafo)
graph_builder.add_node("reporter", reporter_agent)

# Definir el flujo principal
graph_builder.add_edge(START, "supervisor")
graph_builder.add_edge("supervisor", "scraper")
graph_builder.add_edge("scraper", "router")
graph_builder.add_edge("router", "subgrafo_analisis")
graph_builder.add_edge("subgrafo_analisis", "reporter")
graph_builder.add_edge("reporter", END)

# --- Construir subgrafo ---

subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node("classifier", classifier_agent)
subgraph_builder.add_node("geo_spatial", geo_spatial_agent)
subgraph_builder.add_node("analytics", analytics_agent)
subgraph_builder.add_node("evaluator", evaluator_agent)
subgraph_builder.add_node("predictive", predictive_agent)
subgraph_builder.add_node("recommender", recommender_agent)

# Definir el flujo del subgrafo
subgraph_builder.set_entry_point("classifier")
subgraph_builder.add_edge("classifier", "geo_spatial")
subgraph_builder.add_edge("geo_spatial", "analytics")
subgraph_builder.add_edge("analytics", "evaluator")
subgraph_builder.add_edge("evaluator", "predictive")
subgraph_builder.add_edge("predictive", "recommender")

# Iteraciones controladas
subgraph_builder.add_conditional_edges(
    "recommender",
    lambda state: END if state["iteration"] >= 2 else "classifier",
    {"classifier": "classifier", END: END}
)

subgraph = subgraph_builder.compile()

# Compilar grafo principal
graph = graph_builder.compile()

# Función para ejecución directa
def ejecutar_grafo():
    initial_state = {"start_signal": "Y", "raw_data": None, "all_incidents": []}
    result = graph.invoke(initial_state)
    print("Resultado final:", result)
    return result