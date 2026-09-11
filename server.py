import os
import sys
import json
import time
import subprocess
import tempfile
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv

load_dotenv(override=True)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise ValueError("Falta GEMINI_API_KEY en el archivo .env")

client = genai.Client(api_key=GEMINI_KEY)
MODELO_PRINCIPAL = "gemini-3.6-flash"
MODELO_RESPALDO = "gemini-3.5-flash"
ARCHIVO_MEMORIA = "memoria.json"

ADMIN_USER = "admin"
ADMIN_PASS = "gangsto123"

app = FastAPI(title="Agente Programador Multi-Entorno")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# -------------------------------------------------------------
# MEMORIA PERSISTENTE
# -------------------------------------------------------------

def cargar_memoria() -> dict:
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"reglas_aprendidas": [], "historial_conversacion": []}

def guardar_memoria(memoria: dict):
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, indent=2, ensure_ascii=False)

def guardar_mensaje_historial(rol: str, contenido: str):
    memoria = cargar_memoria()
    if "historial_conversacion" not in memoria:
        memoria["historial_conversacion"] = []
    
    memoria["historial_conversacion"].append({
        "rol": rol,
        "contenido": contenido,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    memoria["historial_conversacion"] = memoria["historial_conversacion"][-20:]
    guardar_memoria(memoria)

# -------------------------------------------------------------
# SANDBOX AISLADA CON SUBPROCESS Y TIMEOUT
# -------------------------------------------------------------

def ejecutar_en_sandbox_subproceso(codigo_python: str, timeout_segundos: int = 5) -> tuple[bool, str]:
    """
    Ejecuta código Python en un subproceso totalmente separado con un archivo temporal.
    Evita bloqueos de memoria y corta bucles infinitos mediante timeout.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp_file:
        tmp_file.write(codigo_python)
        tmp_file_path = tmp_file.name

    try:
        # Ejecuta en un proceso secundario aislado
        resultado = subprocess.run(
            [sys.executable, tmp_file_path],
            capture_output=True,
            text=True,
            timeout=timeout_segundos
        )
        
        os.remove(tmp_file_path)
        
        if resultado.returncode == 0:
            salida = resultado.stdout.strip()
            return True, salida if salida else "✅ Ejecutado exitosamente (Sin salida de texto)."
        else:
            return False, resultado.stderr.strip()

    except subprocess.TimeoutExpired:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        return False, f"⏰ TIMEOUT: La ejecución excedió el límite de {timeout_segundos} segundos (Posible bucle infinito)."
    except Exception as e:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
        return False, f"❌ Error de la Sandbox: {str(e)}"

# -------------------------------------------------------------
# CONSULTAS GEMINI CON RAZONAMIENTO AMPLIADO
# -------------------------------------------------------------

def consultar_gemini(prompt: str) -> str:
    memoria = cargar_memoria()
    reglas = "\n".join([f"- {r}" for r in memoria.get("reglas_aprendidas", [])])
    
    conversacion_previa = ""
    for msg in memoria.get("historial_conversacion", [])[-6:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    prompt_final = (
        "Eres un Agente Programador Full-Stack Senior Autónomo.\n"
        f"REGLAS APRENDIDAS:\n{reglas}\n\n"
        f"HISTORIAL RECIENTE:\n{conversacion_previa}\n\n"
        "RAZONAMIENTO AMPLIADO: Analiza la estructura, sintaxis y casos borde.\n"
        f"PETICIÓN ACTUAL:\n{prompt}"
    )

    for modelo in [MODELO_PRINCIPAL, MODELO_RESPALDO]:
        try:
            response = client.models.generate_content(model=modelo, contents=prompt_final)
            guardar_mensaje_historial("usuario", prompt)
            guardar_mensaje_historial("agente", response.text)
            return response.text
        except (ServerError, ClientError):
            time.sleep(2)

    raise HTTPException(status_code=503, detail="Servidores de IA saturados.")

# -------------------------------------------------------------
# ENDPOINTS REST DE AUTENTICACIÓN Y SANDBOX
# -------------------------------------------------------------

class PeticionChat(BaseModel):
    prompt: str

class PeticionSandbox(BaseModel):
    codigo: str

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == ADMIN_USER and form_data.password == ADMIN_PASS:
        return {"access_token": "token-sesion-valida", "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")

@app.post("/api/chat")
def chat_endpoint(peticion: PeticionChat, token: str = Depends(oauth2_scheme)):
    respuesta = consultar_gemini(peticion.prompt)
    return {"respuesta": respuesta}

@app.post("/api/sandbox")
def sandbox_endpoint(peticion: PeticionSandbox, token: str = Depends(oauth2_scheme)):
    exito, salida = ejecutar_en_sandbox_subproceso(peticion.codigo)
    return {"exito": exito, "salida": salida}

@app.get("/api/historial")
def historial_endpoint(token: str = Depends(oauth2_scheme)):
    memoria = cargar_memoria()
    return {"historial": memoria.get("historial_conversacion", [])}

# -------------------------------------------------------------
# INTERFAZ WEB RESPONSIVA CON CONSOLA DE PRUEBAS EN VIVO
# -------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def interfaz_web():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Agente IA Multi-Entorno</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-white min-h-screen flex flex-col font-sans">
        
        <!-- PANTALLA LOGIN -->
        <div id="login-screen" class="flex-1 flex items-center justify-center p-4">
            <div class="bg-gray-800 p-6 rounded-xl shadow-2xl w-full max-w-sm border border-gray-700">
                <h1 class="text-2xl font-bold mb-4 text-center text-purple-400">🤖 Agente IA</h1>
                <input id="username" type="text" placeholder="Usuario" class="w-full p-3 mb-3 bg-gray-700 rounded border border-gray-600 focus:outline-none focus:border-purple-500">
                <input id="password" type="password" placeholder="Contraseña" class="w-full p-3 mb-4 bg-gray-700 rounded border border-gray-600 focus:outline-none focus:border-purple-500">
                <button onclick="login()" class="w-full bg-purple-600 hover:bg-purple-700 font-bold p-3 rounded transition">Iniciar Sesión</button>
            </div>
        </div>

        <!-- PANTALLA CHAT Y SANDBOX -->
        <div id="chat-screen" class="hidden flex-1 flex flex-col h-screen max-w-5xl mx-auto w-full p-2">
            <header class="p-4 bg-gray-800 rounded-t-xl flex justify-between items-center border-b border-gray-700">
                <div class="flex items-center gap-3">
                    <h2 class="font-bold text-lg text-purple-400">💬 Agente Autónomo</h2>
                    <span class="text-xs bg-green-900 text-green-300 px-2 py-1 rounded">Sandbox Activa (Subprocess)</span>
                </div>
                <button onclick="logout()" class="text-xs bg-red-600 px-3 py-1 rounded font-bold">Salir</button>
            </header>
            
            <div id="messages" class="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-950 font-mono text-sm"></div>
            
            <div class="p-3 bg-gray-800 rounded-b-xl flex gap-2 border-t border-gray-700">
                <input id="user-input" type="text" placeholder="Escribe tu consulta o pide un código para probar en Sandbox..." class="flex-1 p-3 bg-gray-700 rounded border border-gray-600 focus:outline-none focus:border-purple-500">
                <button onclick="enviarMensaje()" class="bg-purple-600 px-6 rounded font-bold hover:bg-purple-700 transition">Enviar</button>
            </div>
        </div>

        <script>
            let token = localStorage.getItem('token');
            if (token) mostrarChat();

            async function login() {
                const formData = new FormData();
                formData.append('username', document.getElementById('username').value);
                formData.append('password', document.getElementById('password').value);

                const res = await fetch('/token', { method: 'POST', body: formData });
                if (res.ok) {
                    const data = await res.json();
                    token = data.access_token;
                    localStorage.setItem('token', token);
                    mostrarChat();
                } else {
                    alert('Credenciales incorrectas');
                }
            }

            function mostrarChat() {
                document.getElementById('login-screen').classList.add('hidden');
                document.getElementById('chat-screen').classList.remove('hidden');
                cargarHistorial();
            }

            function logout() {
                localStorage.removeItem('token');
                location.reload();
            }

            async function cargarHistorial() {
                const res = await fetch('/api/historial', { headers: { 'Authorization': 'Bearer ' + token } });
                if (res.ok) {
                    const data = await res.json();
                    const container = document.getElementById('messages');
                    container.innerHTML = '';
                    data.historial.forEach(m => agregarBubble(m.rol, m.contenido));
                }
            }

            async function enviarMensaje() {
                const input = document.getElementById('user-input');
                const text = input.value.trim();
                if (!text) return;
                
                agregarBubble('usuario', text);
                input.value = '';

                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                    body: JSON.stringify({ prompt: text })
                });

                if (res.ok) {
                    const data = await res.json();
                    agregarBubble('agente', data.respuesta);
                }
            }

            function agregarBubble(rol, texto) {
                const container = document.getElementById('messages');
                const div = document.createElement('div');
                div.className = rol === 'usuario' ? 'text-right' : 'text-left';
                div.innerHTML = `<span class="inline-block p-3 rounded-lg max-w-full text-sm ${rol === 'usuario' ? 'bg-purple-600 text-white' : 'bg-gray-800 text-gray-200 border border-gray-700 whitespace-pre-wrap'}">${texto}</span>`;
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
            }

            document.getElementById('user-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') enviarMensaje();
            });
        </script>
    </body>
    </html>
    """