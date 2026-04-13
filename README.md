# 🚚 Hackyardigans — Logística Inteligente para Tiendas 3B

> **Proyecto desarrollado durante el Hackathon Tiendas 3B 2026**
> Equipo: **Hackyardigans**

Sistema integral de optimización de rutas de entrega que combina **OR-Tools** (Google) para resolver el Problema de Ruteo de Vehículos (VRP) con la **API de Mapbox** para obtener distancias reales entre puntos, minimizando el costo operativo de la flota de distribución de Tiendas 3B.

---

## 📐 Arquitectura del Sistema

```
hackaton-3b/
├── backend/                  # API REST en FastAPI
│   ├── main.py               # Endpoints y lógica principal
│   ├── data_processor.py     # Carga JSON + llamada a Mapbox Matrix API
│   ├── solver.py             # Motor de optimización OR-Tools (VRP)
│   ├── simulator.py          # Monitor de terminal para el pitch
│   └── requirements.txt      # Dependencias Python
│
├── frontend/                 # Interfaz web estática
│   ├── pages/
│   │   ├── index.html        # Dashboard principal (selección de rol)
│   │   ├── logistica.html    # Vista CEDIS: mapa interactivo + rutas
│   │   └── tienda.html       # Vista Tienda: semáforo de entrega
│   ├── js/
│   │   ├── logistica.js      # Lógica Mapbox GL + llamadas a la API
│   │   ├── tienda.js         # Polling de estado y confirmación
│   │   └── utils.js          # Base de datos de tiendas en el cliente
│   ├── css/                  # Estilos por vista
│   └── images/               # Recursos visuales
│
├── data/                     # Datos de entrada (JSONs)
│   ├── orders.json           # Órdenes del día con pallets por tienda
│   ├── products.json         # Catálogo de productos con presentaciones
│   ├── stores.json           # Tiendas con coordenadas geográficas
│   ├── warehouse.json        # Ubicación del CEDIS central
│   └── capacidades.json      # Flota: tipos de camión y capacidades
│
├── .env.example              # Plantilla de variables de entorno
└── README.md
```

---

## ⚙️ Requisitos Previos

- **Python 3.10+**
- **Cuenta en Mapbox** con un token de acceso público (`pk.`)
- Navegador moderno (Chrome, Edge, Firefox)
- Un servidor de archivos estáticos para el frontend (ej. Live Server de VS Code)

---

## 🚀 Instalación y Ejecución

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd hackaton-3b
```

### 2. Configurar variables de entorno

```bash
# Copiar la plantilla
cp .env.example .env
```

Edita el archivo `.env` y agrega tu token de Mapbox:

```
MAPBOX_ACCESS_TOKEN=pk.tu_token_real_aqui
SOLVER_TIME_LIMIT_SECONDS=30
CORS_ALLOWED_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

### 3. Instalar dependencias del backend

```bash
cd backend
pip install -r requirements.txt
```

### 4. Iniciar el servidor FastAPI

```bash
# Desde la carpeta backend/
uvicorn main:app --reload --port 8000
```

El servidor quedará disponible en: `http://localhost:8000`

Puedes ver la documentación interactiva de la API en: `http://localhost:8000/docs`

### 5. Abrir el frontend

Abre `frontend/pages/index.html` con un servidor local (recomendado: extensión **Live Server** de VS Code en el puerto 5500).

---

## 📡 Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Estado de salud de la API |
| `POST` | `/api/rutas/generar` | **Genera rutas optimizadas** — lee JSONs, llama a Mapbox, ejecuta OR-Tools |
| `GET` | `/api/rutas/activas` | Devuelve el estado actual de todas las rutas del día |
| `GET` | `/api/tienda/{store_id}/status` | Estado de entrega individual de una tienda |
| `POST` | `/api/tienda/recibir` | Confirma la recepción de mercancía en una tienda |

### Ejemplo — Generar Rutas

```bash
curl -X POST http://localhost:8000/api/rutas/generar
```

Respuesta exitosa:
```json
{
  "status": "success",
  "mensaje": "Rutas optimizadas exitosamente.",
  "métricas_financieras": {
    "costo_total_operacion_mxn": 45000,
    "vehiculos_desplegados": 3
  },
  "rutas_generadas": [ ... ]
}
```

---

## 🖥️ Vistas del Frontend

### Dashboard (index.html)
Punto de entrada. Permite elegir entre la **Vista Logística** (para el CEDIS) y la **Vista Tienda** (para gerentes de sucursal).

### Vista Logística (logistica.html)
- Mapa interactivo **Mapbox GL** con todas las rutas del día
- Botón **"Optimizar Rutas del Día"** que dispara el endpoint `POST /api/rutas/generar`
- Panel financiero con costo total de operación y vehículos desplegados
- Tarjetas individuales por camión con detalle de carga

### Vista Tienda (tienda.html)
- Selector de sucursal
- **Semáforo de entrega**: 🔴 Sin asignar → 🟡 En camino → 🟢 Confirmado
- Contador de tiendas previas antes de la entrega
- Botón de confirmación de recepción

---

## 🖥️ Simulador (Terminal)

Para hacer un seguimiento visual de la operación en terminal durante el pitch:

```bash
# Desde la carpeta backend/ (con el servidor ya corriendo)
python simulator.py
```

El simulador monitorea en tiempo real el avance de los camiones conforme las tiendas confirman la recepción desde el frontend.

---

## 🧠 Cómo funciona el Motor de Optimización

1. **Carga de datos**: `data_processor.py` lee los 5 JSONs y calcula la demanda en kg y tarimas por tienda.
2. **Matriz de distancias**: Llama a la **Mapbox Matrix API** para obtener distancias reales en metros entre todos los puntos (CEDIS + tiendas).
3. **OR-Tools VRP**: `solver.py` construye un modelo con 3 dimensiones:
   - **Capacidad de peso (kg)** por vehículo
   - **Capacidad de tarimas** por vehículo
   - **Costo fijo** por vehículo (para minimizar el gasto total)
4. **Estrategia de búsqueda**: `PATH_CHEAPEST_ARC` como solución inicial + `GUIDED_LOCAL_SEARCH` para mejora local.

---

## 👥 Equipo Hackyardigans

Desarrollado con ❤️ durante el Hackathon Tiendas 3B 2026.
