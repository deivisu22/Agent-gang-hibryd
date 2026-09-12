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

app = FastAPI(title="Aria Studio - Multi-Engine AI Suite")

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
        raise HTTPException(status_code=500, detail="Falta GEMINI_API_KEYS en variables de entorno.")
    return keys[KEY_INDEX % len(keys)]

def rotar_api_key():
    global KEY_INDEX
    keys = obtener_keys()
    if keys:
        KEY_INDEX = (KEY_INDEX + 1) % len(keys)

# PERSISTENCIA
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
ARCHIVO_MEMORIA = "/tmp/aria_chats.json"

def guardar_en_supabase(sessions: dict) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/aria_storage"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        res = requests.post(url, json=[{"id": "global_sessions", "data": sessions}], headers=headers, timeout=4)
        return res.status_code in [200, 201, 204]
    except Exception:
        return False

def obtener_de_supabase() -> Optional[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/aria_storage?id=eq.global_sessions"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            rows = res.json()
            if rows:
                return rows[0].get("data")
    except Exception:
        pass
    return None

def cargar_todas_sesiones() -> dict:
    try:
        sup = obtener_de_supabase()
        if sup is not None:
            return sup
    except Exception:
        pass
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def guardar_todas_sesiones(data: dict):
    try:
        guardar_en_supabase(data)
    except Exception:
        pass
    try:
        with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def obtener_historial_chat(chat_id: str) -> list:
    return cargar_todas_sesiones().get(chat_id, {}).get("mensajes", [])

def guardar_mensaje_en_chat(chat_id: str, rol: str, contenido: str, titulo: str = ""):
    sesiones = cargar_todas_sesiones()
    timestamp_actual = time.strftime("%Y-%m-%d %H:%M:%S")
    
    if chat_id not in sesiones:
        sesiones[chat_id] = {
            "titulo": titulo if titulo else f"Conversación {time.strftime('%H:%M')}",
            "creado": timestamp_actual,
            "mensajes": []
        }
    if len(sesiones[chat_id]["mensajes"]) == 0 and rol == "usuario":
        sesiones[chat_id]["titulo"] = (contenido[:35] + "...") if len(contenido) > 35 else contenido

    sesiones[chat_id]["mensajes"].append({"rol": rol, "contenido": contenido, "timestamp": timestamp_actual})
    sesiones[chat_id]["mensajes"] = sesiones[chat_id]["mensajes"][-40:]
    guardar_todas_sesiones(sesiones)

ROLES_PROMPTS = {
    "dev": "Eres Aria AI en modo FULL STACK DEVELOPER y Arquitecta de Software. Especialista en Python, JS, FastAPI y AI.",
    "accounting": "Eres Aria AI en modo ANALISTA CONTABLE Y FISCAL EXPERTO EN VENEZUELA (SENIAT, IGTF, IVA, ISLR, SAP, Profit Plus).",
    "english": "You are Aria AI in ENGLISH TUTOR Mode. Help the user learn English with dynamic feedback."
}

# --- MOTORES DE INFERENCIA DE IA ---

def ejecutar_ollama_local(prompt: str, system_prompt: str, ollama_url: str, modelo: str) -> str:
    url = f"{ollama_url.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": modelo if modelo else "llama3.2",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    res = requests.post(url, json=payload, timeout=60)
    if res.status_code == 200:
        return res.json()["choices"][0]["message"]["content"]
    raise Exception(f"Ollama Error {res.status_code}: {res.text}")

def ejecutar_groq_cloud(prompt: str, system_prompt: str) -> str:
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise Exception("Falta la variable GROQ_API_KEY en Vercel.")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    res = requests.post(url, json=payload, headers=headers, timeout=25)
    if res.status_code == 200:
        return res.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq Error {res.status_code}: {res.text}")

def ejecutar_gemini_rest(prompt: str, system_prompt: str, archivos: list) -> str:
    keys = obtener_keys()
    current_parts = []
    
    if archivos:
        for arch in archivos:
            if "text" in arch.mime_type or any(arch.nombre.endswith(ext) for ext in [".py", ".csv", ".sql", ".js", ".html", ".css", ".txt", ".json"]):
                try:
                    decoded = base64.b64decode(arch.contenido_b64.split(",")[-1]).decode("utf-8", errors="ignore")
                    current_parts.append({"text": f"--- ARCHIVO: {arch.nombre} ---\n{decoded[:20000]}\n--- FIN ARCHIVO ---"})
                except Exception:
                    pass
            else:
                current_parts.append({"inline_data": {"mime_type": arch.mime_type, "data": arch.contenido_b64.split(",")[-1]}})

    current_parts.append({"text": f"{system_prompt}\n\nPETICIÓN ACTUAL: {prompt}"})
    payload = {"contents": [{"parts": current_parts}]}
    modelos = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-3.5-flash"]
    
    for _ in range(len(keys)):
        api_key = obtener_key_actual()
        for mod in modelos:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            try:
                res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
                data = res.json()
                if res.status_code == 200 and "candidates" in data:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                pass
        rotar_api_key()
    raise Exception("Fallaron todas las claves o modelos de Gemini.")

class ArchivoAdjunto(BaseModel):
    nombre: str
    mime_type: str
    contenido_b64: str

class PeticionChat(BaseModel):
    chat_id: str
    prompt: str
    proveedor: Optional[str] = "gemini" # gemini, ollama, groq
    ollama_url: Optional[str] = "http://localhost:11434"
    ollama_model: Optional[str] = "llama3.2"
    modo_rol: Optional[str] = "dev"
    instrucciones_custom: Optional[str] = ""
    archivos: Optional[List[ArchivoAdjunto]] = None

@app.post("/api/chat")
def chat_endpoint(peticion: PeticionChat):
    role_instruction = ROLES_PROMPTS.get(peticion.modo_rol, ROLES_PROMPTS["dev"])
    if peticion.instrucciones_custom and peticion.instrucciones_custom.strip():
        role_instruction += f"\n\nINSTRUCCIONES EXTRA:\n{peticion.instrucciones_custom.strip()}"

    historial = obtener_historial_chat(peticion.chat_id)
    conversacion_previa = "".join([f"\n[{m.get('rol').upper()}]: {m.get('contenido')}\n" for m in historial[-6:]])
    system_prompt = f"{role_instruction}\n\nHISTORIAL PREVIO:\n{conversacion_previa}"

    prompt_final = peticion.prompt if peticion.prompt.strip() else "Analiza los archivos adjuntos."
    texto_resp = ""

    try:
        if peticion.proveedor == "ollama":
            texto_resp = ejecutar_ollama_local(prompt_final, system_prompt, peticion.ollama_url, peticion.ollama_model)
        elif peticion.proveedor == "groq":
            texto_resp = ejecutar_groq_cloud(prompt_final, system_prompt)
        else:
            texto_resp = ejecutar_gemini_rest(prompt_final, system_prompt, peticion.archivos)

        guardar_mensaje_en_chat(peticion.chat_id, "usuario", prompt_final)
        guardar_mensaje_en_chat(peticion.chat_id, "agente", texto_resp)
        return {"respuesta": texto_resp, "proveedor_usado": peticion.proveedor}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Motor ({peticion.proveedor}): {str(e)}")

@app.get("/api/chats")
def listar_chats():
    return {"chats": [{"chat_id": k, "titulo": v.get("titulo", "Conversación"), "creado": v.get("creado", "")} for k, v in cargar_todas_sesiones().items()]}

@app.get("/api/chats/{chat_id}")
def obtener_chat(chat_id: str):
    return cargar_todas_sesiones().get(chat_id, {"titulo": "Nuevo Chat", "mensajes": []})

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
