#!/bin/bash
echo "⚡ Iniciando servidor backend..."
pkill -f uvicorn
pkill -f cloudflared

nohup uvicorn server:app --host 0.0.0.0 --port 8000 --reload > uvicorn.log 2>&1 &

sleep 3
echo "🌐 Generando túnel de dominio personalizado y seguro..."
cloudflared tunnel --url http://localhost:8000
