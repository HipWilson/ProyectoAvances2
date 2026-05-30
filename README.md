# TiendaDB — Proyecto 3
**Bases de Datos 1 | Wilson Peña - 24760**

Sistema web de gestión de inventario y ventas, extendido con seguridad a nivel de base de datos: roles y permisos en el DBMS, stored procedures y ORM (SQLAlchemy).

Stack: **Python/Flask · SQLAlchemy (ORM) · PostgreSQL · HTML/CSS/JS · Docker**

---

## Levantar el proyecto desde cero

```bash
# 1. Clonar el repositorio y entrar a la carpeta
git clone <URL_DEL_REPO>
cd tienda

# 2. Cambiar a la rama del proyecto
git checkout proyecto-3

# 3. Copiar variables de entorno (ya vienen configuradas)
cp .env.example .env

# 4. Levantar todo con Docker
docker compose up --build
```

Abrir en el navegador: **http://localhost:5000**

> Si ya tienes el volumen de una corrida anterior y quieres empezar limpio:
> ```bash
> docker compose down -v
> docker compose up --build
> ```

---

## Credenciales de base de datos

| Variable     | Valor      |
|--------------|------------|
| `DB_USER`    | `proy3`    |
| `DB_PASSWORD`| `secret`   |
| `DB_NAME`    | `tiendadb` |
| `DB_HOST`    | `db`       |
| `DB_PORT`    | `5432`     |

---

## Usuarios de prueba (1 por cada rol)

Todos creados automáticamente al primer arranque por `init_usuarios()`.

| Usuario               | Contraseña  | Rol         |
|-----------------------|-------------|-------------|
| `admin_usuario`       | `secret123` | admin       |
| `supervisor_usuario`  | `secret123` | supervisor  |
| `vendedor_usuario`    | `secret123` | vendedor    |
| `bodeguero_usuario`   | `secret123` | bodeguero   |
| `reportes_usuario`    | `secret123` | reportes    |

> También existe el usuario `admin` con contraseña `admin123` (rol admin).

---

## Qué puede hacer cada rol en la UI

| Sección      | admin | supervisor | vendedor | bodeguero | reportes |
|--------------|:-----:|:----------:|:--------:|:---------:|:--------:|
| Dashboard    | ✓     | ✓          | ✓        | ✓         | ✓        |
| Productos    | ✓     | ✓ (sin eliminar) | solo ver | solo ver | solo ver |
| Inventario   | ✓     | ✓          | —        | ✓         | —        |
| Clientes     | ✓     | ✓          | ✓ (sin eliminar) | — | solo ver |
| Empleados    | ✓     | ✓          | —        | —         | —        |
| Ventas       | ✓     | ✓ (sin crear) | ✓     | solo ver  | solo ver |
| Reportes     | ✓     | ✓          | —        | —         | ✓        |

---

## Estructura del proyecto

```
tienda/
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh
├── .env
├── .env.example
├── db/
│   ├── 01_schema.sql              ← DDL: tablas, índices, VIEW
│   ├── 02_seed.sql                ← Datos de prueba (25+ registros por tabla)
│   ├── 03_roles.sql               ← 5 roles con CREATE ROLE, GRANT, REVOKE
│   ├── 04_stored_procedures.sql   ← 6 stored procedures PL/pgSQL
│   └── 05_seed_usuarios.sql       ← 1 usuario por rol
├── backend/
│   ├── app.py                     ← Flask + ORM + SPs + decoradores de rol
│   ├── models.py                  ← Modelos SQLAlchemy
│   └── requirements.txt
└── frontend/
    ├── templates/
    │   ├── base.html              ← Navegación condicional por rol
    │   ├── login.html             ← Tabla de usuarios de prueba
    │   ├── dashboard.html
    │   ├── productos.html
    │   ├── inventario.html        ← Vista exclusiva para bodeguero/admin
    │   ├── clientes.html
    │   ├── empleados.html
    │   ├── ventas.html
    │   └── reportes.html
    └── static/
        ├── css/style.css
        └── js/main.js
```

---

## I. Seguridad y Roles

### 5 Roles definidos en el DBMS (`db/03_roles.sql`)

Creados con `CREATE ROLE`, permisos asignados con `GRANT` y removidos con `REVOKE`, granulares por tabla y operación.

| Rol              | Tablas con acceso                                                     | Operaciones                                  |
|------------------|-----------------------------------------------------------------------|----------------------------------------------|
| `rol_admin`      | Todas                                                                 | ALL (SELECT, INSERT, UPDATE, DELETE, EXECUTE)|
| `rol_supervisor` | Todas (lectura) + productos + empleados (escritura)                   | SELECT todas; INSERT/UPDATE productos/empleados |
| `rol_vendedor`   | productos, categorias, clientes, empleados, ventas, detalle_venta     | SELECT; INSERT ventas/detalle; UPDATE stock  |
| `rol_bodeguero`  | productos, categorias, proveedores, ventas, detalle_venta             | SELECT; UPDATE stock y descripcion           |
| `rol_reportes`   | categorias, proveedores, productos, empleados, clientes, ventas, detalle_venta, vista_reporte_ventas | Solo SELECT |

