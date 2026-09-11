#!/bin/bash
pkill -f uvicorn
nohup uvicorn server:app --host 0.0.0.0 --port 8000 --reload > uvicorn.log 2>&1 &
echo "✅ Servidor levantado en segundo plano (PID: $!). Ya puedes cerrar o reutilizar la terminal."
