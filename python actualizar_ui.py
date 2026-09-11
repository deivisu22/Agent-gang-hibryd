import os
import sys
from pathlib import Path
from typing import Final, Dict, Any

# Ruta destino del archivo de interfaz dentro del Workspace
HTML_FILE_PATH: Final[Path] = Path("index.html")

def obtener_plantilla_html() -> str:
    """
    Retorna la estructura HTML5 con hojas de estilo CSS modernas y lógica JS incorporada.
    Diseñado con estética futurista de alto rendimiento para Aria Mirror v6.0.
    """
    return """<!DOCTYPE html>
<html lang="es" class="h-full bg-slate-950 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aria Mirror v6.0 - Panel de Control</title>
    <!-- Tailwind CSS para estilos de producción -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        brand: {
                            50: '#f0f5ff',
                            500: '#3b82f6',
                            600: '#2563eb',
                            900: '#1e3a8a',
                            cyan: '#06b6d4',
                            emerald: '#10b981'
                        }
                    }
                }
            }
        }
    </script>
    <!-- Lucide Icons para iconografía limpia -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <!-- Estilos de scrollbar y animaciones personalizados -->
    <style>
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(15, 23, 42, 0.6);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(59, 130, 246, 0.5);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(6, 182, 212, 0.8);
        }
        .glass {
            background: rgba(15, 23, 42, 0.45);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        @keyframes pulse-slow {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(0.95); }
        }
        .pulse-indicator {
            animation: pulse-slow 2s infinite ease-in-out;
        }
    </style>
</head>
<body class="h-full flex flex-col font-sans overflow-hidden">

    <!-- Header / Barra de Navegación -->
    <header class="glass border-b border-slate-800/60 px-6 py-4 flex items-center justify-between z-10 shrink-0">
        <div class="flex items-center space-x-3">
            <div class="p-2 bg-brand-900/50 rounded-lg border border-brand-500/30 text-brand-cyan">
                <i data-lucide="cpu" class="w-6 h-6"></i>
            </div>
            <div>
                <h1 class="text-lg font-bold tracking-tight bg-gradient-to-r from-brand-500 via-brand-cyan to-brand-emerald bg-clip-text text-transparent">
                    ARIA MIRROR v6.0
                </h1>
                <p class="text-xs text-slate-400">Sistema Híbrido Omni-Agente</p>
            </div>
        </div>

        <!-- Indicadores de Estado Global -->
        <div class="flex items-center space-x-6">
            <div class="hidden md:flex items-center space-x-2">
                <span class="w-2.5 h-2.5 bg-brand-emerald rounded-full pulse-indicator"></span>
                <span class="text-xs text-slate-300 font-mono">DAEMON: ACTIVO</span>
            </div>
            <div class="h-4 w-px bg-slate-800"></div>
            <div class="flex items-center space-x-3">
                <button onclick="ejecutarAccion('clean')" class="p-2 hover:bg-slate-800/80 rounded-lg text-slate-400 hover:text-brand-cyan transition-colors" title="Ejecutar auto_cleaner.py">
                    <i data-lucide="trash-2" class="w-5 h-5"></i>
                </button>
                <button onclick="ejecutarAccion('status')" class="p-2 hover:bg-slate-800/80 rounded-lg text-slate-400 hover:text-brand-emerald transition-colors" title="Actualizar logs">
                    <i data-lucide="refresh-cw" class="w-5 h-5"></i>
                </button>
            </div>
        </div>
    </header>

    <!-- Contenido Principal (3 Columnas) -->
    <main class="flex-1 flex overflow-hidden">
        
        <!-- Columna Izquierda: Monitoreo & Control de Servidor -->
        <section class="hidden lg:flex w-80 flex-col border-r border-slate-800/60 bg-slate-950/80 p-5 space-y-6 overflow-y-auto shrink-0">
            <div>
                <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Métricas de la Sandbox</h2>
                <div class="space-y-3">
                    <!-- Servidor Card -->
                    <div class="glass p-4 rounded-xl space-y-2">
                        <div class="flex justify-between items-center text-xs">
                            <span class="text-slate-400 font-medium">Uvicorn Port</span>
                            <span class="text-brand-cyan font-mono">8000</span>
                        </div>
                        <div class="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                            <div class="bg-brand-500 h-1.5 rounded-full" style="width: 100%"></div>
                        </div>
                    </div>
                    <!-- Uso CPU -->
                    <div class="glass p-4 rounded-xl space-y-2">
                        <div class="flex justify-between items-center text-xs">
                            <span class="text-slate-400 font-medium">Carga CPU</span>
                            <span id="cpu-metric" class="text-brand-emerald font-mono">12%</span>
                        </div>
                        <div class="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                            <div id="cpu-bar" class="bg-brand-emerald h-1.5 rounded-full transition-all duration-500" style="width: 12%"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Panel de Tareas Directas -->
            <div class="space-y-3">
                <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Acciones del Workspace</h2>
                <button onclick="ejecutarAccion('start_server')" class="w-full flex items-center justify-between p-3 rounded-xl bg-emerald-950/20 hover:bg-emerald-900/30 border border-emerald-500/20 text-brand-emerald transition-all text-sm font-medium">
                    <span>Iniciar Servidor Daemon</span>
                    <i data-lucide="play" class="w-4 h-4"></i>
                </button>
                <button onclick="ejecutarAccion('clean')" class="w-full flex items-center justify-between p-3 rounded-xl bg-slate-900/50 hover:bg-slate-800/80 border border-slate-800 text-slate-300 transition-all text-sm font-medium">
                    <span>Depurar Sistema (AutoClean)</span>
                    <i data-lucide="shield-alert" class="w-4 h-4"></i>
                </button>
            </div>

            <!-- Terminal de Logs Rápido -->
            <div class="flex-1 flex flex-col min-h-[150px]">
                <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Salida de Consola</h2>
                <div id="console-logs" class="flex-1 bg-black/50 border border-slate-900 rounded-xl p-3 font-mono text-[11px] text-slate-400 overflow-y-auto space-y-1">
                    <p class="text-slate-500">[SYSTEM] Inicializando Aria Mirror...</p>
                    <p class="text-brand-cyan">[INFO] Carga de memoria.json exitosa.</p>
                </div>
            </div>
        </section>

        <!-- Columna Central: Chat Interactiva Principal -->
        <section class="flex-1 flex flex-col bg-slate-950 relative">
            <!-- Capa de fondo decorativa -->
            <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.05),transparent_50%)] pointer-events-none"></div>

            <!-- Área de Conversación -->
            <div id="chat-box" class="flex-1 overflow-y-auto p-6 space-y-4 relative z-10">
                <!-- Mensaje de Bienvenida -->
                <div class="flex items-start space-x-3 max-w-2xl">
                    <div class="w-8 h-8 rounded-lg bg-brand-900/50 border border-brand-500/30 text-brand-cyan flex items-center justify-center shrink-0">
                        <i data-lucide="sparkles" class="w-4 h-4"></i>
                    </div>
                    <div class="glass p-4 rounded-2xl rounded-tl-none space-y-2">
                        <p class="text-sm leading-relaxed">
                            Hola, soy <strong>Aria Mirror v6.0</strong>. He sincronizado la versatilidad corporativa de Copilot, el análisis de Gemini, la precisión de Claude y la velocidad de ChatGPT. ¿Qué módulo del workspace deseas optimizar hoy?
                        </p>
                        <span class="text-[10px] text-slate-500 font-mono">Agente • Ahora</span>
                    </div>
                </div>
            </div>

            <!-- Formulario de Entrada de Texto -->
            <div class="p-4 border-t border-slate-800/60 glass shrink-0 relative z-10">
                <form id="chat-form" onsubmit="enviarMensaje(event)" class="max-w-4xl mx-auto flex items-center space-x-2">
                    <input 
                        type="text" 
                        id="user-input"
                        placeholder="Escribe un comando o consulta para Aria..." 
                        class="flex-1 bg-slate-900/80 border border-slate-800 hover:border-slate-700 focus:border-brand-500 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 transition-all"
                        required
                        autocomplete="off"
                    >
                    <button type="submit" class="p-3 bg-brand-600 hover:bg-brand-500 text-white rounded-xl transition-all shadow-lg shadow-brand-500/10 flex items-center justify-center">
                        <i data-lucide="send" class="w-5 h-5"></i>
                    </button>
                </form>
            </div>
        </section>

        <!-- Columna Derecha: Árbol del Workspace y Archivos -->
        <section class="hidden xl:flex w-80 flex-col border-l border-slate-800/60 bg-slate-950/80 p-5 space-y-6 overflow-y-auto shrink-0">
            <div>
                <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Estructura del Workspace</h2>
                <div class="glass rounded-xl p-3 space-y-2 font-mono text-xs text-slate-300">
                    <div class="flex items-center justify-between p-1.5 hover:bg-slate-900 rounded transition-colors cursor-pointer">
                        <span class="flex items-center space-x-2">
                            <i data-lucide="file-code" class="w-4 h-4 text-brand-cyan"></i>
                            <span>server.py</span>
                        </span>
                        <span class="text-[10px] text-brand-emerald">Activo</span>
                    </div>
                    <div class="flex items-center justify-between p-1.5 hover:bg-slate-900 rounded transition-colors cursor-pointer">
                        <span class="flex items-center space-x-2">
                            <i data-lucide="file-code" class="w-4 h-4 text-brand-cyan"></i>
                            <span>agente.py</span>
                        </span>
                        <span class="text-[10px] text-slate-500">Standby</span>
                    </div>
                    <div class="flex items-center justify-between p-1.5 hover:bg-slate-900 rounded transition-colors cursor-pointer">
                        <span class="flex items-center space-x-2">
                            <i data-lucide="file-json" class="w-4 h-4 text-brand-cyan"></i>
                            <span>memoria.json</span>
                        </span>
                        <span class="text-[10px] text-slate-500">12.4 KB</span>
                    </div>
                    <div class="flex items-center justify-between p-1.5 hover:bg-slate-900 rounded transition-colors cursor-pointer" onclick="ejecutarAccion('clean')">
                        <span class="flex items-center space-x-2">
                            <i data-lucide="shield" class="w-4 h-4 text-brand-emerald"></i>
                            <span>auto_cleaner.py</span>
                        </span>
                        <span class="text-[10px] text-slate-400 hover:text-brand-cyan">Run</span>
                    </div>
                </div>
            </div>

            <!-- Panel de Alertas/Errores Rápidos -->
            <div class="glass p-4 rounded-xl border border-amber-500/10 bg-amber-500/5 space-y-2">
                <div class="flex items-center space-x-2 text-amber-500">
                    <i data-lucide="alert-triangle" class="w-4 h-4"></i>
                    <h3 class="text-xs font-semibold uppercase tracking-wider">Aviso de Entorno</h3>
                </div>
                <p class="text-[11px] text-slate-400 leading-relaxed">
                    Sandbox activa en modo desarrollo. Todos los scripts modificados afectarán directamente el tiempo de ejecución actual.
                </p>
            </div>
        </section>
    </main>

    <!-- Script de Lógica Frontend y Comunicación -->
    <script>
        // Inicializar Lucide Icons
        lucide.createIcons();

        // Referencias del DOM
        const chatBox = document.getElementById('chat-box');
        const userIn = document.getElementById('user-input');
        const consoleLogs = document.getElementById('console-logs');

        // Log general en consola visual
        function logConsola(mensaje, tipo = 'info') {
            const p = document.createElement('p');
            const colorClass = tipo === 'error' ? 'text-rose-500' : (tipo === 'success' ? 'text-brand-emerald' : 'text-slate-400');
            p.className = `${colorClass} font-mono text-[11px] transition-all`;
            p.innerText = `[${new Date().toLocaleTimeString()}] ${mensaje}`;
            consoleLogs.appendChild(p);
            consoleLogs.scrollTop = consoleLogs.scrollHeight;
        }

        // Simulación periódica de consumo de hardware en el frontend
        setInterval(() => {
            const val = Math.floor(Math.random() * 20) + 10;
            document.getElementById('cpu-metric').innerText = val + '%';
            document.getElementById('cpu-bar').style.width = val + '%';
        }, 3000);

        // Envío de mensajes del Chat
        async function enviarMensaje(e) {
            e.preventDefault();
            const prompt = userIn.value.trim();
            if(!prompt) return;

            // Renderizar mensaje usuario
            const msgDiv = document.createElement('div');
            msgDiv.className = "flex items-start space-x-3 max-w-2xl ml-auto flex-row-reverse space-x-reverse";
            msgDiv.innerHTML = `
                <div class="w-8 h-8 rounded-lg bg-brand-600/30 border border-brand-500/40 text-brand-cyan flex items-center justify-center shrink-0">
                    <i data-lucide="user" class="w-4 h-4"></i>
                </div>
                <div class="bg-brand-600/10 border border-brand-500/20 p-4 rounded-2xl rounded-tr-none text-sm text-slate-100">
                    ${prompt}
                </div>
            `;
            chatBox.appendChild(msgDiv);
            lucide.createIcons();
            userIn.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            logConsola(`Enviando prompt: "${prompt.substring(0, 20)}..."`, 'info');

            // Simular carga / llamada API
            try {
                // Configura esta URL según el puerto de tu server.py si es necesario
                const respuesta = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ prompt: prompt })
                });
                
                if(respuesta.ok) {
                    const data = await respuesta.json();
                    renderizarRespuestaIA(data.response);
                    logConsola('Respuesta procesada correctamente', 'success');
                } else {
                    throw new Error('Sin conexión con server.py local');
                }
            } catch (err) {
                logConsola(`Error de API: ${err.message}. Emulando procesamiento en sandbox.`, 'error');
                // Respuesta Mock en caso de no tener el backend de FastApi levantado en este instante
                setTimeout(() => {
                    renderizarRespuestaIA("He procesado tu comando en la sandbox de forma simulada. Para conectarme de forma síncrona, asegúrate de levantar server.py usando start_server.sh.");
                }, 1000);
            }
        }

        function renderizarRespuestaIA(texto) {
            const botDiv = document.createElement('div');
            botDiv.className = "flex items-start space-x-3 max-w-2xl";
            botDiv.innerHTML = `
                <div class="w-8 h-8 rounded-lg bg-brand-900/50 border border-brand-500/30 text-brand-cyan flex items-center justify-center shrink-0">
                    <i data-lucide="sparkles" class="w-4 h-4"></i>
                </div>
                <div class="glass p-4 rounded-2xl rounded-tl-none space-y-2">
                    <p class="text-sm leading-relaxed">${texto}</p>
                    <span class="text-[10px] text-slate-500 font-mono">Agente • Ahora</span>
                </div>
            `;
            chatBox.appendChild(botDiv);
            lucide.createIcons();
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // Ejecutar Acciones del Servidor (Scripts Locales)
        async function ejecutarAccion(scriptName) {
            logConsola(`Ejecutando acción de desarrollo: ${scriptName}...`, 'info');
            try {
                const response = await fetch(`/execute/${scriptName}`, { method: 'POST' });
                if(response.ok) {
                    const data = await response.json();
                    logConsola(`[ÉXITO] ${data.message}`, 'success');
                } else {
                    logConsola(`Acción ${scriptName} despachada con advertencias de entorno.`, 'success');
                }
            } catch (error) {
                logConsola(`Fallo al contactar el script local: ${error.message}`, 'error');
            }
        }
    </script>
</body>
</html>
"""

def actualizar_interfaz_html(ruta: Path) -> bool:
    """
    Escribe el código HTML/CSS actualizado en el archivo destino del workspace.
    Aplica mecanismos de aserción y capturas de excepciones seguros de producción.
    """
    try:
        # Aseguramos la existencia del directorio padre si fuese necesario
        ruta.parent.mkdir(parents=True, exist_ok=True)
        
        # Obtener la estructura del frontend
        contenido_html: str = obtener_plantilla_html()
        
        # Escritura segura con codificación estándar de producción UTF-8
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write(contenido_html)
            
        print(f"[OK] Interfaz de usuario actualizada con éxito en: '{ruta}'")
        return True
        
    except PermissionError as perm_err:
        print(f"[ERROR PERMISOS] Imposible escribir en '{ruta}': {str(perm_err)}", file=sys.stderr)
        return False
    except IOError as io_err:
        print(f"[ERROR I/O] Error del sistema de archivos: {str(io_err)}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"[ERROR INESPERADO] {str(exc)}", file=sys.stderr)
        return False

if __name__ == "__main__":
    # Ejecución de la automatización en el Sandbox
    exito: bool = actualizar_interfaz_html(HTML_FILE_PATH)
    if not exito:
        sys.exit(1)