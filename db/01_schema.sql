-- ============================================================
-- PROYECTO 2 - Bases de Datos 1 - UVG 2026
-- Schema principal - PostgreSQL
-- ============================================================

-- Crear usuario y base de datos (ejecutar como superusuario)
-- El docker-compose lo maneja automáticamente

-- ============================================================
-- TABLAS
-- ============================================================

CREATE TABLE IF NOT EXISTS categorias (
    id_categoria  SERIAL PRIMARY KEY,
    nombre        VARCHAR(100) NOT NULL,
    descripcion   TEXT
);

CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor  SERIAL PRIMARY KEY,
    nombre        VARCHAR(150) NOT NULL,
    telefono      VARCHAR(20),
    email         VARCHAR(100),
    direccion     TEXT
);

CREATE TABLE IF NOT EXISTS productos (
    id_producto   SERIAL PRIMARY KEY,
    nombre        VARCHAR(150) NOT NULL,
    descripcion   TEXT,
    precio        NUMERIC(10,2) NOT NULL,
    stock         INT NOT NULL DEFAULT 0,
    id_categoria  INT NOT NULL,
    id_proveedor  INT NOT NULL,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria),
    FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor)
);

CREATE TABLE IF NOT EXISTS empleados (
    id_empleado   SERIAL PRIMARY KEY,
    nombre        VARCHAR(150) NOT NULL,
    cargo         VARCHAR(100),
    email         VARCHAR(100),
    telefono      VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS clientes (
    id_cliente    SERIAL PRIMARY KEY,
    nombre        VARCHAR(150) NOT NULL,
    email         VARCHAR(100),
    telefono      VARCHAR(20),
    direccion     TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario    SERIAL PRIMARY KEY,
    username      VARCHAR(80)  NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    rol           VARCHAR(20)  NOT NULL DEFAULT 'empleado'
);

CREATE TABLE IF NOT EXISTS ventas (
    id_venta      SERIAL PRIMARY KEY,
    fecha         TIMESTAMP    NOT NULL DEFAULT NOW(),
    id_cliente    INT          NOT NULL,
    id_empleado   INT          NOT NULL,
    total         NUMERIC(10,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (id_cliente)  REFERENCES clientes(id_cliente),
    FOREIGN KEY (id_empleado) REFERENCES empleados(id_empleado)
);

CREATE TABLE IF NOT EXISTS detalle_venta (
    id_detalle    SERIAL PRIMARY KEY,
    id_venta      INT           NOT NULL,
    id_producto   INT           NOT NULL,
    cantidad      INT           NOT NULL,
    precio_unitario NUMERIC(10,2) NOT NULL,
    subtotal      NUMERIC(10,2) NOT NULL,
    FOREIGN KEY (id_venta)    REFERENCES ventas(id_venta),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
);

-- ============================================================
-- ÍNDICES justificados
-- ============================================================
-- Búsquedas frecuentes por nombre de producto
CREATE INDEX IF NOT EXISTS idx_productos_nombre   ON productos(nombre);
-- Búsquedas de ventas por fecha para reportes
CREATE INDEX IF NOT EXISTS idx_ventas_fecha       ON ventas(fecha);
-- Filtros por categoría
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(id_categoria);

-- ============================================================
-- VIEW: resumen de ventas por producto (alimenta el reporte UI)
-- ============================================================
CREATE OR REPLACE VIEW vista_reporte_ventas AS
SELECT
    p.id_producto,
    p.nombre        AS producto,
    c.nombre        AS categoria,
    SUM(dv.cantidad)             AS unidades_vendidas,
    SUM(dv.subtotal)             AS ingresos_totales,
    COUNT(DISTINCT dv.id_venta)  AS num_ventas
FROM detalle_venta dv
JOIN productos  p ON p.id_producto  = dv.id_producto
JOIN categorias c ON c.id_categoria = p.id_categoria
GROUP BY p.id_producto, p.nombre, c.nombre;