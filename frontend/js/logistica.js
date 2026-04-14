// js/logistica.js - Lógica del Dashboard Central (CEDIS)

let map;
// Paleta de colores para diferenciar visualmente a cada camión en el mapa
const COLORS = ['#dc3545', '#0d6efd', '#198754', '#ffc107', '#6f42c1', '#fd7e14', '#20c997'];

/**
 * Inicializa el mapa base centrado en la Ciudad de México.
 */
function inicializarMapa() {
    // IMPORTANTE: Coloca aquí tu token público de Mapbox (el que empieza con pk.)
    mapboxgl.accessToken = process.env.MAPBOX_ACCESS_TOKEN;

    map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/light-v10',
        center: [-99.1332, 19.4326], // Centro de CDMX
        zoom: 10
    });

    // Poner el marcador fijo del CEDIS apenas cargue el mapa
    map.on('load', () => {
        const cedis = window.utils.STORES_DB["CEDIS_CDMX_01"];
        if (cedis) {
            new mapboxgl.Marker({ color: '#000000' })
                .setLngLat([cedis.lon, cedis.lat])
                .setPopup(new mapboxgl.Popup({ offset: 25 }).setHTML('<strong>CEDIS CENTRAL 3B</strong>'))
                .addTo(map);
        }
    });
}

/**
 * Recibe el JSON de la API y dibuja las líneas de los viajes.
 */
function dibujarRutasEnMapa(rutasGeneradas) {
    // 1. Limpiar el mapa de rutas anteriores si el gerente vuelve a calcular
    if (map.getSource('rutas_source')) {
        map.removeLayer('rutas_layer');
        map.removeSource('rutas_source');
    }

    const features = [];
    const marcadoresActivos = document.querySelectorAll('.mapboxgl-marker:not(:first-child)');
    marcadoresActivos.forEach(marker => marker.remove()); // Limpiamos marcadores (menos el CEDIS)

    // 2. Procesar cada camión devuelto por el backend
    rutasGeneradas.forEach((ruta, index) => {
        const colorRuta = COLORS[index % COLORS.length];

        // Convertir array de IDs ("3B_CDMX_001") a Coordenadas Geográficas [lon, lat]
        const coordenadas = ruta.paradas.map(id => {
            const tienda = window.utils.STORES_DB[id];
            return [tienda.lon, tienda.lat];
        });

        // Trazar la línea geométrica para Mapbox
        features.push({
            type: 'Feature',
            properties: { color: colorRuta },
            geometry: { type: 'LineString', coordinates: coordenadas }
        });

        // Poner un pin en cada tienda que visitará este camión
        coordenadas.forEach((coord, i) => {
            // Evitamos poner pin extra en el índice 0 y el último (que son el CEDIS)
            if (i > 0 && i < coordenadas.length - 1) {
                new mapboxgl.Marker({ color: colorRuta, scale: 0.8 })
                    .setLngLat(coord)
                    .setPopup(new mapboxgl.Popup({ offset: 25 }).setHTML(`
                        <strong>${window.utils.STORES_DB[ruta.paradas[i]].name}</strong><br>
                        <small>Turno en ruta: ${i}</small>
                    `))
                    .addTo(map);
            }
        });
    });

    // 3. Inyectar las líneas al motor del mapa
    map.addSource('rutas_source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: features }
    });

    map.addLayer({
        id: 'rutas_layer',
        type: 'line',
        source: 'rutas_source',
        paint: {
            'line-color': ['get', 'color'],
            'line-width': 5,
            'line-opacity': 0.8
        }
    });
}

// ==========================================
// Eventos Principales de la Pantalla
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    inicializarMapa();

    const btnGenerar = document.getElementById('btn_generar_rutas');

    if (btnGenerar) {
        btnGenerar.addEventListener('click', async (e) => {
            const btn = e.target;
            btn.disabled = true;
            btn.textContent = "Ejecutando OR-Tools...";
            document.getElementById('route-status').textContent = "Calculando la ruta más rentable...";

            try {
                // LLAMADA A TU API (Rol 3)
                const response = await fetch('http://localhost:8000/api/rutas/generar', { method: 'POST' });

                if (!response.ok) throw new Error("Error en el servidor FastAPI");

                const data = await response.json();

                if (data.status === "success") {
                    // --- Actualizar Panel Financiero ---
                    const panelFinanzas = document.getElementById('panel-finanzas');
                    if (panelFinanzas) {
                        panelFinanzas.style.display = 'block';
                        // Formatear a pesos mexicanos
                        const costoFormateado = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(data.métricas_financieras.costo_total_operacion_mxn);
                        document.getElementById('costo-operacion').textContent = costoFormateado;
                        document.getElementById('vehiculos-desplegados').textContent = `${data.métricas_financieras.vehiculos_desplegados} vehículos en operación`;
                    }

                    // --- Renderizar Tarjetas de Camiones ---
                    const listaDiv = document.getElementById('lista-rutas');
                    if (listaDiv) {
                        listaDiv.innerHTML = data.rutas_generadas.map(r =>
                            `<div class="card mb-2 shadow-sm border-0">
                                <div class="card-body p-2">
                                    <h6 class="mb-1 text-primary">🚚 ${r.vehiculo} (Ruta ${r.id_viaje.split('_')[2]})</h6>
                                    <p class="mb-0 small text-muted">${r.detalle_carga}</p>
                                    <span class="badge bg-success mt-1">Costo: $${r.costo_operativo}</span>
                                </div>
                            </div>`
                        ).join('');
                    }

                    // --- Actualizar Mapa ---
                    dibujarRutasEnMapa(data.rutas_generadas);
                    document.getElementById('route-status').textContent = "✅ Rutas asignadas y en tránsito.";
                } else {
                    alert("Error matemático: " + data.message);
                }

            } catch (error) {
                console.error("Error conectando con el backend:", error);
                alert("Error de conexión. Asegúrate de que tu servidor Uvicorn esté corriendo en el puerto 8000.");
                document.getElementById('route-status').textContent = "Error de conexión.";
            } finally {
                btn.disabled = false;
                btn.textContent = "Optimizar Rutas del Día";
            }
        });
    }
});