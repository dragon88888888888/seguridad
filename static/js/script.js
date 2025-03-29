// Variables globales
let map;
let markers = [];
let heatLayer;
let markerClusterGroup;
let securityData = null;
let heatmapActive = false;

// Configuración del mapa
const mapConfig = {
    center: [20.5888, -100.3899], // Querétaro
    zoom: 12,
    minZoom: 8,
    maxZoom: 18
};

// Función actualizada para la gráfica
async function fetchAndUpdateChart() {
    try {
        // Obtener directamente todos los incidentes
        const response = await fetch('/api/all-incidents');
        const incidents = await response.json();

        console.log("Datos brutos para gráfica:", incidents);

        // Crear un contador simple para los tipos de incidentes
        const typeCount = {};

        incidents.forEach(incident => {
            let type = 'Desconocido';

            // Extraer el tipo del incidente (cualquier formato)
            if (incident.type) {
                type = incident.type;
            }

            // Normalizar formato
            type = type.charAt(0).toUpperCase() + type.slice(1).toLowerCase();
            type = type.replace(/_/g, ' ');

            // Incrementar contador
            typeCount[type] = (typeCount[type] || 0) + 1;
        });

        // Convertir a arrays para Chart.js
        const types = Object.keys(typeCount);
        const counts = Object.values(typeCount);

        // Crear gráfica horizontal
        const ctx = document.getElementById('incidents-chart').getContext('2d');

        if (window.incidentsChart) {
            window.incidentsChart.destroy();
        }

        window.incidentsChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: types,
                datasets: [{
                    label: 'Incidentes por tipo',
                    data: counts,
                    backgroundColor: types.map(t => getColorForType(t)),
                    borderColor: types.map(t => getColorForType(t, 0.8)),
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',  // Gráfica horizontal
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });

    } catch (error) {
        console.error("Error al cargar datos para la gráfica:", error);
    }
}

// Función auxiliar para obtener color por tipo
function getColorForType(type, alpha = 0.7) {
    const t = type.toLowerCase();

    if (t.includes('robo') || t.includes('hurto')) {
        return `rgba(244, 67, 54, ${alpha})`;  // Rojo
    } else if (t.includes('homicidio') || t.includes('asesinato')) {
        return `rgba(211, 47, 47, ${alpha})`;  // Rojo oscuro
    } else if (t.includes('accidente') || t.includes('vial')) {
        return `rgba(255, 152, 0, ${alpha})`;  // Naranja
    } else if (t.includes('violencia') || t.includes('ataque')) {
        return `rgba(233, 30, 99, ${alpha})`;  // Rosa
    } else if (t.includes('secuestro')) {
        return `rgba(213, 0, 249, ${alpha})`;  // Púrpura
    } else if (t.includes('droga') || t.includes('narco')) {
        return `rgba(76, 175, 80, ${alpha})`;  // Verde
    } else if (t.includes('fraude')) {
        return `rgba(30, 136, 229, ${alpha})`;  // Azul
    } else if (t.includes('clausura')) {
        return `rgba(156, 39, 176, ${alpha})`;  // Púrpura
    } else if (t.includes('detención') || t.includes('detencion')) {
        return `rgba(123, 31, 162, ${alpha})`;  // Púrpura oscuro
    } else if (t.includes('muerte')) {
        return `rgba(106, 27, 154, ${alpha})`;  // Púrpura más oscuro
    } else {
        return `rgba(156, 39, 176, ${alpha})`;  // Púrpura por defecto
    }
}

