import os
import json
import time
import base64
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(override=True)

app = FastAPI(title="Aria Mirror AI Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KEY_INDEX = 0

def obtener_keys() -> list[str]:
    raw = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    return [k.strip() for k in raw.split(",") if k.strip()]

def configurar_gemini() -> str:
    global KEY_INDEX
    keys = obtener_keys()
    if not keys:
        raise HTTPException(
            status_code=500, 
            detail="Falta la variable GEMINI_API_KEYS en Vercel."
        )
    key_actual = keys[KEY_INDEX % len(keys)]
    genai.configure(api_key=key_actual)
    return key_actual

def rotar_api_key():
    global KEY_INDEX
    keys = obtener_keys()
    if keys:
        KEY_INDEX = (KEY_INDEX + 1) % len(keys)

ARCHIVO_MEMORIA = "/tmp/memoria.json"

def cargar_memoria() -> dict:
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"historial_conversacion": []}

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

    keys = obtener_keys()
    if not keys:
        raise HTTPException(
            status_code=500, 
            detail="Error: GEMINI_API_KEYS no configurada en Vercel."
        )

    memoria = cargar_memoria()
    conversacion_previa = ""
    for msg in memoria.get("historial_conversacion", [])[-8:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    system_instruction = (
        "Eres Aria AI, mi asistente personal, desarrollador full stack y tutor personal.\n"
        "Responde de forma técnica, dinámica y directa.\n"
        f"HISTORIAL RECIENTE:\n{conversacion_previa}"
    )

    contents = []
    if imagen_b64 and "," in imagen_b64:
        header, encoded = imagen_b64.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
        data_bytes = base64.b64decode(encoded)
        contents.append({"mime_type": mime_type, "data": data_bytes})

    prompt_final = f"{system_instruction}\n\nPETICIÓN ACTUAL: {prompt if prompt else 'Analiza la imagen.'}"
    contents.append(prompt_final)

    errores_acumulados = []

    for k_idx in range(len(keys)):
        configurar_gemini()
        # Nombres exactos aceptados por la REST API v1beta de google-generativeai
        for mod in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]:
            try:
                model = genai.GenerativeModel(mod)
                response = model.generate_content(contents)
                if response and hasattr(response, 'text') and response.text:
                    guardar_mensaje_historial("usuario", prompt)
                    guardar_mensaje_historial("agente", response.text)
                    return response.text
            except Exception as e:
                err_msg = f"KeyIdx {k_idx} | Mod {mod} -> {str(e)}"
                errores_acumulados.append(err_msg)
                rotar_api_key()

    detalle_final = " || ".join(errores_acumulados)
    raise HTTPException(status_code=500, detail=f"FALLO DE CONEXION A GEMINI. Detalles: {detalle_final}")

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
