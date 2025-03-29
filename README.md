# Q-Alert

[![Demo de QR-Alert]](https://youtu.be/GB_Dr1jhNug "Demo de QR-Alert")

<p align="center">
  <img src="image0.png" width="100%">
</p>
<p align="center">
  <img src="imagen1.png" width="45%">
  <img src="imagen2.png" width="45%">
</p>

## 🌟 Descripción

Q-Alert es un sistema multiagente (MAS) que resuelve la necesidad crítica de información en tiempo real sobre seguridad vial en Querétaro. Diseñado para abordar la problemática de accidentes, bloqueos y otros incidentes que afectan la movilidad urbana, Q-Alert permite a los ciudadanos tomar decisiones informadas sobre sus desplazamientos y rutas alternativas.

El sistema utiliza una arquitectura de agentes inteligentes coordinados con LangGraph, donde cada agente especializado se encarga de aspectos específicos: desde la recolección de datos de noticias locales, clasificación de incidentes por gravedad, geolocalización precisa, hasta la generación de recomendaciones personalizadas. Esta arquitectura distribuida permite procesar grandes volúmenes de información de manera eficiente y ofrecer alertas relevantes según la ubicación y necesidades del usuario.

## Arquitectura Multiagente con LangGraph

El núcleo de Q-Alert está construido sobre un sistema multiagente donde cada agente IA especializado tiene responsabilidades específicas:

- **Supervisor Agent**: Coordina y monitorea el trabajo de los demás agentes, garantizando la coherencia del sistema.
- **Scraper Agent**: Recolecta datos de fuentes de noticias utilizando la API de Tavily Search para encontrar incidentes de seguridad recientes.
- **Router Agent**: Analiza los datos recopilados y prioriza los incidentes según su impacto vial y relevancia, asignando un nivel de urgencia.
- **Classifier Agent**: Categoriza cada incidente en tipos específicos para su mejor procesamiento.
- **Geo-Spatial Agent**: Determina y valida las coordenadas geográficas de cada incidente.
- **Analytics Agent**: Realiza análisis profundo de los incidentes, identificando patrones y evaluando su impacto.
- **Evaluator Agent**: Valida la calidad del análisis y asigna un nivel de confianza a los datos.
- **Predictive Agent**: Genera predicciones sobre el impacto futuro de los incidentes.
- **Recommender Agent**: Sugiere rutas alternativas específicas basadas en los incidentes actuales.
- **Reporter Agent**: Genera informes adaptados para diferentes audiencias: ciudadanos, autoridades y medios.

Implementamos estos agentes utilizando LangGraph, que permite una orquestación eficiente del flujo de trabajo entre ellos. Cada agente tiene ponderaciones específicas en el grafo de decisión, lo que garantiza que los incidentes más críticos para la vialidad reciban mayor atención y desencadenen alertas más urgentes.

## 🔍 Características principales

- **Mapa interactivo**: Visualización geoespacial de incidentes de seguridad con marcadores categorizados por tipo
- **Mapa de calor**: Identificación de zonas con mayor concentración de incidentes
- **Reportes ciudadanos**: Permite a los usuarios contribuir con información en tiempo real
- **Análisis multiagente**: Procesamiento automatizado y coordinado de noticias e incidentes mediante varios agentes IA
- **Recomendaciones de rutas alternativas**: Sugerencias para evitar zonas afectadas
- **Estadísticas y tendencias**: Visualización de patrones de incidentes por tipo y ubicación
- **Notificaciones en tiempo real**: Alertas sobre nuevos incidentes relevantes
- **Interfaz adaptable**: Diseño responsive para dispositivos móviles y escritorio

## 🛠️ Tecnologías utilizadas

- **Backend**: Flask (Python)
- **Arquitectura Multiagente**: LangGraph para orquestar flujos de trabajo entre agentes IA
- **Modelo de IA**: Google Gemini 2.0 Flash
- **Frontend**: HTML, CSS, JavaScript
- **Mapas**: Leaflet.js
- **Visualización de datos**: Chart.js
- **Geocodificación**: OpenCage API
- **Análisis de noticias**: Tavily Search API

## 🚀 Instalación y despliegue

### Requisitos previos
- Python 3.10 o superior
- Docker (para despliegue en contenedores)
- API Keys para:
  - Google Gemini (GOOGLE_API_KEY)
  - OpenCage Geocoding (OPENCAGE_API_KEY)
  - Tavily Search (TAVILY_API_KEY)

### Instalación local

1. Clonar el repositorio:
```bash
git clone https://github.com/tu-usuario/qr-alert.git
cd qr-alert
```

2. Crear y activar entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
# Crear archivo .env en la raíz del proyecto
GOOGLE_API_KEY=tu_api_key_de_google
OPENCAGE_API_KEY=tu_api_key_de_opencage
TAVILY_API_KEY=tu_api_key_de_tavily
```

5. Ejecutar la aplicación:
```bash
python app.py
```

## 🔗 Enlaces

- [Demo de agentes](https://youtu.be/yScVSfOTcLc)
- [Demo en vivo](https://seguridad-production-ff55.up.railway.app/)

## 📄 Licencia

Este proyecto está licenciado bajo la licencia MIT