// Configuración de iconos para marcadores
const incidentIcons = {
    'accidente_vial': L.icon({
        iconUrl: '/static/img/accident.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'bloqueo_vial': L.icon({
        iconUrl: '/static/img/blockade.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'robo_vehículo': L.icon({
        iconUrl: '/static/img/theft.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'robo_casa': L.icon({
        iconUrl: '/static/img/theft.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'robo_transeúnte': L.icon({
        iconUrl: '/static/img/theft.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'homicidio_doloso': L.icon({
        iconUrl: '/static/img/violent.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'otro': L.icon({
        iconUrl: '/static/img/other.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    })
};

// Colores para diferentes tipos de incidentes (para el mapa de calor)
const incidentColors = {
    'accidente_vial': '#FF9800',       // Naranja
    'bloqueo_vial': '#FFC107',         // Ámbar
    'robo_vehículo': '#F44336',        // Rojo 
    'robo_casa': '#E91E63',            // Rosa
    'robo_transeúnte': '#9C27B0',      // Púrpura
    'homicidio_doloso': '#D32F2F',     // Rojo oscuro
    'otro': '#607D8B'                  // Gris azulado
};

// Función para inicializar el mapa
function initMap() {
    // Crear el mapa
    map = L.map('map', {
        center: mapConfig.center,
        zoom: mapConfig.zoom,
        minZoom: mapConfig.minZoom,
        maxZoom: mapConfig.maxZoom
    });

    // Añadir capa base de OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Inicializar cluster de marcadores
    markerClusterGroup = L.markerClusterGroup({
        disableClusteringAtZoom: 16,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true
    });

    map.addLayer(markerClusterGroup);

    // Cargar datos iniciales
    loadSecurityData();
}
async function loadAllIncidents() {
    try {
        showLoadingIndicator(true);
        const response = await fetch('/api/all-incidents');
        const data = await response.json();

        console.log("Cargados todos los incidentes:", data.length);

        // Limpiar y crear marcadores
        clearMarkers();
        createAllIncidentMarkers(data);

        // Actualizar contador de incidentes
        document.getElementById('reported-incidents').textContent = data.length;

        showLoadingIndicator(false);
    } catch (error) {
        console.error('Error cargando todos los incidentes:', error);
        showLoadingIndicator(false);
        showError('No se pudieron cargar los incidentes');
    }
}
// Función para cargar datos de seguridad del backend
async function loadSecurityData() {
    try {
        showLoadingIndicator(true);

        // Intentar cargar los datos reales
        const response = await fetch('/api/security_data');

        // Verificar si la respuesta es válida
        if (!response.ok) {
            throw new Error(`Error de servidor: ${response.status}`);
        }

        const data = await response.json();
        console.log("Datos cargados:", data); // Para depuración

        // Verificar estructura de datos
        if (!data || typeof data !== 'object') {
            throw new Error('Formato de datos inválido');
        }

        securityData = data;

        // Validar presencia de incidentes
        if (!data.incidents || !Array.isArray(data.incidents)) {
            console.warn("No hay incidentes en los datos o formato incorrecto");
            data.incidents = [];
        }

        // Validar la existencia del incidente principal
        if (!data.main_incident || typeof data.main_incident !== 'object') {
            console.warn("No hay incidente principal o formato incorrecto");
            // Si hay incidentes, usar el primero como principal
            if (data.incidents.length > 0) {
                data.main_incident = data.incidents[0];
            } else {
                data.main_incident = {
                    noticia: "No hay incidentes reportados",
                    resumen: "No se encontraron incidentes de seguridad recientes.",
                    tipo_incidente: "desconocido",
                    gravedad: "baja"
                };
            }
        }

        // Actualizar la UI con los datos
        updateUI(data);

        // Actualizar timestamp de última actualización
        updateLastUpdateTime(data.timestamp);

        // Limpiar y crear marcadores
        clearMarkers();
        createIncidentMarkers(data.incidents);

        // Actualizar contador de incidentes
        document.getElementById('reported-incidents').textContent = data.incidents.length;

        showLoadingIndicator(false);

        // Mostrar notificación de éxito
        showNotification("Datos actualizados correctamente", "success");

    } catch (error) {
        console.error('Error cargando datos de seguridad:', error);
        showLoadingIndicator(false);

        // Mostrar mensaje amigable de error
        showError('No se pudieron cargar los datos. Intente de nuevo más tarde.');

        // Cargar datos de respaldo para mantener la funcionalidad mínima
        loadBackupData();
    }
}

// Función para cargar datos de respaldo si fallan los datos reales
function loadBackupData() {
    // Datos mínimos para evitar que la interfaz se rompa
    const backupData = {
        timestamp: new Date().toISOString(),
        incidents: [
            {
                titulo: "Error de conexión",
                resumen: "No se pudieron cargar los datos actuales. Intente actualizar más tarde.",
                lugar: "Querétaro",
                tipo: "error",
                gravedad: "baja",
                coordenadas: {
                    lat: 20.5888,
                    lng: -100.3899
                }
            }
        ],
        main_incident: {
            noticia: "Error de conexión",
            resumen: "No se pudieron cargar los datos actuales. Intente actualizar más tarde.",
            lugar: "Querétaro",
            tipo_incidente: "error",
            gravedad: "baja"
        },
        recommendations: ["Intente actualizar los datos más tarde"]
    };

    updateUI(backupData);
}

// Añadir esta función a main-script.js (script.js)

// Configuración de iconos para reportes ciudadanos
const citizenReportIcons = {
    'accidente_vial': L.icon({
        iconUrl: '/static/img/accident.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'bloqueo_vial': L.icon({
        iconUrl: '/static/img/blockade.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'trafico_intenso': L.icon({
        iconUrl: '/static/img/traffic.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'robo': L.icon({
        iconUrl: '/static/img/theft.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'disturbio': L.icon({
        iconUrl: '/static/img/disturbance.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'operativo_policial': L.icon({
        iconUrl: '/static/img/police.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'manifestacion': L.icon({
        iconUrl: '/static/img/protest.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    }),
    'otro': L.icon({
        iconUrl: '/static/img/other.png',
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    })
};

// Reemplazar la función loadSecurityData para que use loadAllIncidents
async function loadSecurityData() {
    try {
        // Cargar todos los incidentes (incluidos los reportes ciudadanos)
        await loadAllIncidents();

        // Cargar datos específicos del sistema para la información principal
        const response = await fetch('/api/security_data');
        if (!response.ok) {
            throw new Error(`Error de servidor: ${response.status}`);
        }

        const data = await response.json();
        console.log("Datos del sistema cargados:", data);

        securityData = data;

        // Actualizar la UI con los datos del sistema
        updateUI(data);

        // Actualizar timestamp de última actualización
        updateLastUpdateTime(data.timestamp);

    } catch (error) {
        console.error('Error cargando datos de seguridad:', error);
        showLoadingIndicator(false);
        showError('No se pudieron cargar los datos');
        loadBackupData();
    }
}

// Función para crear marcadores para todos los incidentes
function createAllIncidentMarkers(incidents) {
    // Validar entrada
    if (!incidents || !Array.isArray(incidents)) {
        console.error('Datos de incidentes inválidos');
        return;
    }

    console.log(`Creando marcadores para ${incidents.length} incidentes`);

    // Datos para mapa de calor
    const heatmapData = [];
    let validMarkers = 0;

    incidents.forEach((incident, index) => {
        // Verificar si el incidente tiene coordenadas válidas
        let hasValidCoords = false;
        let lat = null;
        let lng = null;

        if (incident.coordinates && incident.coordinates.lat && incident.coordinates.lng) {
            lat = parseFloat(incident.coordinates.lat);
            lng = parseFloat(incident.coordinates.lng);
            hasValidCoords = !isNaN(lat) && !isNaN(lng);
        }

        if (!hasValidCoords) {
            console.log(`Incidente #${index} sin coordenadas válidas`);
            return;
        }

        try {
            // Determinar icono basado en fuente y tipo
            let icon;

            if (incident.source === 'citizen') {
                // Usar iconos de reportes ciudadanos
                const iconType = incident.type || 'otro';
                icon = citizenReportIcons[iconType] || citizenReportIcons.otro;
            } else {
                // Usar iconos del sistema
                let iconType = 'otro';
                const tipo = incident.type ? incident.type.toLowerCase() : '';

                if (tipo.includes('accidente') || tipo.includes('vial')) {
                    iconType = 'accidente_vial';
                } else if (tipo.includes('bloqueo')) {
                    iconType = 'bloqueo_vial';
                } else if (tipo.includes('robo')) {
                    iconType = 'robo_vehículo';
                } else if (tipo.includes('homicidio')) {
                    iconType = 'homicidio_doloso';
                }

                icon = incidentIcons[iconType] || incidentIcons.otro;
            }

            // Crear marcador
            const marker = L.marker([lat, lng], {
                icon: icon,
                title: incident.title || 'Incidente'
            });

            // Crear contenido del popup
            let sourceLabel = incident.source === 'citizen' ?
                '<span class="citizen-source">Reporte Ciudadano</span>' :
                '<span class="system-source">Reporte Oficial</span>';

            // Añadir verificación si es un reporte ciudadano
            let verifiedBadge = '';
            if (incident.source === 'citizen' && incident.verified) {
                verifiedBadge = '<span class="verified-badge">Verificado</span>';
            }

            const popupContent = `
                <div class="incident-popup ${incident.source}">
                    <div class="popup-header">
                        <h3>${incident.title}</h3>
                        <div class="popup-meta">
                            ${sourceLabel}
                            ${verifiedBadge}
                        </div>
                    </div>
                    <p><strong>Lugar:</strong> ${incident.location || 'No especificado'}</p>
                    <p><strong>Fecha/Hora:</strong> ${incident.timestamp || '-'} ${incident.time || ''}</p>
                    <p><strong>Tipo:</strong> ${formatIncidentType(incident.type) || 'No especificado'}</p>
                    <p><strong>Gravedad:</strong> ${incident.severity || 'No especificada'}</p>
                    <div class="popup-summary">${incident.description || 'No hay detalles disponibles'}</div>
                    ${incident.url ? `<a href="${incident.url}" target="_blank" class="popup-link">Ver noticia completa</a>` : ''}
                </div>
            `;

            // Asignar evento de clic
            marker.bindPopup(popupContent);
            marker.on('click', () => {
                // Convertir a formato compatible con showIncidentDetails
                const formattedIncident = {
                    noticia: incident.title,
                    lugar: incident.location,
                    fecha_incidente: incident.timestamp,
                    hora_incidente: incident.time,
                    tipo_incidente: incident.type,
                    gravedad: incident.severity,
                    resumen: incident.description,
                    impacto_vial: incident.vial_impact || 'No especificado'
                };

                showIncidentDetails(formattedIncident);
            });

            // Añadir al clúster
            markerClusterGroup.addLayer(marker);
            markers.push(marker);
            validMarkers++;

            // Añadir datos para el mapa de calor
            // Intensidad basada en la gravedad
            let intensity = 0.5;
            const severityMap = {
                'baja': 0.3,
                'media': 0.5,
                'alta': 0.7,
                'crítica': 1.0,
                'critica': 1.0
            };

            if (incident.severity && severityMap[incident.severity.toLowerCase()]) {
                intensity = severityMap[incident.severity.toLowerCase()];
            }

            heatmapData.push([lat, lng, intensity]);
        } catch (error) {
            console.error(`Error creando marcador para incidente #${index}:`, error);
        }
    });

    console.log(`Se crearon ${validMarkers} marcadores válidos de ${incidents.length} incidentes`);

    // Actualizar datos para mapa de calor
    createHeatmap(heatmapData);
}

// Función para crear el mapa de calor a partir de datos
function createHeatmap(heatmapData) {
    // Eliminar mapa de calor existente
    if (heatLayer) {
        map.removeLayer(heatLayer);
    }

    if (heatmapData.length > 0) {
        // Agrupar puntos para identificar áreas con múltiples incidentes
        const groupedPoints = {};

        heatmapData.forEach(point => {
            // Redondear coordenadas para agrupar puntos cercanos (precisión de ~100m)
            const roundedLat = Math.round(point[0] * 1000) / 1000;
            const roundedLng = Math.round(point[1] * 1000) / 1000;
            const key = `${roundedLat},${roundedLng}`;

            if (!groupedPoints[key]) {
                groupedPoints[key] = {
                    lat: point[0],
                    lng: point[1],
                    count: 1,
                    intensity: point[2]
                };
            } else {
                groupedPoints[key].count += 1;
                groupedPoints[key].intensity += point[2];
            }
        });

        // Construir nuevos datos para el mapa de calor
        const enhancedHeatData = [];

        Object.values(groupedPoints).forEach(point => {
            // Si hay múltiples incidentes en el mismo lugar, aumentar la intensidad
            let finalIntensity = point.intensity;

            if (point.count > 1) {
                // Aumentar intensidad exponencialmente con el número de incidentes
                finalIntensity = Math.min(1.0, point.intensity * Math.sqrt(point.count));
            } else {
                // Para incidentes únicos, reducir un poco la intensidad
                finalIntensity = point.intensity * 0.5;
            }

            enhancedHeatData.push([point.lat, point.lng, finalIntensity]);
        });

        // Crear la capa de calor con parámetros mejorados
        heatLayer = L.heatLayer(enhancedHeatData, {
            radius: 35,
            blur: 20,
            maxZoom: 17,
            minOpacity: 0.4,
            max: 1.0,
            gradient: {
                0.2: 'blue',
                0.4: 'lime',
                0.6: 'yellow',
                0.8: 'orange',
                1.0: 'red'
            }
        });
    }
}

// Función para mostrar notificaciones temporales
function showNotification(message, type = 'info') {
    // Crear elemento de notificación
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    // Añadir al cuerpo del documento
    document.body.appendChild(notification);

    // Mostrar con animación
    setTimeout(() => {
        notification.classList.add('visible');
    }, 10);

    // Ocultar después de 3 segundos
    setTimeout(() => {
        notification.classList.remove('visible');
        // Eliminar después de la animación
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Función para actualizar la interfaz con los datos cargados
function updateUI(data) {
    // Mostrar incidente principal
    if (data.main_incident) {
        updateMainIncidentInfo(data.main_incident);
    }

    // Actualizar recomendaciones
    updateRecommendations(data.recommendations || []);

    // Actualizar reportes en pestañas
    updateReports(data.reports || {});

    // Actualizar gráfica
    updateIncidentsChart(data.incidents || []);
}

// Función para actualizar la información del incidente principal
function updateMainIncidentInfo(incident) {
    // Validación de entrada
    if (!incident || typeof incident !== 'object') {
        console.error('Formato de incidente inválido:', incident);
        incident = {
            noticia: 'Error en los datos',
            resumen: 'No se pudieron procesar los datos del incidente.',
            tipo_incidente: 'error',
            gravedad: 'desconocida'
        };
    }

    // Título del incidente
    let title = 'Incidente sin título';
    if (incident.noticia) {
        title = incident.noticia;
    } else if (incident.titulo) {
        title = incident.titulo;
    }
    document.getElementById('incident-title').textContent = title;

    // Descripción/resumen
    let description = 'No hay descripción disponible';
    if (incident.resumen) {
        description = incident.resumen;
    } else if (incident.summary) {
        description = incident.summary;
    } else if (incident.descripcion) {
        description = incident.descripcion;
    } else if (incident.contenido_completo && incident.contenido_completo.length < 300) {
        description = incident.contenido_completo;
    }
    document.getElementById('incident-description').textContent = description;

    // Ubicación
    let location = '-';
    if (incident.lugar) {
        location = incident.lugar;
    } else if (incident.location) {
        location = incident.location;
    } else if (incident.lugar_exacto) {
        location = incident.lugar_exacto;
    }
    document.getElementById('incident-location').textContent = location;

    // Fecha y hora
    let datetime = '-';

    // Buscar en diferentes posibles propiedades
    let fecha = incident.fecha_incidente || incident.fecha || incident.date || '';
    let hora = incident.hora_incidente || incident.hora || incident.time || '';

    if (fecha) {
        datetime = fecha;
        if (hora) {
            datetime += ' a las ' + hora;
        }
    }
    document.getElementById('incident-datetime').textContent = datetime;

    // Tipo de incidente
    let type = '-';
    if (incident.tipo_incidente) {
        type = formatIncidentType(incident.tipo_incidente);
    } else if (incident.tipo) {
        type = formatIncidentType(incident.tipo);
    }
    document.getElementById('incident-type').textContent = type;

    // Impacto vial
    let impact = 'No especificado';
    if (incident.impacto_vial) {
        impact = incident.impacto_vial;
    } else if (incident.traffic_impact) {
        impact = incident.traffic_impact;
    }
    document.getElementById('incident-impact').textContent = impact;

    // Actualizar badge según gravedad
    const securityBadge = document.getElementById('security-badge');
    securityBadge.className = 'security-badge';

    let gravedad = '';
    if (incident.gravedad) {
        gravedad = incident.gravedad.toLowerCase();
    } else if (incident.severity) {
        gravedad = incident.severity.toLowerCase();
    }

    switch (gravedad) {
        case 'baja':
        case 'bajo':
        case 'low':
            securityBadge.classList.add('safe');
            securityBadge.textContent = 'Baja';
            break;
        case 'media':
        case 'medio':
        case 'medium':
            securityBadge.classList.add('less-unsafe');
            securityBadge.textContent = 'Media';
            break;
        case 'alta':
        case 'alto':
        case 'high':
            securityBadge.classList.add('unsafe');
            securityBadge.textContent = 'Alta';
            break;
        case 'crítica':
        case 'critica':
        case 'critical':
            securityBadge.classList.add('risk-zone');
            securityBadge.textContent = 'Crítica';
            break;
        default:
            securityBadge.classList.add('standard');
            securityBadge.textContent = 'Estándar';
    }

    // Actualizar nivel de riesgo desde diferentes fuentes posibles
    let riskLevel = 'No determinado';

    if (securityData) {
        if (securityData.predictions && securityData.predictions.risk_level) {
            riskLevel = securityData.predictions.risk_level;
        } else if (securityData.analysis && securityData.analysis.risk_level) {
            riskLevel = securityData.analysis.risk_level;
        } else if (securityData.risk_level) {
            riskLevel = securityData.risk_level;
        }
    }

    document.getElementById('risk-level').textContent = formatRiskLevel(riskLevel);

    // Calcular índice de seguridad basado en gravedad
    let safetyIndex = calculateSafetyIndex(gravedad);
    document.getElementById('safety-index').textContent = safetyIndex + '%';
}

// Función para formatear el tipo de incidente
function formatIncidentType(type) {
    if (!type) return '-';

    // Convertir a formato legible
    type = type.replace(/_/g, ' ');

    // Capitalizar primera letra
    return type.charAt(0).toUpperCase() + type.slice(1);
}

// Función para formatear el nivel de riesgo
function formatRiskLevel(level) {
    if (!level) return 'No determinado';

    // Si es una cadena JSON o un objeto, extraer el valor
    if (typeof level === 'string' && (level.startsWith('{') || level.startsWith('['))) {
        try {
            const parsed = JSON.parse(level);
            if (parsed && typeof parsed === 'object') {
                return parsed.level || parsed.risk || parsed.value || 'No determinado';
            }
        } catch (e) {
            // Si no se puede parsear, usar como está
        }
    }

    return level;
}

// Calcular índice de seguridad basado en gravedad
function calculateSafetyIndex(gravedad) {
    let safetyIndex = 65; // Valor por defecto (medio)

    switch (gravedad) {
        case 'baja':
        case 'bajo':
        case 'low':
            safetyIndex = 85;
            break;
        case 'media':
        case 'medio':
        case 'medium':
            safetyIndex = 65;
            break;
        case 'alta':
        case 'alto':
        case 'high':
            safetyIndex = 45;
            break;
        case 'crítica':
        case 'critica':
        case 'critical':
            safetyIndex = 25;
            break;
    }

    return safetyIndex;
}

// Función para actualizar las recomendaciones
function updateRecommendations(recommendations) {
    const recommendationsList = document.getElementById('recommendations-list');
    recommendationsList.innerHTML = '';

    // Verificar si hay recomendaciones y son un array o un objeto
    if (recommendations) {
        // Si es un array, mostrar cada elemento
        if (Array.isArray(recommendations) && recommendations.length > 0) {
            recommendations.forEach(rec => {
                if (typeof rec === 'string') {
                    const li = document.createElement('li');
                    li.textContent = rec;
                    recommendationsList.appendChild(li);
                }
            });
        }
        // Si es un objeto que contiene recomendaciones específicas
        else if (typeof recommendations === 'object' && recommendations !== null) {
            // Buscar array de recomendaciones dentro del objeto
            let recArray = null;

            // Buscar en campos comunes
            if (Array.isArray(recommendations.recommendations)) {
                recArray = recommendations.recommendations;
            } else if (recommendations.general && Array.isArray(recommendations.general)) {
                recArray = recommendations.general;
            }

            if (recArray && recArray.length > 0) {
                recArray.forEach(rec => {
                    if (typeof rec === 'string') {
                        const li = document.createElement('li');
                        li.textContent = rec;
                        recommendationsList.appendChild(li);
                    }
                });
            } else {
                // Si no hay array pero hay propiedades, mostrar cada propiedad
                let foundRecommendations = false;

                for (const key in recommendations) {
                    if (typeof recommendations[key] === 'string') {
                        const li = document.createElement('li');
                        li.textContent = recommendations[key];
                        recommendationsList.appendChild(li);
                        foundRecommendations = true;
                    }
                }

                if (!foundRecommendations) {
                    const li = document.createElement('li');
                    li.textContent = 'No hay recomendaciones específicas disponibles';
                    recommendationsList.appendChild(li);
                }
            }
        } else if (typeof recommendations === 'string') {
            // Es una sola recomendación en forma de string
            const li = document.createElement('li');
            li.textContent = recommendations;
            recommendationsList.appendChild(li);
        } else {
            const li = document.createElement('li');
            li.textContent = 'No hay recomendaciones disponibles';
            recommendationsList.appendChild(li);
        }
    } else {
        const li = document.createElement('li');
        li.textContent = 'No hay recomendaciones disponibles';
        recommendationsList.appendChild(li);
    }
}

// Función para actualizar los reportes en las pestañas
function updateReports(reports) {
    if (reports.citizens) {
        document.getElementById('citizen-report').innerHTML = formatReport(reports.citizens);
    }

    if (reports.authorities) {
        document.getElementById('authority-report').innerHTML = formatReport(reports.authorities);
    }

    if (reports.media) {
        document.getElementById('media-report').innerHTML = formatReport(reports.media);
    }
}

// Función para formatear reportes (convertir texto plano a HTML con formato)
function formatReport(reportText) {
    let formattedText = '';

    // Si es un objeto, formatear de manera legible
    if (typeof reportText === 'object' && reportText !== null) {
        // Extraer campos clave
        if (reportText.report_title) {
            formattedText += `<h3>${reportText.report_title}</h3>`;
        }

        if (reportText.incident_summary) {
            formattedText += `<p class="summary">${reportText.incident_summary}</p>`;
        }

        if (reportText.traffic_impact) {
            formattedText += `<p><strong>Impacto vial:</strong> ${reportText.traffic_impact}</p>`;
        }

        if (reportText.affected_vialities) {
            formattedText += `<p><strong>Vialidades afectadas:</strong> ${reportText.affected_vialities}</p>`;
        }

        if (reportText.alternative_routes) {
            formattedText += `<p><strong>Rutas alternativas:</strong> ${reportText.alternative_routes}</p>`;
        }

        if (reportText.estimated_duration) {
            formattedText += `<p><strong>Duración estimada:</strong> ${reportText.estimated_duration}</p>`;
        }

        // Si hay recomendaciones, mostrarlas como lista
        if (reportText.recommendations && Array.isArray(reportText.recommendations)) {
            formattedText += `<h4>Recomendaciones:</h4><ul>`;
            reportText.recommendations.forEach(rec => {
                formattedText += `<li>${rec}</li>`;
            });
            formattedText += `</ul>`;
        } else if (reportText.recommendations) {
            formattedText += `<h4>Recomendaciones:</h4><p>${reportText.recommendations}</p>`;
        }
    } else if (typeof reportText === 'string') {
        // Reemplazar saltos de línea con <br> y formatear
        formattedText = reportText.replace(/\n/g, '<br>');

        // Resaltar secciones importantes
        formattedText = formattedText.replace(/ALERTA:/gi, '<strong class="alert-text">ALERTA:</strong>');
        formattedText = formattedText.replace(/RECOMENDACIÓN:/gi, '<strong class="recommendation-text">RECOMENDACIÓN:</strong>');
    } else {
        formattedText = "No hay información disponible";
    }

    return formattedText;
}

// Función para actualizar la gráfica de incidentes
function updateIncidentsChart(incidents) {
    const ctx = document.getElementById('incidents-chart').getContext('2d');

    console.log("Datos para gráfica:", incidents); // Para depuración

    // Contar tipos de incidentes
    const incidentTypes = {};

    if (!incidents || incidents.length === 0) {
        incidentTypes['Sin datos'] = 1;
    } else {
        incidents.forEach(incident => {
            // Normalizar el campo de tipo
            let type = 'Desconocido';

            if (incident.tipo_incidente) {
                type = incident.tipo_incidente;
            } else if (incident.tipo) {
                type = incident.tipo;
            }

            // Verificar si el tipo está vacío o es null/undefined
            if (!type || type === 'null' || type === 'undefined' || type === 'None') {
                type = 'Desconocido';
            }

            // Formatear los tipos para ser más legibles
            type = type.toString().charAt(0).toUpperCase() + type.toString().slice(1);
            type = type.replace(/_/g, ' ');

            // Agrupar tipos similares
            if (type.toLowerCase().includes('robo')) {
                type = 'Robo';
            } else if (type.toLowerCase().includes('accidente')) {
                type = 'Accidente vial';
            } else if (type.toLowerCase().includes('bloqueo')) {
                type = 'Bloqueo vial';
            } else if (type.toLowerCase().includes('homicidio')) {
                type = 'Homicidio';
            } else if (type.toLowerCase().includes('detención') || type.toLowerCase().includes('detencion')) {
                type = 'Detención';
            } else if (type.toLowerCase().includes('ataque') || type.toLowerCase().includes('violencia')) {
                type = 'Ataque/Violencia';
            }

            incidentTypes[type] = (incidentTypes[type] || 0) + 1;
            console.log(`Contando incidente tipo: ${type}, total ahora: ${incidentTypes[type]}`); // Para depuración
        });
    }

    // Preparar datos para la gráfica
    const labels = Object.keys(incidentTypes);
    const data = Object.values(incidentTypes);

    console.log("Etiquetas de gráfica:", labels); // Para depuración
    console.log("Valores de gráfica:", data); // Para depuración

    // Asignar colores específicos a cada tipo de incidente
    const backgroundColors = labels.map(label => {
        const normalizedLabel = label.toLowerCase();

        if (normalizedLabel.includes('robo')) {
            return '#F44336'; // Rojo
        } else if (normalizedLabel.includes('accidente') || normalizedLabel.includes('vial')) {
            return '#FF9800'; // Naranja
        } else if (normalizedLabel.includes('homicidio')) {
            return '#D32F2F'; // Rojo oscuro
        } else if (normalizedLabel.includes('bloqueo')) {
            return '#FFC107'; // Ámbar
        } else if (normalizedLabel.includes('detención') || normalizedLabel.includes('detencion')) {
            return '#9C27B0'; // Púrpura
        } else if (normalizedLabel.includes('ataque') || normalizedLabel.includes('violencia')) {
            return '#E91E63'; // Rosa
        } else if (normalizedLabel.includes('sin datos')) {
            return '#607D8B'; // Gris azulado
        } else {
            return '#9C27B0'; // Púrpura
        }
    });

    // Crear gráfica con tema oscuro y colores ajustados
    if (window.incidentsChart) {
        window.incidentsChart.destroy();
    }

    // Opciones avanzadas de la gráfica
    Chart.defaults.color = '#E1BEE7'; // Color para textos

    window.incidentsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Incidentes por tipo',
                data: data,
                backgroundColor: backgroundColors,
                borderColor: backgroundColors.map(color => color),
                borderWidth: 1,
                barThickness: 40,
                maxBarThickness: 60
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false,
                    labels: {
                        color: '#E1BEE7' // Color claro para texto en tema oscuro
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(30, 30, 30, 0.9)',
                    titleColor: '#E1BEE7',
                    bodyColor: '#E1BEE7',
                    titleFont: {
                        size: 14,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 14
                    },
                    padding: 10,
                    displayColors: true,
                    usePointStyle: true,
                    callbacks: {
                        // Personalizar el texto del tooltip
                        label: function (context) {
                            return `Total: ${context.parsed.y} incidente(s)`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,              // Incrementos de 1 en el eje y
                        precision: 0,              // Sin decimales
                        color: '#E1BEE7',         // Color claro para texto
                        font: {
                            size: 12              // Tamaño de fuente
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)' // Líneas de cuadrícula más claras
                    }
                },
                x: {
                    ticks: {
                        color: '#E1BEE7',         // Color claro para texto
                        font: {
                            size: 12              // Tamaño de fuente
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)' // Líneas de cuadrícula más claras
                    }
                }
            },
            animation: {
                duration: 1500,                  // Duración de la animación en ms
                easing: 'easeOutQuart'            // Tipo de efecto
            }
        }
    });
}

// Función para crear marcadores de incidentes
function createIncidentMarkers(incidents) {
    // Validar entrada
    if (!incidents || !Array.isArray(incidents)) {
        console.error('Datos de incidentes inválidos:', incidents);
        return;
    }

    console.log(`Creando marcadores para ${incidents.length} incidentes`);

    // Datos para mapa de calor
    const heatmapData = [];
    let validMarkers = 0;

    incidents.forEach((incident, index) => {
        // Verificar si el incidente tiene coordenadas válidas
        let hasValidCoords = false;
        let lat = null;
        let lng = null;

        if (incident.coordenadas && incident.coordenadas.lat && incident.coordenadas.lng) {
            lat = parseFloat(incident.coordenadas.lat);
            lng = parseFloat(incident.coordenadas.lng);
            hasValidCoords = !isNaN(lat) && !isNaN(lng);
        }

        // Si no hay coordenadas, intentar geocodificar on-the-fly (esto requeriría un servicio backend)
        if (!hasValidCoords && incident.lugar) {
            console.log(`Incidente sin coordenadas: ${incident.lugar}`);
            // Aquí podrías implementar una solicitud al backend para geocodificar
            // Por ahora, saltamos este incidente
            return;
        }

        if (!hasValidCoords) {
            console.log(`Incidente #${index} sin coordenadas válidas`, incident);
            return;
        }

        // Determinar el icono basado en el tipo de incidente
        let iconType = 'otro';

        if (incident.tipo || incident.tipo_incidente) {
            const tipo = (incident.tipo || incident.tipo_incidente).toLowerCase();

            // Determinar la categoría
            if (tipo.includes('accidente') || tipo.includes('vial')) {
                iconType = 'accidente_vial';
            } else if (tipo.includes('bloqueo')) {
                iconType = 'bloqueo_vial';
            } else if (tipo.includes('robo') && tipo.includes('veh')) {
                iconType = 'robo_vehículo';
            } else if (tipo.includes('robo') && tipo.includes('casa')) {
                iconType = 'robo_casa';
            } else if (tipo.includes('robo') && tipo.includes('trans')) {
                iconType = 'robo_transeúnte';
            } else if (tipo.includes('homicidio') || tipo.includes('asesinat')) {
                iconType = 'homicidio_doloso';
            }
        }

        // Verificar si el icono existe, sino usar uno por defecto
        const icon = incidentIcons[iconType] || incidentIcons.otro;

        // Asegurarse de que se use un título significativo
        const title = incident.titulo || incident.noticia || 'Incidente';

        try {
            // Crear marcador
            const marker = L.marker([lat, lng], {
                icon: icon,
                title: title
            });

            // Crear contenido del popup
            const popupContent = `
                <div class="incident-popup">
                    <h3>${title}</h3>
                    <p><strong>Lugar:</strong> ${incident.lugar || 'No especificado'}</p>
                    <p><strong>Fecha/Hora:</strong> ${incident.fecha_incidente || incident.fecha || '-'} ${incident.hora_incidente || incident.hora || ''}</p>
                    <p><strong>Tipo:</strong> ${formatIncidentType(incident.tipo_incidente || incident.tipo || 'No especificado')}</p>
                    <p><strong>Gravedad:</strong> ${incident.gravedad || 'No especificada'}</p>
                    <p><strong>Impacto vial:</strong> ${incident.impacto_vial || 'No especificado'}</p>
                    <div class="popup-summary">${incident.resumen || 'No hay detalles disponibles'}</div>
                    ${incident.url ? `<a href="${incident.url}" target="_blank" class="popup-link">Ver noticia completa</a>` : ''}
                </div>
            `;

            // Asignar evento de clic
            marker.bindPopup(popupContent);
            marker.on('click', () => showIncidentDetails(incident));

            // Añadir al clúster
            markerClusterGroup.addLayer(marker);
            markers.push(marker);
            validMarkers++;

            // Añadir datos para el mapa de calor
            // Intensidad basada en la gravedad
            let intensity = 0.5;
            if (incident.gravedad) {
                const gravedad = incident.gravedad.toLowerCase();
                switch (gravedad) {
                    case 'baja': intensity = 0.3; break;
                    case 'media': intensity = 0.5; break;
                    case 'alta': intensity = 0.7; break;
                    case 'crítica':
                    case 'critica': intensity = 1.0; break;
                }
            }

            heatmapData.push([lat, lng, intensity]);
        } catch (error) {
            console.error(`Error creando marcador para incidente #${index}:`, error);
        }
    });

    console.log(`Se crearon ${validMarkers} marcadores válidos de ${incidents.length} incidentes`);

    // Crear capa de mapa de calor si hay datos
    if (heatLayer) {
        map.removeLayer(heatLayer);
    }

    if (heatmapData.length > 0) {
        // Agrupar puntos para identificar áreas con múltiples incidentes
        const groupedPoints = {};

        heatmapData.forEach(point => {
            // Redondear coordenadas para agrupar puntos cercanos (precisión de ~100m)
            const roundedLat = Math.round(point[0] * 1000) / 1000;
            const roundedLng = Math.round(point[1] * 1000) / 1000;
            const key = `${roundedLat},${roundedLng}`;

            if (!groupedPoints[key]) {
                groupedPoints[key] = {
                    lat: point[0],
                    lng: point[1],
                    count: 1,
                    intensity: point[2]
                };
            } else {
                groupedPoints[key].count += 1;
                groupedPoints[key].intensity += point[2];
            }
        });

        // Construir nuevos datos para el mapa de calor, aumentando la intensidad 
        // en áreas con múltiples incidentes
        const enhancedHeatData = [];

        Object.values(groupedPoints).forEach(point => {
            // Si hay múltiples incidentes en el mismo lugar, aumentar la intensidad
            let finalIntensity = point.intensity;

            if (point.count > 1) {
                // Aumentar intensidad exponencialmente con el número de incidentes
                finalIntensity = Math.min(1.0, point.intensity * Math.sqrt(point.count));
            } else {
                // Para incidentes únicos, reducir un poco la intensidad
                finalIntensity = point.intensity * 0.5;
            }

            enhancedHeatData.push([point.lat, point.lng, finalIntensity]);
        });

        // Crear la capa de calor con parámetros mejorados
        heatLayer = L.heatLayer(enhancedHeatData, {
            radius: 35,         // Aumentado para mejor visibilidad
            blur: 20,           // Aumentado para suavizar bordes
            maxZoom: 17,
            minOpacity: 0.4,    // Aumentada para mayor visibilidad
            max: 1.0,           // Valor máximo para normalización
            gradient: {
                0.2: 'blue',
                0.4: 'lime',
                0.6: 'yellow',
                0.8: 'orange',
                1.0: 'red'
            }
        });

        // No añadir al mapa inmediatamente, se hará con el botón toggle
    }

    // Si no hay marcadores, mostrar un mensaje
    if (validMarkers === 0) {
        showNotification("No hay incidentes con ubicaciones válidas", "warning");
    }
}

// Función para limpiar todos los marcadores
function clearMarkers() {
    markerClusterGroup.clearLayers();
    markers = [];

    if (heatLayer && map.hasLayer(heatLayer)) {
        map.removeLayer(heatLayer);
    }
}

// Función para mostrar detalles de un incidente específico
function showIncidentDetails(incident) {
    // Actualizar la información en el panel lateral
    updateMainIncidentInfo(incident);

    // Desplazarse al panel de información (en móviles)
    if (window.innerWidth < 768) {
        document.querySelector('.info-card').scrollIntoView({ behavior: 'smooth' });
    }
}

// Función para actualizar la hora de última actualización
function updateLastUpdateTime(timestamp) {
    const lastUpdate = document.getElementById('last-update');
    if (timestamp) {
        const date = new Date(timestamp);
        lastUpdate.textContent = date.toLocaleString();
    } else {
        lastUpdate.textContent = 'Desconocido';
    }
}

// Función para mostrar/ocultar indicador de carga
function showLoadingIndicator(show) {
    // Implementar indicador de carga (puede ser un spinner o mensaje)
    const refreshButton = document.getElementById('refresh-data');

    if (show) {
        refreshButton.disabled = true;
        refreshButton.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg> Cargando...';
    } else {
        refreshButton.disabled = false;
        refreshButton.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg> Actualizar Datos';
    }
}

// Función para mostrar mensajes de error
function showError(message) {
    alert(message);
}

// Función para alternar el mapa de calor
function toggleHeatmap() {
    if (!heatLayer) return;

    if (heatmapActive) {
        map.removeLayer(heatLayer);
    } else {
        map.addLayer(heatLayer);
    }

    heatmapActive = !heatmapActive;

    // Actualizar texto del botón
    const toggleButton = document.getElementById('toggle-heatmap');
    toggleButton.textContent = heatmapActive ? 'Ocultar Mapa de Calor' : 'Mostrar Mapa de Calor';
}

// Función para buscar municipio
function searchMunicipality() {
    const selectedValue = document.getElementById('municipality-select').value;

    if (!selectedValue) return;

    // Coordenadas y zoom para cada municipio
    const municipalities = {
        'queretaro': { center: [20.5888, -100.3899], zoom: 13 },
        'corregidora': { center: [20.5522, -100.4422], zoom: 13 },
        'san-juan-del-rio': { center: [20.3894, -99.9953], zoom: 13 },
        'el-marques': { center: [20.6272, -100.2389], zoom: 13 },
        'huimilpan': { center: [20.5500, -100.4167], zoom: 13 }
    };

    if (municipalities[selectedValue]) {
        map.setView(municipalities[selectedValue].center, municipalities[selectedValue].zoom);
    }
}

// Función para resetear la vista del mapa
function resetMapView() {
    map.setView(mapConfig.center, mapConfig.zoom);
}

// Función para obtener la ubicación del usuario
function locateUser() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function (position) {
                map.setView([position.coords.latitude, position.coords.longitude], 15);
            },
            function (error) {
                showError('No se pudo obtener tu ubicación: ' + error.message);
            },
            { timeout: 10000, enableHighAccuracy: true }
        );
    } else {
        showError('Geolocalización no soportada en tu navegador');
    }
}

// Función para solicitar actualización manual de datos
async function refreshData() {
    try {
        showLoadingIndicator(true);

        // Solicitar actualización al backend
        const response = await fetch('/api/trigger_update', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            // Cargar los nuevos datos
            await loadSecurityData();

            // También actualizar las últimas noticias
            if (typeof loadLatestNews === 'function') {
                await loadLatestNews();
            }

            showLoadingIndicator(false);
            showNotification("Datos actualizados correctamente", "success");
        } else {
            showLoadingIndicator(false);
            showError('No se pudo actualizar los datos');
        }
    } catch (error) {
        console.error('Error actualizando datos:', error);
        showLoadingIndicator(false);
        showError('Error de conexión al actualizar datos');
    }
}
// Manejador para pestañas
function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');

    tabButtons.forEach(button => {
        button.addEventListener('click', function () {
            // Desactivar todos los botones y paneles
            tabButtons.forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

            // Activar el botón y panel seleccionado
            this.classList.add('active');
            const tabName = this.getAttribute('data-tab');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });
}

// Sistema de comentarios
function setupComments() {
    const commentInput = document.getElementById('comment-input');
    const submitComment = document.getElementById('submit-comment');
    const commentsList = document.getElementById('comments-list');

    // Cargar comentarios guardados en localStorage
    loadComments();

    submitComment.addEventListener('click', function () {
        const text = commentInput.value.trim();
        if (text) {
            // Crear nuevo comentario
            addComment(text);

            // Guardar en localStorage
            saveComment(text);

            // Limpiar entrada
            commentInput.value = '';
        }
    });

    // Permitir envío con Enter
    commentInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            submitComment.click();
        }
    });
}

