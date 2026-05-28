-- ============================================================
-- PROYECTO 3 - Roles y Permisos en el DBMS
-- PostgreSQL - Ejecutado como superusuario (proy3)
-- ============================================================
-- Nota: proy3 es superusuario creado por docker-compose.
-- Los 5 roles son roles de grupo sin login; los usuarios de
-- prueba (05_seed_usuarios.sql) reciben GRANT de estos roles.
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- 1. ROL: rol_admin
--    Acceso total a todas las tablas. Gestión completa.
-- ──────────────────────────────────────────────────────────
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_admin') THEN
    CREATE ROLE rol_admin;
  END IF;
END $$;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rol_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rol_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rol_admin;

-- ──────────────────────────────────────────────────────────
-- 2. ROL: rol_supervisor
--    Lee todo. Puede modificar productos y empleados.
--    No puede eliminar ventas ni usuarios.
-- ──────────────────────────────────────────────────────────
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_supervisor') THEN
    CREATE ROLE rol_supervisor;
  END IF;
END $$;

-- Lectura total
GRANT SELECT ON categorias, proveedores, productos, empleados,
               clientes, ventas, detalle_venta, usuarios TO rol_supervisor;
-- Modificar productos e inventario
GRANT INSERT, UPDATE ON productos TO rol_supervisor;
GRANT USAGE, SELECT ON SEQUENCE productos_id_producto_seq TO rol_supervisor;
-- Modificar empleados
GRANT INSERT, UPDATE ON empleados TO rol_supervisor;
GRANT USAGE, SELECT ON SEQUENCE empleados_id_empleado_seq TO rol_supervisor;
-- Ejecutar stored procedures
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rol_supervisor;

-- ──────────────────────────────────────────────────────────
-- 3. ROL: rol_vendedor
--    Puede crear ventas y ver clientes/productos.
--    No puede modificar precios ni ver reportes internos.
-- ──────────────────────────────────────────────────────────
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_vendedor') THEN
    CREATE ROLE rol_vendedor;
  END IF;
END $$;

-- Lectura de lo necesario para vender
GRANT SELECT ON productos, categorias, clientes, empleados TO rol_vendedor;
-- Registrar ventas
GRANT SELECT, INSERT ON ventas TO rol_vendedor;
GRANT USAGE, SELECT ON SEQUENCE ventas_id_venta_seq TO rol_vendedor;
GRANT SELECT, INSERT ON detalle_venta TO rol_vendedor;
GRANT USAGE, SELECT ON SEQUENCE detalle_venta_id_detalle_seq TO rol_vendedor;
-- Actualizar stock (necesario al vender)
GRANT UPDATE (stock) ON productos TO rol_vendedor;
-- Ejecutar stored procedures de venta
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rol_vendedor;
-- Sin acceso a usuarios
REVOKE ALL ON usuarios FROM rol_vendedor;

-- ──────────────────────────────────────────────────────────
-- 4. ROL: rol_bodeguero
--    Gestiona inventario: lee y actualiza stock de productos.
--    No puede ver ventas completas ni usuarios.
-- ──────────────────────────────────────────────────────────
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_bodeguero') THEN
    CREATE ROLE rol_bodeguero;
  END IF;
END $$;

-- Ver y actualizar productos
GRANT SELECT ON productos, categorias, proveedores TO rol_bodeguero;
GRANT UPDATE (stock, descripcion) ON productos TO rol_bodeguero;
-- Ver ventas para conocer qué se vendió (solo lectura)
GRANT SELECT ON ventas, detalle_venta TO rol_bodeguero;
-- Sin acceso a clientes, empleados ni usuarios
REVOKE ALL ON clientes FROM rol_bodeguero;
REVOKE ALL ON usuarios FROM rol_bodeguero;
-- Ejecutar SP de ajuste de inventario
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rol_bodeguero;

-- ──────────────────────────────────────────────────────────
-- 5. ROL: rol_reportes
--    Solo lectura. Accede a reportes y vistas.
--    No puede modificar ningún dato.
-- ──────────────────────────────────────────────────────────
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rol_reportes') THEN
    CREATE ROLE rol_reportes;
  END IF;
END $$;

-- Solo SELECT en tablas de negocio (no en usuarios)
GRANT SELECT ON categorias, proveedores, productos,
               empleados, clientes, ventas, detalle_venta TO rol_reportes;
-- Acceso a la vista de reportes
GRANT SELECT ON vista_reporte_ventas TO rol_reportes;
-- Sin acceso a usuarios
REVOKE ALL ON usuarios FROM rol_reportes;
-- Sin INSERT, UPDATE ni DELETE en ninguna tabla
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM rol_reportes;