import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env en la raíz del proyecto
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Importamos tus módulos
import data_processor 
import solver 

app = FastAPI(title="API Logística Inteligente 3B", version="1.0.MVP")

# CORS: lee los orígenes permitidos desde la variable de entorno.
# Por defecto, solo permite localhost para el frontend de desarrollo.
_raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- BASE DE DATOS EN MEMORIA ---
db_rutas = {
    "rutas_activas": [],
    "estado_tiendas": {} 
}

class RecepcionMercancia(BaseModel):
    store_id: str
    comentarios: Optional[str] = "Sin comentarios"

@app.get("/")
def read_root():
    return {"status": "online", "mensaje": "API 3B Operativa - Integración OR-Tools Activa"}

@app.post("/api/rutas/generar")
def generar_rutas():
    """
    Endpoint principal. Lee datos, calcula distancias y optimiza con OR-Tools.
    """
    try:
        print("1. Construyendo modelo de datos (Mapbox + JSONs)...")
        data_model = data_processor.build_data_model()
        
        print("2. Ejecutando motor de optimización OR-Tools...")
        time_limit = int(os.getenv("SOLVER_TIME_LIMIT_SECONDS", "30"))
        resultado_solver = solver.solve_routing(data_model, time_limit_seconds=time_limit)
        
        # Validamos si OR-Tools encontró una solución matemática posible
        if resultado_solver.get("status") == "error":
            raise HTTPException(status_code=400, detail=resultado_solver.get("message"))
        
        # Limpiamos la "base de datos" para este nuevo día de operación
        db_rutas["rutas_activas"] = []
        db_rutas["estado_tiendas"] = {}
        
        rutas_procesadas = []
        costo_total = resultado_solver.get("costo_total_operacion", 0)
        
        # Procesamos la respuesta del solver para guardarla en memoria y enviarla al Frontend
        for ruta in resultado_solver["rutas"]:
            paradas_reales = ruta["ruta_nombres"] # Ej: ["CEDIS_01", "3B_015", "3B_042", "CEDIS_01"]
            
            # Determinamos el tipo de vehículo basado en su capacidad para la UI
            tipo_vehiculo = "Torton" if ruta["capacidad_tarimas_max"] >= 14 else "Camión"
            
            ruta_info = {
                "id_viaje": f"VIAJE_{tipo_vehiculo.upper()}_{ruta['camion_id']}_{datetime.now().strftime('%H%M')}",
                "vehiculo": tipo_vehiculo,
                "costo_operativo": ruta["costo_operativo"],
                "paradas": paradas_reales,
                "parada_actual_index": 1, # El índice 0 es el CEDIS, el 1 es la primera tienda
                "estado": "en_transito",
                "detalle_carga": ruta["detalle_asignacion"]
            }
            rutas_procesadas.append(ruta_info)
            db_rutas["rutas_activas"].append(ruta_info)
            
            # Actualizamos el estado individual de cada tienda (Omitimos el inicio y fin que son el CEDIS)
            for i, store_id in enumerate(paradas_reales[1:-1]): 
                db_rutas["estado_tiendas"][store_id] = {
                    "id_viaje": ruta_info["id_viaje"],
                    "estado": "en_camino",
                    "turno_en_ruta": i + 1, # Tienda 1 es turno 1, Tienda 2 es turno 2...
                    "recibido": False
                }
                
        return {
            "status": "success", 
            "mensaje": "Rutas optimizadas exitosamente.",
            "métricas_financieras": {
                "costo_total_operacion_mxn": costo_total,
                "vehiculos_desplegados": resultado_solver.get("vehiculos_utilizados", 0)
            },
            "rutas_generadas": rutas_procesadas
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rutas/activas")
def obtener_rutas_activas():
    return {"rutas": db_rutas["rutas_activas"]}

@app.get("/api/tienda/{store_id}/status")
def estatus_tienda(store_id: str):
    estado = db_rutas["estado_tiendas"].get(store_id)
    if not estado:
        return {"store_id": store_id, "estado_general": "rojo_sin_asignar"}
    return {"store_id": store_id, "detalles": estado}

@app.post("/api/tienda/recibir")
def confirmar_recepcion(data: RecepcionMercancia):
    estado = db_rutas["estado_tiendas"].get(data.store_id)
    if not estado:
        raise HTTPException(status_code=404, detail="Tienda no tiene entregas pendientes")
    
    if estado["recibido"]:
        return {"status": "warning", "mensaje": "Pedido ya marcado como recibido previamente."}
        
    estado["recibido"] = True
    estado["estado"] = "entregado"
    estado["comentarios_gerente"] = data.comentarios
    estado["hora_recepcion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Lógica para avanzar el camión a la siguiente parada
    for ruta in db_rutas["rutas_activas"]:
        if ruta["id_viaje"] == estado["id_viaje"]:
            ruta["parada_actual_index"] += 1
            # Si el índice actual ya es el último (regreso al CEDIS), cerramos la ruta
            if ruta["parada_actual_index"] >= len(ruta["paradas"]) - 1:
                ruta["estado"] = "completado"
            break
            
    return {"status": "success", "mensaje": "Recepción confirmada. El camión avanza a la siguiente parada."}
