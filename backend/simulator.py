import requests
import time
import sys

# La dirección de tu API (FastAPI)
BASE_URL = "http://localhost:8000"

def print_estilo(mensaje, tipo="INFO"):
    """Le da colores a la terminal para que se vea espectacular en el pitch."""
    colores = {
        "INFO": "\033[94m",    # Azul
        "EXITO": "\033[92m",   # Verde
        "ALERTA": "\033[93m",  # Amarillo
        "ERROR": "\033[91m",   # Rojo
        "FIN": "\033[0m"       # Reset
    }
    print(f"{colores.get(tipo, '')}[{tipo}] {mensaje}{colores['FIN']}")

def monitorear_operacion():
    print_estilo("Iniciando Monitor Logístico 3B...", "INFO")
    print_estilo("Esperando a que el CEDIS genere las rutas...", "ALERTA")

    # 1. Esperar a que el gerente del CEDIS presione "Optimizar Rutas"
    while True:
        try:
            res = requests.get(f"{BASE_URL}/api/rutas/activas")
            if res.status_code == 200:
                data = res.json()
                rutas_activas = [r for r in data["rutas"] if r["estado"] != "completado"]
                
                if rutas_activas:
                    print_estilo(f"¡Señal recibida! {len(rutas_activas)} vehículos han salido del CEDIS.", "EXITO")
                    break
        except requests.exceptions.ConnectionError:
            print_estilo("No hay conexión con la API. ¿Está corriendo Uvicorn?", "ERROR")
            sys.exit(1)
        
        time.sleep(2)

    # Memoria para saber en qué parada va cada camión
    memoria_rutas = {}
    for ruta in rutas_activas:
        memoria_rutas[ruta["id_viaje"]] = ruta["parada_actual_index"]
        tienda_actual = ruta["paradas"][ruta["parada_actual_index"]]
        print_estilo(f"🚚 El {ruta['vehiculo']} se dirige a su primera parada: {tienda_actual}", "INFO")

    # 2. Bucle de Monitoreo Pasivo (Solo observa, NO hace clics)
    print_estilo("Esperando confirmación manual desde las sucursales...", "ALERTA")
    
    while True:
        res = requests.get(f"{BASE_URL}/api/rutas/activas")
        rutas = res.json()["rutas"]
        
        todas_completadas = True
        
        for ruta in rutas:
            id_viaje = ruta["id_viaje"]
            estado_actual = ruta["estado"]
            indice_actual = ruta["parada_actual_index"]
            
            if estado_actual != "completado":
                todas_completadas = False
                
                # Si el índice cambió, significa que la TIENDA presionó el botón en el Frontend
                if id_viaje in memoria_rutas and memoria_rutas[id_viaje] < indice_actual:
                    tienda_anterior = ruta["paradas"][memoria_rutas[id_viaje]]
                    
                    if indice_actual < len(ruta["paradas"]) - 1:
                        tienda_nueva = ruta["paradas"][indice_actual]
                        print_estilo(f"✅ Recepción confirmada en {tienda_anterior}. El {ruta['vehiculo']} avanza hacia {tienda_nueva}.", "EXITO")
                    else:
                        print_estilo(f"✅ Recepción confirmada en {tienda_anterior}. El {ruta['vehiculo']} terminó su ruta y regresa al CEDIS.", "EXITO")
                        
                    # Actualizamos la memoria del monitor
                    memoria_rutas[id_viaje] = indice_actual

        if todas_completadas:
            print("\n")
            print_estilo("🎉 ¡TODA LA OPERACIÓN DEL DÍA HA CONCLUIDO EXITOSAMENTE! 🎉", "EXITO")
            print_estilo("Todos los vehículos están de regreso en el CEDIS.", "INFO")
            break
            
        time.sleep(1.5) # Observa en silencio cada 1.5 segundos

if __name__ == "__main__":
    monitorear_operacion()