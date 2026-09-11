import os
import sys
import json
import time
import subprocess
import shutil
import psutil
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv(override=True)

# -------------------------------------------------------------
# 1. POOL Y ROTACIÓN AUTOMÁTICA DE API KEYS (ZERO LIMITS / CLAUDE FIX)
# -------------------------------------------------------------
KEYS_RAW = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
API_KEYS = [k.strip() for k in KEYS_RAW.split(",") if k.strip()]

if not API_KEYS:
    raise ValueError("Falta GEMINI_API_KEYS o GEMINI_API_KEY en .env")

KEY_INDEX = 0

def obtener_cliente_genai():
    global KEY_INDEX
    key_actual = API_KEYS[KEY_INDEX % len(API_KEYS)]
    return genai.Client(api_key=key_actual)

def rotar_api_key():
    global KEY_INDEX
    KEY_INDEX = (KEY_INDEX + 1) % len(API_KEYS)

MODELO_PRINCIPAL = "gemini-3.6-flash"
MODELO_RESPALDO = "gemini-3.5-flash"
ARCHIVO_MEMORIA = "memoria.json"

app = FastAPI(title="Aria Mirror AI Studio v6.0 Ultra-Omni")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# SCHEDULER DE MANTENIMIENTO BACKGROUND
# -------------------------------------------------------------
def tarea_mantenimiento_background():
    try:
        if os.path.exists("auto_cleaner.py"):
            subprocess.run(["python", "auto_cleaner.py"], capture_output=True, text=True)
    except Exception as e:
        print(f"❌ Error Scheduler: {str(e)}")

scheduler = BackgroundScheduler()
scheduler.add_job(tarea_mantenimiento_background, 'interval', hours=6)
scheduler.start()

# -------------------------------------------------------------
# MEMORIA PERSISTENTE Y LOGS
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
    memoria["historial_conversacion"] = memoria["historial_conversacion"][-40:]
    guardar_memoria(memoria)

def ejecutar_comando_shell(comando: str, timeout_segundos: int = 25) -> tuple[bool, str]:
    comandos_prohibidos = ["rm -rf /", "mkfs", "shutdown", "reboot"]
    if any(p in comando for p in comandos_prohibidos):
        return False, "❌ Comando denegado por políticas de seguridad."

    try:
        resultado = subprocess.run(
            comando,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_segundos,
            cwd=os.getcwd()
        )
        salida = (resultado.stdout + "\n" + resultado.stderr).strip()
        return (resultado.returncode == 0), salida if salida else "✅ Comando ejecutado sin salida."
    except subprocess.TimeoutExpired:
        return False, f"⏰ TIMEOUT: Excedió los {timeout_segundos} segundos."
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def obtener_arbol_proyecto(ruta_base: str = ".") -> list:
    archivos_ignorar = {".git", "__pycache__", "venv", ".venv", "node_modules", ".pytest_cache"}
    arbol = []
    for raiz, dirs, archivos in os.walk(ruta_base):
        dirs[:] = [d for d in dirs if d not in archivos_ignorar]
        for archivo in archivos:
            ruta_relativa = os.path.relpath(os.path.join(raiz, archivo), ruta_base)
            arbol.append(ruta_relativa)
    return arbol[:100]

def obtener_metricas_sistema() -> dict:
    disco = shutil.disk_usage(".")
    return {
        "cpu_uso": f"{psutil.cpu_percent()}%",
        "ram_uso": f"{psutil.virtual_memory().percent}%",
        "disco_libre_gb": f"{disco.free / (1024**3):.2f} GB",
        "total_keys_pool": len(API_KEYS)
    }

def generar_imagen_artística(prompt: str) -> str:
    prompt_encoded = prompt.replace(" ", "%20")
    url_imagen = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true"
    return (
        f"🎨 **Generador Multimodal (ChatGPT DALL·E Equivalent):**\n\n"
        f"![Imagen Generada]({url_imagen})\n\n"
        f"🔗 [Descargar Imagen HD]({url_imagen})"
    )

