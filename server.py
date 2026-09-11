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

app = FastAPI(title="Aria Studio - Enterprise Multi-Agent Suite")

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
        raise HTTPException(status_code=500, detail="Falta GEMINI_API_KEYS en Vercel.")
    return keys[KEY_INDEX % len(keys)]

def rotar_api_key():
    global KEY_INDEX
    keys = obtener_keys()
    if keys:
        KEY_INDEX = (KEY_INDEX + 1) % len(keys)

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
    timestamp_actual = time.strftime("%Y-%m-%d %H:%M:%S")
    
    if chat_id not in sesiones:
        sesiones[chat_id] = {
            "titulo": titulo if titulo else "Conversación " + time.strftime("%H:%M"),
            "creado": timestamp_actual,
            "mensajes": []
        }
    if len(sesiones[chat_id]["mensajes"]) == 0 and rol == "usuario":
        sesiones[chat_id]["titulo"] = (contenido[:35] + "...") if len(contenido) > 35 else contenido

    sesiones[chat_id]["mensajes"].append({
        "rol": rol,
        "contenido": contenido,
        "timestamp": timestamp_actual
    })
    sesiones[chat_id]["mensajes"] = sesiones[chat_id]["mensajes"][-40:]
    guardar_todas_sesiones(sesiones)

def realizar_busqueda_google(query: str) -> list[str]:
    results = []
    google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    google_cx = os.getenv("GOOGLE_SEARCH_CX", "")
    if google_api_key and google_cx:
        try:
            url = f"https://www.googleapis.com/customsearch/v1?q={requests.utils.quote(query)}&key={google_api_key}&cx={google_cx}&num=3"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                items = res.json().get("items", [])
                for item in items:
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    link = item.get("link", "")
                    results.append(f"[Google] {title}: {snippet} ({link})")
        except Exception:
            pass
    return results

def realizar_busqueda_duckduckgo(query: str) -> list[str]:
    results = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200 and "result__snippet" in res.text:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            snippets = [s.get_text() for s in soup.find_all("a", class_="result__snippet")[:3]]
            for s in snippets:
                results.append(f"[DuckDuckGo] {s.strip()}")
    except Exception:
        pass
    return results

def realizar_busqueda_web_hibrida(query: str) -> str:
    hallazgos = []
    google_res = realizar_busqueda_google(query)
    if google_res:
        hallazgos.extend(google_res)
    ddg_res = realizar_busqueda_duckduckgo(query)
    if ddg_res:
        hallazgos.extend(ddg_res)
    if hallazgos:
        return "\n".join(hallazgos[:5])
    return "No se obtuvieron resultados en tiempo real."

ROLES_PROMPTS = {
    "dev": (
        "Eres Aria AI en modo FULL STACK DEVELOPER.\n"
        "Especialista en Python, JavaScript, FastAPI, SQL y arquitecturas Serverless.\n"
        "Proporciona código limpio, optimizado y libre de bugs."
    ),
    "accounting": (
        "Eres Aria AI en modo ANALISTA CONTABLE Y FISCAL EXPERTO EN VENEZUELA.\n"
        "Tienes dominio completo de normativas SENIAT, IGTF, IVA, ISLR y los siguientes sistemas contables:\n"
        "- SAP\n- PROFIT PLUS\n- ABC-SOFT\n- INFO AUTO\n- ODOO\n"
        "Proporciona análisis estructurados, tablas comparativas y asientos contables precisos."
    ),
    "english": (
        "You are Aria AI in ENGLISH TUTOR Mode.\n"
        "Help the user learn English dynamically. Correct grammar, expand vocabulary, "
        "and provide responses in English with concise Spanish explanations when needed."
    )
}

class ArchivoAdjunto(BaseModel):
    nombre: str
    mime_type: str
    contenido_b64: str

class PeticionChat(BaseModel):
    chat_id: str
    prompt: str
    modo_rol: Optional[str] = "dev"
    web_search: Optional[bool] = False
    archivos: Optional[List[ArchivoAdjunto]] = None

