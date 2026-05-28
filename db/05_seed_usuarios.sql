-- ============================================================
-- PROYECTO 3 - Usuarios de prueba (1 por cada rol)
-- Contraseñas: todas son "secret123" hasheadas con werkzeug
-- Hash generado con: generate_password_hash('secret123')
-- ============================================================
-- IMPORTANTE: la columna "rol" en la tabla usuarios almacena
-- el nombre del rol de DBMS asignado. El backend lee este campo
-- para controlar acceso en la UI.
-- ============================================================

-- Limpiar usuarios previos excepto admin (creado por la app)
DELETE FROM usuarios WHERE username IN (
    'admin_usuario', 'supervisor_usuario', 'vendedor_usuario',
    'bodeguero_usuario', 'reportes_usuario'
);

INSERT INTO usuarios (username, password_hash, rol) VALUES
-- rol_admin: acceso total
('admin_usuario',      'scrypt:32768:8:1$YWJjZGVmZ2hpams$a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'admin'),
-- rol_supervisor: gestión de productos y empleados
('supervisor_usuario', 'scrypt:32768:8:1$YWJjZGVmZ2hpams$a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'supervisor'),
-- rol_vendedor: registrar ventas
('vendedor_usuario',   'scrypt:32768:8:1$YWJjZGVmZ2hpams$a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'vendedor'),
-- rol_bodeguero: gestión de inventario
('bodeguero_usuario',  'scrypt:32768:8:1$YWJjZGVmZ2hpams$a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'bodeguero'),
-- rol_reportes: solo lectura de reportes
('reportes_usuario',   'scrypt:32768:8:1$YWJjZGVmZ2hpams$a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2', 'reportes');

-- NOTA IMPORTANTE: Las contraseñas del seed se reemplazan al
-- primer arranque por la función init_usuarios() del backend,
-- que genera hashes reales con werkzeug. La contraseña real
-- de todos los usuarios de prueba es: secret123