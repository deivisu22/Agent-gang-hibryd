import os
import sys
import io
import time
import json
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError, ClientError

# Cargar variables de entorno
load_dotenv(override=True)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ Error: No se encontró GEMINI_API_KEY en el archivo .env")

client = genai.Client(api_key=api_key)

# Modelos principal y de respaldo
MODELO_PRINCIPAL = "gemini-3.6-flash"
MODELO_RESPALDO = "gemini-3.5-flash"
ARCHIVO_MEMORIA = "memoria.json"

# -------------------------------------------------------------
# GESTOR DE MEMORIA Y APRENDIZAJE
# -------------------------------------------------------------

def cargar_memoria() -> dict:
    if os.path.exists(ARCHIVO_MEMORIA):
        try:
            with open(ARCHIVO_MEMORIA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"reglas_aprendidas": [], "historial_de_errores_corregidos": []}

def guardar_memoria(memoria: dict):
    with open(ARCHIVO_MEMORIA, "w", encoding="utf-8") as f:
        json.dump(memoria, f, indent=2, ensure_ascii=False)

def registrar_aprendizaje(error: str, solucion: str):
    memoria = cargar_memoria()
    nuevo_registro = {
        "error": str(error),
        "solucion": str(solucion),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    memoria["historial_de_errores_corregidos"].append(nuevo_registro)
    guardar_memoria(memoria)
    print("🧠 [MEMORIA] Se registró una nueva lección en memoria.json")

# -------------------------------------------------------------
# CONSULTA RESILIENTE (REINTENTOS AUTOMÁTICOS + FALLBACK)
# -------------------------------------------------------------

def consultar_gemini(prompt: str, max_reintentos: int = 3) -> str:
    memoria = cargar_memoria()
    reglas = "\n".join([f"- {r}" for r in memoria.get("reglas_aprendidas", [])])
    
    prompt_con_memoria = (
        "Sigue estrictamente estas reglas de aprendizaje previo:\n"
        f"{reglas}\n\n"
        f"Instrucción actual:\n{prompt}"
    )

    modelos_a_probar = [MODELO_PRINCIPAL, MODELO_RESPALDO]

    for modelo in modelos_a_probar:
        for intento in range(1, max_reintentos + 1):
            try:
                time.sleep(1) # Control de ritmo
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt_con_memoria
                )
                return response.text
            except (ServerError, ClientError) as e:
                # Captura sobrecarga (503) o cuota temporal (429)
                if "503" in str(e) or "429" in str(e):
                    tiempo_espera = intento * 3
                    print(f"⚠️ Servidor ocupado en '{modelo}' (Error 503/429). Reintentando en {tiempo_espera}s... (Intento {intento}/{max_reintentos})")
                    time.sleep(tiempo_espera)
                else:
                    break  # Si es otro error (ej. 404/400), pasa al modelo de respaldo
        print(f"🔄 Cambiando al modelo de respaldo por saturación...")

    raise RuntimeError("❌ No se pudo conectar con los servidores de Google tras varios reintentos.")

def motor_auditor(codigo: str) -> str:
    prompt_sistema = (
        "Actúa como un auditor de código Senior. Revisa, corrige errores sintácticos, "
        "optimiza el rendimiento y devuelve el código Python perfectamente refactorizado.\n\n"
        "Código a auditar:\n" + str(codigo)
    )
    return consultar_gemini(prompt_sistema)

def limpiar_codigo(texto: str) -> str:
    if "```python" in texto:
        texto = texto.split("```python")[1].split("```")[0]
    elif "```" in texto:
        texto = texto.split("```")[1].split("```")[0]
    return texto.strip()

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

# -------------------------------------------------------------
# ORQUESTATOR PRINCIPAL CON AUTO-CORRECCIÓN Y MEMORIA
# -------------------------------------------------------------

def ejecutar_agente(tarea: str, max_intentos: int = 3):
    print(f"\n🚀 [1/3] Diseñando solución con memoria activa para: '{tarea}'...")
    prompt_inicial = (
        f"Escribe un script en Python completo y funcional para: {tarea}.\n"
        "Incluye pruebas al final con print() para verificar su salida.\n"
        "Responde ÚNICAMENTE con el código en un bloque markdown python."
    )
    
    codigo_raw = consultar_gemini(prompt_inicial)
    codigo_limpio = limpiar_codigo(codigo_raw)
    
    print("🔍 [2/3] Auditando y refactorizando...")
    codigo_refactorizado = motor_auditor(codigo_limpio)
    codigo_final = limpiar_codigo(codigo_refactorizado)
    
    print("⚙️ Ejecutando en Sandbox...")
    exito, resultado = False, ""
    
    for intento in range(1, max_intentos + 1):
        print(f"   👉 Intento {intento}/{max_intentos}...")
        exito, resultado = ejecutar_en_sandbox(codigo_final)
        
        if exito:
            print("   ✅ ¡Ejecución limpia y sin errores!")
            break
        else:
            print(f"   ⚠️ Error detectado: {resultado}")
            print("   🛠️ Auto-corrigiendo y registrando lección...")
            
            prompt_correccion = (
                "El siguiente código Python falló al ejecutarse:\n\n"
                + codigo_final + "\n\nError producido:\n" + str(resultado) +
                "\n\nCorrige el código. Devuelve ÚNICAMENTE el código corregido en un bloque python."
            )
            codigo_corregido_raw = consultar_gemini(prompt_correccion)
            codigo_final = limpiar_codigo(codigo_corregido_raw)
            
            registrar_aprendizaje(resultado, "Código auto-corregido tras fallo en sandbox")

    print("\n⚡ [3/3] Generando resumen...")
    resumen = consultar_gemini("Resume en 2 oraciones qué hace este código:\n\n" + codigo_final)
    
    print("\n" + "="*60)
    print("ESTADO:", "ÉXITO EN SANDBOX" if exito else "ERROR NO RESUELTO")
    print("\nSALIDA DE CONSOLA:")
    print(resultado if exito else "No ejecutó correctamente.")
    print("\nRESUMEN TÉCNICO:")
    print(resumen)
    print("\nCÓDIGO PYTHON FINAL:")
    print(codigo_final)
    print("="*60)

if __name__ == "__main__":
    ejecutar_agente("Crear una función que filtre palabras duplicadas de una lista y las devuelva ordenadas alfabéticamente.")