import os
import json
import time
import base64
import requests
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(override=True)

app = FastAPI(title="Aria Studio - Multi-Function Core")

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

def obtener_key_actual() -> str:
    global KEY_INDEX
    keys = obtener_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="Falta la variable GEMINI_API_KEYS en Vercel.")
    return keys[KEY_INDEX % len(keys)]

def rotar_api_key():
    global KEY_INDEX
    keys = obtener_keys()
    if keys:
        KEY_INDEX = (KEY_INDEX + 1) % len(keys)

# PERSISTENCIA HÍBRIDA (UPSTASH REDIS REST + FALLBACK LOCAL)
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
ARCHIVO_MEMORIA = "/tmp/aria_chats.json"

def guardar_en_redis(key: str, val: dict) -> bool:
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return False
    try:
        url = f"{UPSTASH_URL}/set/{key}"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        res = requests.post(url, json=json.dumps(val), headers=headers, timeout=5)
        return res.status_code == 200
    except Exception:
        return False

def obtener_de_redis(key: str) -> Optional[dict]:
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        url = f"{UPSTASH_URL}/get/{key}"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("result"):
                return json.loads(data["result"])
    except Exception:
        pass
    return None

def cargar_todas_sesiones() -> dict:
    redis_data = obtener_de_redis("aria_todas_sesiones")
    if redis_data is not None:
        return redis_data
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def guardar_todas_sesiones(data: dict):
    guardar_en_redis("aria_todas_sesiones", data)
    try:
        with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def obtener_historial_chat(chat_id: str) -> list:
    sesiones = cargar_todas_sesiones()
    return sesiones.get(chat_id, {}).get("mensajes", [])

def guardar_mensaje_en_chat(chat_id: str, rol: str, contenido: str, titulo: str = "Nueva conversación"):
    sesiones = cargar_todas_sesiones()
    if chat_id not in sesiones:
        sesiones[chat_id] = {
            "titulo": titulo if titulo else "Conversación " + time.strftime("%H:%M"),
            "creado": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mensajes": []
        }
    
    if len(sesiones[chat_id]["mensajes"]) == 0 and rol == "usuario":
        sesiones[chat_id]["titulo"] = (contenido[:30] + "...") if len(contenido) > 30 else contenido

    sesiones[chat_id]["mensajes"].append({
        "rol": rol,
        "contenido": contenido,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    sesiones[chat_id]["mensajes"] = sesiones[chat_id]["mensajes"][-30:]
    guardar_todas_sesiones(sesiones)

def generar_imagen_arte(prompt: str) -> str:
    prompt_encoded = prompt.replace(" ", "%20")
    url_imagen = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true"
    return (
        f"🎨 **Generación Visual Solicitada:**\n\n"
        f"![Imagen Generada]({url_imagen})\n\n"
        f"🔗 [Descargar Render HD]({url_imagen})"
    )

class ArchivoAdjunto(BaseModel):
    nombre: str
    mime_type: str
    contenido_b64: str

class PeticionChat(BaseModel):
    chat_id: str
    prompt: str
    archivos: Optional[List[ArchivoAdjunto]] = None

@app.post("/api/chat")
def chat_endpoint(peticion: PeticionChat):
    palabras_graficas = ["crea una imagen", "genera una imagen", "haz un dibujo", "dibuja", "renderiza", "diseña un logo"]
    if any(p in peticion.prompt.lower() for p in palabras_graficas) and not peticion.archivos:
        resp_visual = generar_imagen_arte(peticion.prompt)
        guardar_mensaje_en_chat(peticion.chat_id, "usuario", peticion.prompt)
        guardar_mensaje_en_chat(peticion.chat_id, "agente", resp_visual)
        return {"respuesta": resp_visual}

    keys = obtener_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEYS no configurada.")

    historial = obtener_historial_chat(peticion.chat_id)
    conversacion_previa = ""
    for msg in historial[-10:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    system_instruction = (
        "Eres Aria AI, mi asistente personal, desarrollador full stack y tutor de desarrollo.\n"
        "Responde de forma técnica, dinámica, directa y formateada en Markdown impecable.\n"
        f"CONTEXTO DE ESTE CHAT:\n{conversacion_previa}"
    )

    parts = []
    
    if peticion.archivos:
        for arch in peticion.archivos:
            if "text" in arch.mime_type or "json" in arch.mime_type or "py" in arch.nombre or "csv" in arch.nombre:
                try:
                    decoded_text = base64.b64decode(arch.contenido_b64.split(",")[-1]).decode("utf-8", errors="ignore")
                    parts.append({"text": f"--- ARCHIVO ADJUNTO: {arch.nombre} ---\n{decoded_text}\n--- FIN ARCHIVO ---"})
                except Exception:
                    pass
            else:
                encoded = arch.contenido_b64.split(",")[-1]
                parts.append({
                    "inline_data": {
                        "mime_type": arch.mime_type,
                        "data": encoded
                    }
                })

    prompt_final = f"{system_instruction}\n\nPETICIÓN ACTUAL: {peticion.prompt if peticion.prompt else 'Analiza los archivos adjuntos.'}"
    parts.append({"text": prompt_final})

    payload = {"contents": [{"parts": parts}]}
    modelos_confirmados = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3.5-flash"]
    errores_acumulados = []

    for k_idx in range(len(keys)):
        api_key = obtener_key_actual()
        for mod in modelos_confirmados:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            try:
                res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=12)
                data = res.json()
                
                if res.status_code == 200 and "candidates" in data:
                    texto_resp = data["candidates"][0]["content"]["parts"][0]["text"]
                    guardar_mensaje_en_chat(peticion.chat_id, "usuario", peticion.prompt)
                    guardar_mensaje_en_chat(peticion.chat_id, "agente", texto_resp)
                    return {"respuesta": texto_resp}
                else:
                    err_txt = data.get("error", {}).get("message", res.text[:120])
                    errores_acumulados.append(f"Mod {mod} -> {res.status_code}: {err_txt}")
            except Exception as e:
                errores_acumulados.append(f"Mod {mod} -> Ex: {str(e)}")
            
            rotar_api_key()

    raise HTTPException(status_code=500, detail=f"FALLO CORE ARIA: {' || '.join(errores_acumulados)}")

@app.get("/api/chats")
def listar_chats():
    sesiones = cargar_todas_sesiones()
    lista = []
    for cid, data in sesiones.items():
        lista.append({
            "chat_id": cid,
            "titulo": data.get("titulo", "Conversación"),
            "creado": data.get("creado", "")
        })
    return {"chats": lista}

@app.get("/api/chats/{chat_id}")
def obtener_chat(chat_id: str):
    sesiones = cargar_todas_sesiones()
    if chat_id in sesiones:
        return sesiones[chat_id]
    return {"titulo": "Nuevo Chat", "mensajes": []}

@app.delete("/api/chats/{chat_id}")
def borrar_chat(chat_id: str):
    sesiones = cargar_todas_sesiones()
    if chat_id in sesiones:
        del sesiones[chat_id]
        guardar_todas_sesiones(sesiones)
    return {"status": "ok"}

@app.get("/api/files/tree")
def tree_endpoint():
    return {"arbol": ["server.py", "index.html", "requirements.txt", "vercel.json"]}

@app.get("/api/system/stats")
def stats_endpoint():
    return {"metricas": {"cpu_uso": "Vercel Serverless", "ram_uso": "Auto-scaled", "disco_libre_gb": "Cloud"}}

@app.get("/")
def interfaz_web():
    return FileResponse("index.html")
