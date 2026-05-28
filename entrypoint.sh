#!/bin/sh
set -e

# Esperar un momento extra por si la DB tarda
sleep 2

# Crear usuarios si no existen
python -c "
import sys
sys.path.insert(0, '/app')
from backend.app import init_usuarios()
init_usuarios()
print('Usuarios inicializados correctamente.')
"

# Arrancar Flask
exec python backend/app.py