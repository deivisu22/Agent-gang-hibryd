import os
import sys
import io
import time
import json
import shutil
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError, ClientError

# Cargar variables de entorno
load_dotenv(override=True)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ Error: No se encontró GEMINI_API_KEY en el archivo .env")

client = genai.Client(api_key=api_key)

MODELO_PRINCIPAL = "gemini-3.6-flash"
MODELO_RESPALDO = "gemini-3.5-flash"
ARCHIVO_MEMORIA = "memoria.json"
ARCHIVO_AGENTE = "agente.py"
ARCHIVO_BACKUP = "agente.py.bak"

# -------------------------------------------------------------
# GESTOR DE MEMORIA Y HISTORIAL DE CHAT
# -------------------------------------------------------------

def cargar_memoria() -> dict:
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "reglas_aprendidas": [],
        "historial_de_errores_corregidos": [],
        "historial_conversacion": []
    }

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
    # Mantener últimos 20 mensajes para optimizar contexto
    memoria["historial_conversacion"] = memoria["historial_conversacion"][-20:]
    guardar_memoria(memoria)

# -------------------------------------------------------------
# MOTOR CON RAZONAMIENTO AMPLIADO Y MULTILENGUAJE
# -------------------------------------------------------------

def consultar_gemini_avanzado(prompt: str, modo_razonamiento: bool = True) -> str:
    memoria = cargar_memoria()
    reglas = "\n".join([f"- {r}" for r in memoria.get("reglas_aprendidas", [])])
    
    # Construcción del contexto conversacional previo
    conversacion_previa = ""
    for msg in memoria.get("historial_conversacion", [])[-6:]:
        conversacion_previa += f"\n[{msg['rol'].upper()}]: {msg['contenido']}\n"

    instruccion_sistema = (
        "Eres un Agente Programador Full-Stack Senior Autónomo.\n"
        "Sopotas múltiples lenguajes de programación: Python, JavaScript, TypeScript, Go, Rust, HTML/CSS, SQL y Bash.\n\n"
        "REGLAS DE MEMORIA Y APRENDIZAJE:\n" + reglas + "\n\n"
        "HISTORIAL RECIENTE DE LA SESIÓN:\n" + conversacion_previa
    )

    if modo_razonamiento:
        prompt_final = (
            f"{instruccion_sistema}\n\n"
            "INSTRUCCIÓN DE RAZONAMIENTO AMPLIADO:\n"
            "Antes de generar código o respuesta final, realiza una fase de análisis interno "
            "evaluando arquitectura, casos borde, seguridad y sintaxis del lenguaje objetivo.\n\n"
            f"PETICIÓN ACTUAL:\n{prompt}"
        )
    else:
        prompt_final = f"{instruccion_sistema}\n\nPETICIÓN ACTUAL:\n{prompt}"

    for modelo in [MODELO_PRINCIPAL, MODELO_RESPALDO]:
        for intento in range(1, 4):
            try:
                time.sleep(1)
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt_final
                )
                
                # Registrar interacciones en la memoria conversacional
                guardar_mensaje_historial("usuario", prompt)
                guardar_mensaje_historial("agente", response.text)
                
                return response.text
            except (ServerError, ClientError) as e:
                if "503" in str(e) or "429" in str(e):
                    time.sleep(intento * 2)
                else:
                    break

    raise RuntimeError("❌ Servidores de Google no disponibles tras varios intentos.")

def ejecutar_en_sandbox(codigo: str):
    buffer_salida = io.StringIO()
    sys.stdout = buffer_salida
    entorno_local = {}
    try:
        exec(codigo, entorno_local)
        sys.stdout = sys.__stdout__
        return True, buffer_salida.getvalue()
    except Exception as e:
        sys.stdout = sys.__stdout__
        return False, str(e)

def procesar_solicitud(tarea: str):
    print(f"\n🧠 [RAZONAMIENTO AMPLIADO] Analizando la tarea en múltiples lenguajes...")
    respuesta = consultar_gemini_avanzado(tarea, modo_razonamiento=True)
    print("\n" + "="*60)
    print("RESPUESTA DEL AGENTE:")
    print("="*60)
    print(respuesta)
    print("="*60)

# -------------------------------------------------------------
# CLI INTERACTIVO
# -------------------------------------------------------------

def iniciar_cli():
    print("\n========================================================")
    print("🤖 AGENTE PROGRAMADOR MULTI-LENGUAJE CON RAZONAMIENTO")
    print("========================================================")
    print("Comandos: 'salir', 'historial', 'limpiar_historial'")
    print("--------------------------------------------------------\n")

    while True:
        try:
            user_input = input("\n💬 Petición > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["salir", "exit"]:
                break
            elif user_input.lower() == "historial":
                mem = cargar_memoria()
                print("\n📜 HISTORIAL CONVERSACIONAL:")
                for m in mem.get("historial_conversacion", []):
                    print(f"[{m['timestamp']}] {m['rol'].upper()}: {m['contenido'][:80]}...")
            elif user_input.lower() == "limpiar_historial":
                mem = cargar_memoria()
                mem["historial_conversacion"] = []
                guardar_memoria(mem)
                print("🧹 Historial conversacional limpiado.")
            else:
                procesar_solicitud(user_input)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    iniciar_cli()