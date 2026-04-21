#!/bin/sh
set -e

# Esperar un momento extra por si la DB tarda
sleep 2

# Crear usuario admin si no existe
python -c "
import sys
sys.path.insert(0, '/app')
from backend.app import init_admin
init_admin()
print('Admin inicializado.')
"

# Arrancar Flask
exec python backend/app.py