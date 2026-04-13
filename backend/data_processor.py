import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

# Cargar variables de entorno desde .env (si existe)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Configuración — el token se lee desde la variable de entorno MAPBOX_ACCESS_TOKEN
MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "")
if not MAPBOX_ACCESS_TOKEN:
    raise EnvironmentError(
        "No se encontró MAPBOX_ACCESS_TOKEN. "
        "Crea un archivo .env en la raíz del proyecto con ese valor "
        "(consulta .env.example para más detalles)."
    )

def parse_weight_to_kg(presentation_str):
    """Convierte cadenas como '120 gr', '500 ml' o '10 lt' a kilogramos flotantes."""
    match = re.match(r"([\d\.]+)\s*(gr|ml|lt)", str(presentation_str).strip().lower())
    if not match:
        return 0.0
    
    value = float(match.group(1))
    unit = match.group(2)
    
    if unit in ['gr', 'ml']:
        return value / 1000.0  # 1000 gr o ml = 1 kg
    elif unit == 'lt':
        return value           # 1 lt = 1 kg (aprox para bebidas)
    return 0.0

# Directorio raíz del proyecto (un nivel arriba del backend/)
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"


def load_data():
    """Carga los 5 archivos JSON desde el directorio /data."""
    with open(DATA_DIR / 'warehouse.json', 'r', encoding='utf-8') as f:
        warehouse = json.load(f)
    with open(DATA_DIR / 'capacidades.json', 'r', encoding='utf-8') as f:
        capacities = json.load(f)
    with open(DATA_DIR / 'orders.json', 'r', encoding='utf-8') as f:
        orders_data = json.load(f)
    with open(DATA_DIR / 'products.json', 'r', encoding='utf-8') as f:
        products = json.load(f)
    with open(DATA_DIR / 'stores.json', 'r', encoding='utf-8') as f:
        stores = json.load(f)

    return warehouse, capacities, orders_data, products, stores

def get_mapbox_matrix(coordinates):
    """Llama a la API de Mapbox Matrix para obtener la matriz de distancias (en metros)."""
    # Coordenadas formato: "lon,lat;lon,lat;..."
    coord_string = ";".join([f"{lon},{lat}" for lon, lat in coordinates])
    url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/driving/{coord_string}?annotations=distance&access_token={MAPBOX_ACCESS_TOKEN}"
    
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['distances']
    else:
        print(f"Error en Mapbox: {response.text}")
        # Retornamos una matriz vacía como fallback de seguridad
        return []

def build_data_model():
    """Función principal que el Rol 1 (OR-Tools) va a importar y ejecutar."""
    warehouse, capacities, orders_data, products, stores = load_data()
    
    # 1. Mapear IDs de productos a su peso en KG
    product_weights = {
        p["src_product_id"]: parse_weight_to_kg(p["presentation"]) 
        for p in products
    }
    
    # 2. Calcular la demanda total (en kg) Y TARIMAS por cada tienda
    store_demands = {store["store_id"]: 0.0 for store in stores}
    store_pallets = {store["store_id"]: 0 for store in stores} # NUEVO: Contador de tarimas
    
    for order in orders_data["orders"]:
        for delivery in order["deliveries"]:
            store_id = delivery["store_id"]
            
            # NUEVO: Contamos cuántas tarimas físicas van a esta tienda
            # Cada elemento en la lista 'pallets' de tu JSON es una tarima
            store_pallets[store_id] += len(delivery["pallets"]) 
            
            for pallet in delivery["pallets"]:
                sku = pallet["sku"]
                units = pallet["units"]
                weight_per_unit = product_weights.get(sku, 0.0)
                store_demands[store_id] += (weight_per_unit * units)
                
    # 3. Construir la lista de Nodos (Índice 0 = Warehouse, Índice 1..N = Tiendas)
    active_stores = [s for s in stores if store_demands[s["store_id"]] > 0]
    
    # NUEVO: Agregamos las tarimas (pallets) al nodo base (CEDIS pide 0)
    nodes = [{"id": warehouse["warehouse_id"], "lat": warehouse["lat"], "lon": warehouse["lon"], "demand": 0.0, "pallets": 0}]
    for store in active_stores:
        nodes.append({
            "id": store["store_id"],
            "lat": store["lat"],
            "lon": store["lon"],
            "demand": store_demands[store["store_id"]],
            "pallets": store_pallets[store["store_id"]] # NUEVO: Asignamos sus tarimas calculadas
        })
        
    # 4. Extraer demandas, tarimas y coordenadas en orden
    demands = [int(node["demand"]) for node in nodes] 
    pallet_demands = [node["pallets"] for node in nodes] # Arreglo de tarimas demandadas
    coordinates = [(node["lon"], node["lat"]) for node in nodes]
    
    # 5. Obtener matriz de distancias reales desde Mapbox
    print("Solicitando matriz de distancias a Mapbox...")
    distance_matrix = get_mapbox_matrix(coordinates)
    
    # 6. Preparar las capacidades de los vehículos (Peso y Tarimas)
    vehicle_capacities = []
    vehicle_pallet_capacities = [] # NUEVO: Arreglo de capacidad de tarimas por camión
    vehicle_costs = [] #Costo$$
    
    for cap in capacities:
        cap_tarimas = 14 if cap["tipo"] == "Torton" else 4
        
        vehicle_capacities.extend([cap["cap_peso_kg"]] * cap["unidades"])
        vehicle_pallet_capacities.extend([cap_tarimas] * cap["unidades"])
        vehicle_costs.extend([int(cap["costo"])] * cap["unidades"]) #OR-Tools prefiere enteros para costos
    # 7. Empaquetar el diccionario final para OR-Tools
    data_model = {
        "distance_matrix": distance_matrix,
        "demands": demands,
        "pallet_demands": pallet_demands,
        "vehicle_capacities": vehicle_capacities,
        "vehicle_pallet_capacities": vehicle_pallet_capacities, 
        "vehicle_costs": vehicle_costs,
        "num_vehicles": len(vehicle_capacities),
        "depot": 0,  
        "node_ids": [node["id"] for node in nodes] 
    }
    
    return data_model

if __name__ == "__main__":
    # Prueba local rápida
    model = build_data_model()
    print("\n--- DATA MODEL GENERADO ---")
    print(f"Total de nodos (1 CEDIS + Tiendas activas): {len(model['node_ids'])}")
    print(f"Total de vehículos disponibles: {model['num_vehicles']}")
    print(f"Demanda del nodo 1 (en kg): {model['demands'][1] if len(model['demands']) > 1 else 0}")