# -------------------------------------------------------------
# CORE PROMPT: FUSIÓN SUPREMA DE IAs
# -------------------------------------------------------------
def consultar_gemini(prompt: str, modo: str = "general") -> str:
    if modo == "imagen":
        return generar_imagen_artística(prompt)

    memoria = cargar_memoria()
    reglas = "\n".join([f"- {r}" for r in memoria.get("reglas_aprendidas", [])])
    arbol = "\n".join(obtener_arbol_proyecto())
    
    conversacion_previa = ""
    for msg in memoria.get("historial_conversacion", [])[-10:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    system_prompt = (
        "SISTEMA HÍBRIDO OMNI-AGENTE (Aria Mirror v6.0):\n"
        "Has sido reprogramado combinando lo mejor de las 4 IAs líderes:\n"
        "1. VERSATILIDAD (ChatGPT): Responde cualquier consulta con naturalidad, tono directo y adaptabilidad.\n"
        "2. PRECISIÓN EN CÓDIGO (Claude): Genera código estructurado, libre de errores y metodológico.\n"
        "3. VELOCIDAD Y ECOSYSTEM (Gemini): Integra visión técnica amplia e información estructurada.\n"
        "4. PRODUCTIVIDAD CORPORATIVA (Copilot): Enfócate en solución de problemas de office, scripts y automatización.\n\n"
        "REGLAS ANTI-DESVENTAJAS:\n"
        "- Cero alucinaciones: Si un dato requiere prueba de ejecución, sugiere usar la Shell del sistema.\n"
        "- En modo 'general': Responde SOLO con texto fluido y explicaciones, NADA de bloques de código.\n"
        "- En modo 'dev': Entrega código probado, modular, listo para producción y paso a paso.\n\n"
        f"MODO ACTUAL: {modo.upper()}\n\n"
        f"ESTRUCTURA DEL WORKSPACE:\n{arbol}\n\n"
        f"REGLAS APRENDIDAS:\n{reglas}\n\n"
        f"HISTORIAL RECIENTE:\n{conversacion_previa}\n\n"
        f"PETICIÓN ACTUAL DEL MASTER:\n{prompt}"
    )

    intentos_totales = len(API_KEYS) * 2
    for _ in range(intentos_totales):
        client = obtener_cliente_genai()
        for modelo in [MODELO_PRINCIPAL, MODELO_RESPALDO]:
            try:
                response = client.models.generate_content(model=modelo, contents=system_prompt)
                guardar_mensaje_historial("usuario", prompt)
                guardar_mensaje_historial("agente", response.text)
                return response.text
            except (ServerError, ClientError):
                rotar_api_key()
                time.sleep(0.5)
            except Exception:
                rotar_api_key()
                time.sleep(0.5)

    raise HTTPException(status_code=503, detail="API Keys ocupadas. Intenta de nuevo.")

# -------------------------------------------------------------
# REST API ENDPOINTS
# -------------------------------------------------------------
class PeticionChat(BaseModel):
    prompt: str
    modo: Optional[str] = "general"

class PeticionShell(BaseModel):
    comando: str

@app.post("/api/chat")
def chat_endpoint(peticion: PeticionChat):
    respuesta = consultar_gemini(peticion.prompt, peticion.modo)
    return {"respuesta": respuesta}

@app.post("/api/shell")
def shell_endpoint(peticion: PeticionShell):
    exito, salida = ejecutar_comando_shell(peticion.comando)
    return {"exito": exito, "salida": salida}

@app.get("/api/files/tree")
def tree_endpoint():
    return {"arbol": obtener_arbol_proyecto()}

@app.get("/api/system/stats")
def stats_endpoint():
    return {"metricas": obtener_metricas_sistema()}

@app.get("/api/historial")
def historial_endpoint():
    memoria = cargar_memoria()
    return {"historial": memoria.get("historial_conversacion", [])}

@app.get("/")
def interfaz_web():
    return FileResponse("index.html")