### Autenticación y protección de rutas

- Login/logout con `flask.session` y contraseñas hasheadas con `werkzeug`.
- Decorador `@rol_required(...)` en cada ruta del backend.
- Navegación lateral (`base.html`) usa `puede_acceder(endpoint)` para mostrar u ocultar ítems según el rol activo.
- Acceso denegado redirige al dashboard con mensaje de error.

---

## II. Stored Procedures

### 6 SPs definidos en `db/04_stored_procedures.sql`, invocados desde `backend/app.py`

| Stored Procedure              | Ruta que lo invoca              | Descripción                                                    |
|-------------------------------|---------------------------------|----------------------------------------------------------------|
| `sp_registrar_venta`          | `POST /ventas/nueva`            | Registra venta completa. Params IN/OUT. ROLLBACK si falla stock |
| `sp_ajustar_stock`            | `POST /inventario/ajustar`      | Ajusta stock +/-. Params IN/OUT. Excepción si queda negativo   |
| `sp_crear_producto`           | `POST /productos/nuevo`         | Crea producto con validaciones de negocio. Params IN/OUT       |
| `sp_eliminar_cliente`         | `POST /clientes/eliminar`       | Elimina cliente solo si no tiene ventas. Params IN/OUT         |
| `sp_reporte_ventas_periodo`   | `GET /reportes`                 | Resumen de ventas entre fechas. Params IN/OUT                  |
| `sp_transferir_stock`         | `POST /inventario/transferir`   | Transfiere stock entre productos. **SAVEPOINT / ROLLBACK**     |

### Transacción explícita con ROLLBACK

`sp_transferir_stock` usa `SAVEPOINT sp_transferencia` y `ROLLBACK TO SAVEPOINT` dentro del stored procedure si el stock es insuficiente. El backend lo envuelve adicionalmente con `BEGIN` / `COMMIT` / `ROLLBACK` explícitos.

Todos los SPs tienen:
- Parámetros `OUT` (al menos `p_mensaje TEXT`)
- Bloque `EXCEPTION WHEN OTHERS` con `RAISE` para propagar el error al backend

---

## III. ORM (SQLAlchemy)

Modelos definidos en `backend/models.py`. Más de 3 operaciones CRUD realizadas vía ORM en `backend/app.py`:

| Operación | Modelo    | Ruta                              |
|-----------|-----------|-----------------------------------|
| READ      | `Usuario` | `GET /login` (autenticación)      |
| READ      | `Categoria`, `Proveedor` | `GET /productos`     |
| UPDATE    | `Producto`| `POST /productos/editar/<id>`     |
| DELETE    | `Producto`| `POST /productos/eliminar/<id>`   |
| CREATE    | `Cliente` | `POST /clientes/nuevo`            |
| UPDATE    | `Cliente` | `POST /clientes/editar/<id>`      |
| READ      | `Producto`| `GET /inventario`                 |
| READ      | `Empleado`| `GET /empleados`                  |
| CREATE    | `Empleado`| `POST /empleados/nuevo`           |
| UPDATE    | `Empleado`| `POST /empleados/editar/<id>`     |
| DELETE    | `Empleado`| `POST /empleados/eliminar/<id>`   |

---

## IV. Consultas SQL avanzadas (del Proyecto 2, mantenidas)

| Técnica              | Dónde se usa                          |
|----------------------|---------------------------------------|
| JOIN 3 tablas        | Dashboard (últimas ventas)            |
| JOIN 3 tablas        | Página de productos                   |
| JOIN + GROUP BY      | Página de ventas                      |
| Subquery correlacionado | Página de clientes (total gastado) |
| Subquery EXISTS      | Ventas (productos con stock > 0)      |
| GROUP BY + HAVING    | Reportes (ingresos por categoría)     |
| CTE (WITH)           | Reportes (top 5 clientes)             |
| VIEW                 | `vista_reporte_ventas` en reportes    |
| Transacción explícita| `POST /ventas/nueva` y todos los SPs  |

---

## V. Índices

```sql
CREATE INDEX idx_productos_nombre    ON productos(nombre);
CREATE INDEX idx_ventas_fecha        ON ventas(fecha);
CREATE INDEX idx_productos_categoria ON productos(id_categoria);
```

---

## Notas de entrega

- Rama: `proyecto-3` del repositorio del Proyecto 2
- Credenciales fijas: usuario `proy3`, contraseña `secret`
- Levanta con: `docker compose up --build`