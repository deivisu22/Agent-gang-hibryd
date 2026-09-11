import os
import json
import time
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

# Variables de entorno para OAuth (se configuran en .env cuando tengas las credenciales)
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

app = FastAPI(title="Agente Programador Multi-Entorno")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# -------------------------------------------------------------
# MEMORIA Y HISTORIAL
# -------------------------------------------------------------

def cargar_memoria() -> dict:
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"reglas_aprendidas": [], "historial_conversacion": [], "cuentas_vinculadas": {}}

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
# CONSULTAS GEMINI CON RAZONAMIENTO AMPLIADO
# -------------------------------------------------------------

def consultar_gemini(prompt: str) -> str:
    memoria = cargar_memoria()
    reglas = "\n".join([f"- {r}" for r in memoria.get("reglas_aprendidas", [])])
    
    conversacion_previa = ""
    for msg in memoria.get("historial_conversacion", [])[-6:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    prompt_final = (
        "Eres un Agente Programador Full-Stack Senior Autónomo Multi-Lenguaje.\n"
        f"REGLAS APRENDIDAS:\n{reglas}\n\n"
        f"HISTORIAL DE CONVERSACIÓN:\n{conversacion_previa}\n\n"
        "RAZONAMIENTO AMPLIADO: Analiza arquitectura, sintaxis y seguridad antes de responder.\n"
        f"PETICIÓN DEL USUARIO:\n{prompt}"
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
# ENDPOINTS REST Y AUTENTICACIÓN
# -------------------------------------------------------------

class PeticionChat(BaseModel):
    prompt: str

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == ADMIN_USER and form_data.password == ADMIN_PASS:
        return {"access_token": "token-sesion-valida", "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")

@app.post("/api/chat")
def chat_endpoint(peticion: PeticionChat, token: str = Depends(oauth2_scheme)):
    respuesta = consultar_gemini(peticion.prompt)
    return {"respuesta": respuesta}

@app.get("/api/historial")
def historial_endpoint(token: str = Depends(oauth2_scheme)):
    memoria = cargar_memoria()
    return {"historial": memoria.get("historial_conversacion", [])}

# -------------------------------------------------------------
# INTEGRACIONES OAUTH: GITHUB Y GOOGLE
# -------------------------------------------------------------

@app.get("/auth/github")
def auth_github():
    if not GITHUB_CLIENT_ID:
        return {"error": "GITHUB_CLIENT_ID no configurado en el archivo .env"}
    url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo,user"
    return RedirectResponse(url)

@app.get("/auth/google")
def auth_google():
    if not GOOGLE_CLIENT_ID:
        return {"error": "GOOGLE_CLIENT_ID no configurado en el archivo .env"}
    url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&response_type=code&scope=openid%20email%20profile"
    return RedirectResponse(url)

# -------------------------------------------------------------
# INTERFAZ WEB RESPONSIVA (FRONTEND CON VINCULACIÓN DE CUENTAS)
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

        <!-- PANTALLA CHAT -->
        <div id="chat-screen" class="hidden flex-1 flex flex-col h-screen max-w-4xl mx-auto w-full p-2">
            <header class="p-4 bg-gray-800 rounded-t-xl flex justify-between items-center border-b border-gray-700">
                <div class="flex items-center gap-3">
                    <h2 class="font-bold text-lg text-purple-400">💬 Agente Autónomo</h2>
                    <span class="text-xs bg-purple-900 text-purple-300 px-2 py-1 rounded">Multi-Lenguaje</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="window.location.href='/auth/github'" class="text-xs bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded border border-gray-600 flex items-center gap-1">
                        🔗 GitHub
                    </button>
                    <button onclick="window.location.href='/auth/google'" class="text-xs bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded border border-gray-600 flex items-center gap-1">
                        🌐 Google
                    </button>
                    <button onclick="logout()" class="text-xs bg-red-600 px-3 py-1 rounded font-bold">Salir</button>
                </div>
            </header>
            
            <div id="messages" class="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-950 font-mono text-sm"></div>
            
            <div class="p-3 bg-gray-800 rounded-b-xl flex gap-2 border-t border-gray-700">
                <input id="user-input" type="text" placeholder="Escribe tu consulta o tarea..." class="flex-1 p-3 bg-gray-700 rounded border border-gray-600 focus:outline-none focus:border-purple-500">
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