// Función para añadir un comentario a la UI
function addComment(text) {
    const commentsList = document.getElementById('comments-list');
    const comment = document.createElement('div');
    comment.className = 'comment';

    comment.innerHTML = `
        <p>${text}</p>
        <div class="comment-actions">
            <button class="like">👍 <span>0</span></button>
            <button class="dislike">👎 <span>0</span></button>
        </div>
    `;

    // Añadir al principio para que el más reciente aparezca primero
    commentsList.insertBefore(comment, commentsList.firstChild);

    // Configurar botones de like/dislike
    const likeButton = comment.querySelector('.like');
    const dislikeButton = comment.querySelector('.dislike');

    likeButton.addEventListener('click', function () {
        const countSpan = this.querySelector('span');
        countSpan.textContent = parseInt(countSpan.textContent) + 1;
    });

    dislikeButton.addEventListener('click', function () {
        const countSpan = this.querySelector('span');
        countSpan.textContent = parseInt(countSpan.textContent) + 1;
    });
}

// Guardar comentario en localStorage
function saveComment(text) {
    let comments = JSON.parse(localStorage.getItem('securityAppComments') || '[]');
    comments.unshift({
        text: text,
        date: new Date().toISOString(),
        likes: 0,
        dislikes: 0
    });

    // Limitar a 50 comentarios
    if (comments.length > 50) {
        comments = comments.slice(0, 50);
    }

    localStorage.setItem('securityAppComments', JSON.stringify(comments));
}

