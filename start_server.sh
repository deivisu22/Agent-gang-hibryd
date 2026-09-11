#!/bin/bash
# Matar procesos anteriores de uvicorn si existen
pkill -f uvicorn

# Iniciar servidor en segundo plano con auto-reload
nohup uvicorn server:app --host 0.0.0.0 --port 8000 --reload > uvicorn.log 2>&1 &

echo "🚀 Servidor iniciado en segundo plano en http://0.0.0.0:8000"
echo "📋 Revisa los logs en tiempo real con: tail -f uvicorn.log"