#!/bin/sh
set -e

# Esperar un momento extra por si la DB tarda
sleep 2

# Crear usuarios si no existen
python3 -c "
content = '#!/bin/sh\nset -e\nsleep 2\npython -c \"import sys; sys.path.insert(0, /app); from backend.app import init_usuarios; init_usuarios()\"\nexec python backend/app.py\n'
content = content.replace('/app', \"'/app'\")
with open('entrypoint.sh', 'w') as f:
    f.write(content)
print('OK')
"

# Arrancar Flask
exec python backend/app.py