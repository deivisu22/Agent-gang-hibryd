import os
import shutil
import time

def ejecutar_limpieza():
    print("🧹 [Auto-Cleaner] Iniciando rutina de mantenimiento...")
    
    # 1. Eliminar archivos temporales de Python
    for raiz, dirs, archivos in os.walk("."):
        if "__pycache__" in dirs:
            ruta_cache = os.path.join(raiz, "__pycache__")
            shutil.rmtree(ruta_cache)
            print(f"🗑️ Eliminado: {ruta_cache}")
            
    # 2. Controlar tamaño del log de uvicorn
    if os.path.exists("uvicorn.log"):
        tamano_mb = os.path.getsize("uvicorn.log") / (1024 * 1024)
        if tamano_mb > 10:
            with open("uvicorn.log", "w") as f:
                f.write(f"--- LOG REINICIADO POR AUTO-CLEANER ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
            print("✂️ Log uvicorn.log truncado por exceder 10MB.")

    # 3. Respaldo incremental de memoria
    if os.path.exists("memoria.json"):
        shutil.copy("memoria.json", "memoria_backup.json")
        print("💾 Respaldo 'memoria_backup.json' actualizado.")

if __name__ == "__main__":
    ejecutar_limpieza()
