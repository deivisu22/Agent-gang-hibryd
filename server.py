import os
import sys
import json
import time
import subprocess
import shutil
import base64
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv

load_dotenv(override=True)

KEYS_RAW = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
API_KEYS = [k.strip() for k in KEYS_RAW.split(",") if k.strip()]

KEY_INDEX = 0

def obtener_cliente_genai():
    global KEY_INDEX
    if not API_KEYS:
        raise HTTPException(status_code=500, detail="Falta GEMINI_API_KEYS en las variables de Vercel.")
    key_actual = API_KEYS[KEY_INDEX % len(API_KEYS)]
    return genai.Client(api_key=key_actual)

def rotar_api_key():
    global KEY_INDEX
    if API_KEYS:
        KEY_INDEX = (KEY_INDEX + 1) % len(API_KEYS)

MODELO_PRINCIPAL = "gemini-3.6-flash"
MODELO_RESPALDO = "gemini-3.5-flash"
ARCHIVO_MEMORIA = "/tmp/memoria.json"

app = FastAPI(title="Aria Mirror AI Studio Vercel Edition")

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
    try:
        with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(memoria, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

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

def generar_imagen_arte(prompt: str) -> str:
    prompt_encoded = prompt.replace(" ", "%20")
    url_imagen = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true"
    return (
        f"🎨 **Resultado Visual:**\n\n"
        f"![Imagen Generada]({url_imagen})\n\n"
        f"🔗 [Descargar Imagen HD]({url_imagen})"
    )

def consultar_multimodal(prompt: str, imagen_b64: Optional[str] = None) -> str:
    palabras_graficas = ["crea una imagen", "genera una imagen", "haz un dibujo", "dibuja", "renderiza", "diseña un logo"]
    if any(p in prompt.lower() for p in palabras_graficas) and not imagen_b64:
        return generar_imagen_arte(prompt)

    memoria = cargar_memoria()
    conversacion_previa = ""
    for msg in memoria.get("historial_conversacion", [])[-8:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    system_instruction = (
        "Eres Aria AI, un Agente Autónomo Multi-Funcional y Tutor Personal en Vercel Cloud.\n"
        "1. Responde con texto directo, natural y fluido.\n"
        "2. Si la petición es de código, entrega código modular, listo para producción y probado.\n"
        "3. NUNCA agregues resúmenes o conclusiones innecesarias al final.\n\n"
        f"HISTORIAL RECIENTE:\n{conversacion_previa}"
    )

    contents = []
    if imagen_b64 and "," in imagen_b64:
        header, encoded = imagen_b64.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
        data_bytes = base64.b64decode(encoded)
        contents.append(types.Part.from_bytes(data=data_bytes, mime_type=mime_type))

    prompt_final = f"{system_instruction}\n\nPETICIÓN ACTUAL: {prompt if prompt else 'Analiza la imagen.'}"
    contents.append(prompt_final)

    intentos_totales = max(len(API_KEYS) * 2, 2)
    for _ in range(intentos_totales):
        client = obtener_cliente_genai()
        for modelo in [MODELO_PRINCIPAL, MODELO_RESPALDO]:
            try:
                response = client.models.generate_content(model=modelo, contents=contents)
                guardar_mensaje_historial("usuario", prompt)
                guardar_mensaje_historial("agente", response.text)
                return response.text
            except (ServerError, ClientError):
                rotar_api_key()
                time.sleep(0.5)
            except Exception as e:
                rotar_api_key()
                time.sleep(0.5)

    raise HTTPException(status_code=503, detail="API Keys temporalmente saturadas.")

class PeticionChat(BaseModel):
    prompt: str
    imagen: Optional[str] = None

@app.post("/api/chat")
def chat_endpoint(peticion: PeticionChat):
    respuesta = consultar_multimodal(peticion.prompt, peticion.imagen)
    return {"respuesta": respuesta}

@app.get("/api/files/tree")
def tree_endpoint():
    return {"arbol": ["server.py", "index.html", "requirements.txt", "vercel.json"]}

@app.get("/api/system/stats")
def stats_endpoint():
    return {"metricas": {"cpu_uso": "Vercel Serverless", "ram_uso": "Auto-scaled", "disco_libre_gb": "Cloud"}}

@app.get("/api/historial")
def historial_endpoint():
    memoria = cargar_memoria()
    return {"historial": memoria.get("historial_conversacion", [])}

@app.get("/")
def interfaz_web():
    return FileResponse("index.html")
