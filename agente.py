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

MODELO_PRINCIPAL = "gemini-3.6-flash"
MODELO_RESPALDO = "gemini-3.5-flash"
ARCHIVO_MEMORIA = "memoria.json"

# -------------------------------------------------------------
# GESTOR DE MEMORIA
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
    print("🧠 [MEMORIA] Lección registrada en memoria.json")

def agregar_regla_manual(nueva_regla: str):
    memoria = cargar_memoria()
    if nueva_regla not in memoria.get("reglas_aprendidas", []):
        memoria["reglas_aprendidas"].append(nueva_regla)
        guardar_memoria(memoria)
        print(f"✅ Regla agregada a la memoria: '{nueva_regla}'")

# -------------------------------------------------------------
# HERRAMIENTAS DEL AGENTE (SISTEMA DE ARCHIVOS)
# -------------------------------------------------------------

def guardar_script_en_archivo(nombre_archivo: str, contenido_codigo: str):
    """Guarda el código generado directamente en un archivo físico del proyecto."""
    try:
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            f.write(contenido_codigo)
        print(f"💾 [FILE SYSTEM] Script guardado exitosamente en '{nombre_archivo}'")
        return True
    except Exception as e:
        print(f"❌ Error al guardar archivo: {e}")
        return False

# -------------------------------------------------------------
# CONSULTA RESILIENTE CON MEMORIA
# -------------------------------------------------------------

def consultar_gemini(prompt: str, max_reintentos: int = 3) -> str:
    memoria = cargar_memoria()
    reglas = "\n".join([f"- {r}" for r in memoria.get("reglas_aprendidas", [])])
    
    prompt_con_memoria = (
        "Instrucciones de contexto y memoria:\n"
        f"{reglas}\n\n"
        f"Petición del usuario:\n{prompt}"
    )

    for modelo in [MODELO_PRINCIPAL, MODELO_RESPALDO]:
        for intento in range(1, max_reintentos + 1):
            try:
                time.sleep(1)
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt_con_memoria
                )
                return response.text
            except (ServerError, ClientError) as e:
                if "503" in str(e) or "429" in str(e):
                    time.sleep(intento * 2)
                else:
                    break
    raise RuntimeError("❌ Servidores de Google no disponibles tras varios intentos.")

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
# ORQUESTATOR DEL AGENTE
# -------------------------------------------------------------

def ejecutar_agente(tarea: str, guardar_como: str = None, max_intentos: int = 3):
    print(f"\n🚀 [1/3] Diseñando solución para: '{tarea}'...")
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
            print("   🛠️ Auto-corrigiendo script...")
            prompt_correccion = (
                "El siguiente código Python falló al ejecutarse:\n\n"
                + codigo_final + "\n\nError producido:\n" + str(resultado) +
                "\n\nCorrige el código. Devuelve ÚNICAMENTE el código corregido en un bloque python."
            )
            codigo_final = limpiar_codigo(consultar_gemini(prompt_correccion))
            registrar_aprendizaje(resultado, "Auto-corrección tras fallo en sandbox")

    print("\n⚡ [3/3] Resumiendo resultado...")
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

    if exito and guardar_como:
        guardar_script_en_archivo(guardar_como, codigo_final)

# -------------------------------------------------------------
# CLI INTERACTIVO (CONSOLA EN TIEMPO REAL)
# -------------------------------------------------------------

def iniciar_cli():
    print("\n========================================================")
    print("🤖 AGENTE PROGRAMADOR HÍBRIDO - MODO CONSOLA INTERACTIVA")
    print("========================================================")
    print("Comandos especiales:")
    print("  • 'salir'                  : Finaliza la sesión.")
    print("  • 'memoria'                : Muestra las reglas en memoria.")
    print("  • 'regla <texto>'          : Agrega una nueva regla a memoria.")
    print("  • 'guardar <archivo.py> | <tarea>' : Genera y guarda en archivo.")
    print("--------------------------------------------------------\n")

    while True:
        try:
            user_input = input("\n💬 Petición o Comando > ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["salir", "exit", "quit"]:
                print("👋 Cerrando sesión del agente. ¡Hasta luego!")
                break
                
            elif user_input.lower() == "memoria":
                mem = cargar_memoria()
                print("\n🧠 REGLAS APRENDIDAS:")
                for i, r in enumerate(mem.get("reglas_aprendidas", []), 1):
                    print(f"  {i}. {r}")
                print(f"\n📊 Total errores corregidos registrados: {len(mem.get('historial_de_errores_corregidos', []))}")
                
            elif user_input.lower().startswith("regla "):
                nueva_r = user_input[6:].strip()
                agregar_regla_manual(nueva_r)
                
            elif user_input.lower().startswith("guardar "):
                partes = user_input[8:].split("|")
                if len(partes) == 2:
                    nombre_archivo = partes[0].strip()
                    tarea = partes[1].strip()
                    ejecutar_agente(tarea, guardar_como=nombre_archivo)
                else:
                    print("⚠️ Uso correcto: guardar mi_script.py | Crear una función de ordenamiento...")
            else:
                ejecutar_agente(user_input)
                
        except KeyboardInterrupt:
            print("\n👋 Sesión interrumpida.")
            break

if __name__ == "__main__":
    iniciar_cli()