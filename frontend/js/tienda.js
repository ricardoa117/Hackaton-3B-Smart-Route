// js/tienda.js
class TiendaController {
    constructor() {
        this.storeId = null;
        this.pollInterval = null;
        this.inicializarUI();
    }

    inicializarUI() {
        this.selector = document.getElementById('storeSelector');
        this.semaforoEl = document.getElementById('semaforo');
        this.estadoTexto = document.getElementById('estado-texto');
        this.infoRuta = document.getElementById('info-ruta');
        this.paradaEl = document.getElementById('parada');
        this.restanteEl = document.getElementById('restante');
        this.btn = document.getElementById('pedidoBtn');

        // Llenar el dropdown con las tiendas de utils.js
        Object.entries(window.utils.STORES_DB).forEach(([id, data]) => {
            if(id !== "CEDIS_CDMX_01") {
                const option = document.createElement('option');
                option.value = id;
                option.textContent = `[${id}] - ${data.name}`;
                this.selector.appendChild(option);
            }
        });

        this.selector.addEventListener('change', (e) => this.cambiarTienda(e.target.value));
        this.btn.addEventListener('click', () => this.confirmarRecepcion());
    }

    cambiarTienda(nuevoId) {
        this.storeId = nuevoId;
        if (this.pollInterval) clearInterval(this.pollInterval);
        
        if (!this.storeId) {
            this.resetearUI();
            return;
        }

        // Consultar a tu API cada 3 segundos
        this.sincronizarConBackend();
        this.pollInterval = setInterval(() => this.sincronizarConBackend(), 3000);
    }

    async sincronizarConBackend() {
        try {
            // 1. Obtener el estatus específico de esta tienda
            const resTienda = await fetch(`http://localhost:8000/api/tienda/${this.storeId}/status`);
            const statusTienda = await resTienda.json();

            if (statusTienda.estado_general === "rojo_sin_asignar") {
                this.actualizarUI('bg-secondary', 'Sin pedidos programados hoy', false, null);
                return;
            }

            const detalles = statusTienda.detalles;

            if (detalles.estado === "entregado") {
                this.actualizarUI('bg-success', '¡Mercancía Recibida!', false, null);
                return;
            }

            // 2. Si está en camino, necesitamos saber dónde va el camión
            const resRutas = await fetch(`http://localhost:8000/api/rutas/activas`);
            const rutasData = await resRutas.json();
            
            const miRuta = rutasData.rutas.find(r => r.id_viaje === detalles.id_viaje);
            if (!miRuta) return;

            // La magia matemática: Tu turno menos el paso actual del camión
            const tiendasFaltantes = detalles.turno_en_ruta - miRuta.parada_actual_index;

            if (tiendasFaltantes <= 0) {
                this.actualizarUI('bg-success', '¡El camión ha llegado!', true, 0, detalles.turno_en_ruta);
            } else if (tiendasFaltantes <= 1) {
                this.actualizarUI('bg-warning', '¡Prepárate! Camión cerca', false, tiendasFaltantes, detalles.turno_en_ruta);
            } else {
                this.actualizarUI('bg-danger', 'Camión en ruta', false, tiendasFaltantes, detalles.turno_en_ruta);
            }

        } catch (error) {
            console.error("Error sincronizando:", error);
        }
    }

    actualizarUI(colorClase, texto, botonActivo, faltantes, turno = 0) {
        this.semaforoEl.className = `semaforo ${colorClase}`;
        this.estadoTexto.textContent = texto;
        this.btn.disabled = !botonActivo;

        if (faltantes !== null) {
            this.infoRuta.style.display = 'block';
            this.restanteEl.textContent = faltantes;
            this.paradaEl.textContent = turno;
        } else {
            this.infoRuta.style.display = 'none';
        }
    }

    async confirmarRecepcion() {
        this.btn.disabled = true;
        this.btn.textContent = "Procesando...";
        
        try {
            await fetch('http://localhost:8000/api/tienda/recibir', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ store_id: this.storeId, comentarios: "Recibido vía MVP" })
            });
            
            // Forzar actualización inmediata
            this.sincronizarConBackend();
            this.btn.textContent = "✓ Confirmar Recepción";
        } catch (error) {
            alert("Error al conectar con la base central.");
            this.btn.disabled = false;
        }
    }

    resetearUI() {
        this.actualizarUI('bg-secondary', 'Esperando selección...', false, null);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.tiendaApp = new TiendaController();
});