@app.post("/api/chat")
def chat_endpoint(peticion: PeticionChat):
    keys = obtener_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEYS no configurada.")

    historial = obtener_historial_chat(peticion.chat_id)
    conversacion_previa = ""
    for msg in historial[-6:]:
        conversacion_previa += f"\n[{msg['rol'].upper()} - {msg.get('timestamp', '')}]: {msg['contenido']}\n"

    role_instruction = ROLES_PROMPTS.get(peticion.modo_rol, ROLES_PROMPTS["dev"])
    
    web_context = ""
    if peticion.web_search:
        resultados_web = realizar_busqueda_web_hibrida(peticion.prompt)
        web_context = f"\n\nINFORMACIÓN EN TIEMPO REAL (BÚSQUEDA HÍBRIDA GOOGLE + WEB):\n{resultados_web}\n"

    system_instruction = f"{role_instruction}\n{web_context}\nHISTORIAL DE CHAT:\n{conversacion_previa}"

    parts = []
    if peticion.archivos:
        for arch in peticion.archivos:
            if "text" in arch.mime_type or "json" in arch.mime_type or any(arch.nombre.endswith(ext) for ext in [".py", ".csv", ".sql", ".js", ".html", ".css", ".txt"]):
                try:
                    decoded_text = base64.b64decode(arch.contenido_b64.split(",")[-1]).decode("utf-8", errors="ignore")
                    # Truncar código extremadamente largo para evitar Read Timeout
                    if len(decoded_text) > 20000:
                        decoded_text = decoded_text[:20000] + "\n... [CÓDIGO TRUNCADO POR TAMAÑO]"
                    parts.append({"text": f"--- ARCHIVO/CÓDIGO ADJUNTO: {arch.nombre} ---\n{decoded_text}\n--- FIN ARCHIVO ---"})
                except Exception:
                    pass
            else:
                encoded = arch.contenido_b64.split(",")[-1]
                parts.append({"inline_data": {"mime_type": arch.mime_type, "data": encoded}})

    prompt_final = f"{system_instruction}\n\nPETICIÓN ACTUAL: {peticion.prompt if peticion.prompt else 'Analiza los archivos adjuntos.'}"
    parts.append({"text": prompt_final})

    payload = {"contents": [{"parts": parts}]}
    # MODELOS ACTUALIZADOS SEGÚN LA API DE GOOGLE
    modelos = ["gemini-3.6-flash", "gemini-1.5-flash", "gemini-flash-latest"]
    errores = []

    for k_idx in range(len(keys)):
        api_key = obtener_key_actual()
        for mod in modelos:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            try:
                res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
                data = res.json()
                if res.status_code == 200 and "candidates" in data:
                    texto_resp = data["candidates"][0]["content"]["parts"][0]["text"]
                    guardar_mensaje_en_chat(peticion.chat_id, "usuario", peticion.prompt)
                    guardar_mensaje_en_chat(peticion.chat_id, "agente", texto_resp)
                    return {"respuesta": texto_resp}
                else:
                    errores.append(f"Mod {mod} -> {res.status_code}: {data.get('error', {}).get('message', res.text[:100])}")
            except Exception as e:
                errores.append(f"Mod {mod} -> Ex: {str(e)}")
            rotar_api_key()

    raise HTTPException(status_code=500, detail=f"FALLO ARIA SUITE: {' || '.join(errores)}")

@app.get("/api/chats")
def listar_chats():
    sesiones = cargar_todas_sesiones()
    return {"chats": [{"chat_id": k, "titulo": v.get("titulo", "Conversación"), "creado": v.get("creado", "")} for k, v in sesiones.items()]}

@app.get("/api/chats/{chat_id}")
def obtener_chat(chat_id: str):
    sesiones = cargar_todas_sesiones()
    return sesiones.get(chat_id, {"titulo": "Nuevo Chat", "mensajes": []})

@app.delete("/api/chats/{chat_id}")
def borrar_chat(chat_id: str):
    sesiones = cargar_todas_sesiones()
    if chat_id in sesiones:
        del sesiones[chat_id]
        guardar_todas_sesiones(sesiones)
    return {"status": "ok"}

@app.get("/")
def interfaz_web():
    return FileResponse("index.html")
