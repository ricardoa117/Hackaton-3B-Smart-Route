from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def solve_routing(data, time_limit_seconds: int = 30):
    """Resuelve el problema de ruteo de vehículos (VRP) con restricciones de
    peso (kg) y tarimas, optimizando el costo financiero de la flota.

    Args:
        data: Diccionario generado por data_processor.build_data_model().
        time_limit_seconds: Límite de tiempo en segundos para el solver (default 30).

    Returns:
        Diccionario con las rutas optimizadas o un dict de error.
    """
    # 1. Crear el administrador
    manager = pywrapcp.RoutingIndexManager(
        len(data['distance_matrix']), 
        data['num_vehicles'], 
        data['depot']
    )
    routing = pywrapcp.RoutingModel(manager)

    # 2. Distancias (Costo base)
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        
        # Obtenemos la distancia de Mapbox
        distancia = data['distance_matrix'][from_node][to_node]
        
        # EL FIX: Forzamos a que sea un número entero. Si Mapbox falla y manda None, devolvemos 0.
        return int(distancia) if distancia else 0

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # ==========================================
    # 3. DIMENSIÓN 1: Capacidad de Peso en KG
    # ==========================================
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0, 
        data['vehicle_capacities'],
        True,
        'Capacity_KG'
    )

    # ==========================================
    # 4. DIMENSIÓN 2: Capacidad de Tarimas
    # ==========================================
    def pallet_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['pallet_demands'][from_node]

    pallet_callback_index = routing.RegisterUnaryTransitCallback(pallet_callback)
    routing.AddDimensionWithVehicleCapacity(
        pallet_callback_index,
        0,
        data['vehicle_pallet_capacities'],
        True,
        'Capacity_Pallets'
    )

    # ==========================================
    # 5. DIMENSIÓN 3: Optimización de Costos Financieros (NUEVO)
    # ==========================================
    # Le decimos al modelo cuánto cuesta sacar cada camión del CEDIS.
    # Esto fuerza al algoritmo a preferir camiones más baratos si las distancias y capacidades lo permiten.
    for i in range(data['num_vehicles']):
        routing.SetFixedCostOfVehicle(data['vehicle_costs'][i], i)
    # ==========================================

    # 6. Parámetros de búsqueda
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.FromSeconds(time_limit_seconds)

    # 7. ¡Resolver!
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return {"status": "error", "message": "Imposible resolver: Verifica si hay tiendas que piden más tarimas o kilos de los que soporta el vehículo de mayor capacidad."}

    # 8. Formatear la salida para la API
    rutas_optimizadas = []
    costo_total_flota = 0 # NUEVO: Para llevar el control financiero total
    
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        ruta_indices = []
        ruta_nombres = []
        carga_kg = 0
        carga_tarimas = 0
        distancia_total = 0

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            ruta_indices.append(node_index)
            ruta_nombres.append(data['node_ids'][node_index])
            carga_kg += data['demands'][node_index]
            carga_tarimas += data['pallet_demands'][node_index]
            
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            distancia_total += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)

        node_index = manager.IndexToNode(index)
        ruta_indices.append(node_index)
        ruta_nombres.append(data['node_ids'][node_index])

        # Solo enviamos camiones que sí salieron de ruta
        if len(ruta_indices) > 2:
            nombres_tiendas = [n for n in ruta_nombres if n != data['node_ids'][data['depot']]]
            costo_vehiculo_actual = data['vehicle_costs'][vehicle_id] # NUEVO
            costo_total_flota += costo_vehiculo_actual # NUEVO
            
            rutas_optimizadas.append({
                "camion_id": vehicle_id,
                "costo_operativo": costo_vehiculo_actual, # NUEVO
                "capacidad_kg_max": data['vehicle_capacities'][vehicle_id],
                "capacidad_tarimas_max": data['vehicle_pallet_capacities'][vehicle_id],
                "carga_kg_total": carga_kg,
                "tarimas_totales": carga_tarimas,
                "ruta_indices": ruta_indices,
                "ruta_nombres": ruta_nombres,
                "distancia_total_metros": distancia_total,
                "detalle_asignacion": f"Lleva {carga_tarimas} tarimas en total para las tiendas: {', '.join(nombres_tiendas)}"
            })

    return {
        "status": "success",
        "costo_total_operacion": costo_total_flota, # NUEVO: La métrica reina para los jueces
        "vehiculos_utilizados": len(rutas_optimizadas),
        "rutas": rutas_optimizadas
    }

# Prueba Local
if __name__ == "__main__":
    mock_data = {
        "distance_matrix": [[0, 500, 1200], [500, 0, 800], [1200, 800, 0]],
        "demands": [0, 4500, 6000],
        "vehicle_capacities": [15000, 8000],
        "pallet_demands": [0, 4, 6],
        "vehicle_pallet_capacities": [14, 4],
        "vehicle_costs": [12000, 3000], # NUEVO: Costos agregados al mock de prueba
        "num_vehicles": 2,
        "depot": 0,
        "node_ids": ["CEDIS_01", "3B_015", "3B_042"]
    }
    
    import json
    resultado = solve_routing(mock_data)
    print(json.dumps(resultado, indent=2))