// Cargar comentarios desde localStorage
function loadComments() {
    const comments = JSON.parse(localStorage.getItem('securityAppComments') || '[]');

    comments.forEach(comment => {
        addComment(comment.text);
    });
}

// Función para cargar las últimas noticias
async function loadLatestNews() {
    try {
        const newsContainer = document.getElementById('latest-news-container');
        newsContainer.innerHTML = '<div class="loading-spinner">Cargando noticias recientes...</div>';

        const response = await fetch('/api/latest_news');

        if (!response.ok) {
            throw new Error('Error cargando noticias');
        }

        const data = await response.json();

        if (!data.latest_news || data.latest_news.length === 0) {
            newsContainer.innerHTML = '<p>No hay noticias recientes disponibles</p>';
            return;
        }

        // Limpiar contenedor
        newsContainer.innerHTML = '';

        // Añadir cada noticia
        data.latest_news.forEach(news => {
            const newsCard = document.createElement('div');
            newsCard.className = 'news-card';

            // Obtener título
            const title = news.titulo || news.noticia || 'Noticia sin título';

            // Formatear fecha si existe
            let dateText = news.fecha_incidente || news.fecha || 'Fecha no disponible';
            let timeText = news.hora_incidente || news.hora || '';
            if (timeText) {
                dateText += ' a las ' + timeText;
            }

            // Tipo y lugar
            const type = formatIncidentType(news.tipo_incidente || news.tipo || 'Otro');
            const location = news.lugar || 'Ubicación no especificada';

            // Resumen
            const summary = news.resumen || 'No hay detalles disponibles';

            // Construir HTML de la tarjeta
            newsCard.innerHTML = `
                <h4>${title}</h4>
                <div class="news-meta">
                    <span>${dateText}</span>
                    <div>
                        <span class="news-location">${location}</span>
                        <span class="news-type">${type}</span>
                    </div>
                </div>
                <div class="news-summary">${summary}</div>
                ${news.url ? `<a href="${news.url}" target="_blank" class="news-link">Ver noticia completa</a>` : ''}
            `;

            // Añadir al contenedor
            newsContainer.appendChild(newsCard);

            // Añadir evento para ver los detalles en el panel principal
            newsCard.addEventListener('click', function () {
                // Mostrar detalles en el panel principal
                showIncidentDetails(news);

                // Si hay coordenadas, centrar el mapa
                if (news.coordenadas && news.coordenadas.lat && news.coordenadas.lng) {
                    map.setView([news.coordenadas.lat, news.coordenadas.lng], 15);
                }
            });
        });

    } catch (error) {
        console.error('Error cargando noticias recientes:', error);
        document.getElementById('latest-news-container').innerHTML =
            '<p>Error cargando noticias recientes. Intente nuevamente más tarde.</p>';
    }
}

// Configurar eventos al cargar la página
document.addEventListener('DOMContentLoaded', function () {
    // Inicializar el mapa
    initMap();

    // Configurar pestañas
    setupTabs();

    // Configurar comentarios
    setupComments();

    // Cargar las últimas noticias
    loadLatestNews();

    // Configurar eventos de botones
    document.getElementById('search-municipality').addEventListener('click', searchMunicipality);
    document.getElementById('municipality-select').addEventListener('change', searchMunicipality);
    document.getElementById('reset-view').addEventListener('click', resetMapView);
    document.getElementById('locate-me').addEventListener('click', locateUser);
    document.getElementById('toggle-heatmap').addEventListener('click', toggleHeatmap);
    document.getElementById('refresh-data').addEventListener('click', refreshData);

    // Mostrar panel de información
    document.getElementById('info-content').classList.add('active');
    document.addEventListener('DOMContentLoaded', fetchAndUpdateChart);

});