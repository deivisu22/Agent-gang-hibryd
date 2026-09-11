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

load_dotenv(override=True)

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

app = FastAPI(title="Agente Programador Multi-Entorno")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    memoria["historial_conversacion"] = memoria["historial_conversacion"][-30:]
    guardar_memoria(memoria)

def ejecutar_comando_shell(comando: str, timeout_segundos: int = 20) -> tuple[bool, str]:
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

def consultar_gemini(prompt: str, modo: str = "general") -> str:
    memoria = cargar_memoria()
    reglas = "\n".join([f"- {r}" for r in memoria.get("reglas_aprendidas", [])])
    arbol = "\n".join(obtener_arbol_proyecto())
    
    conversacion_previa = ""
    for msg in memoria.get("historial_conversacion", [])[-8:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    if modo == "general":
        instrucción_modo = (
            "MODO SELECCIONADO: CONSULTA GENERAL.\n"
            "REGLA ESTRICTA DE MODO: Responde ÚNICAMENTE con texto explicativo, explicaciones claras y formato narrativo o listas. "
            "Queda ESTRICTAMENTE PROHIBIDO incluir bloques de código (Python, Bash, JS, etc.) o guiones de automatización en la respuesta."
        )
    elif modo == "dev":
        instrucción_modo = (
            "MODO SELECCIONADO: DESARROLLO Y PROGRAMACIÓN.\n"
            "Proveé explicaciones técnicas, código completo probado, manejo de errores y paso a paso didáctico."
        )
    elif modo == "imagen":
        instrucción_modo = (
            "MODO SELECCIONADO: GENERACIÓN Y EDICIÓN DE IMÁGENES.\n"
            "Actúa como experto en Arte Digital y Prompts. Proporciona prompts ultra-detallados en inglés y español para Imagen 3/Midjourney, "
            "así como parámetros de edición, composición, iluminación y estilo visual."
        )
    else:
        instrucción_modo = "Responder de forma general."

    system_prompt = (
        "Eres un Agente Autónomo Multi-Funcional, Desarrollador Full-Stack y Tutor Personal.\n"
        f"{instrucción_modo}\n\n"
        f"ESTRUCTURA DEL PROYECTO ACTUAL:\n{arbol}\n\n"
        f"REGLAS APRENDIDAS:\n{reglas}\n\n"
        f"HISTORIAL RECIENTE:\n{conversacion_previa}\n\n"
        f"PETICIÓN ACTUAL:\n{prompt}"
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
