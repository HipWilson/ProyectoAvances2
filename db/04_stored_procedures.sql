-- ============================================================
-- PROYECTO 3 - Stored Procedures
-- PostgreSQL (PL/pgSQL)
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- SP 1: sp_registrar_venta
--    Registra una venta completa con transacción explícita.
--    Parámetros IN: cliente, empleado, productos (JSON array)
--    Parámetro OUT: id de la venta creada, mensaje de resultado
--    Maneja excepciones con ROLLBACK si stock es insuficiente.
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION sp_registrar_venta(
    p_id_cliente   INT,
    p_id_empleado  INT,
    p_items        JSON,         -- [{"id_producto": 1, "cantidad": 2}, ...]
    OUT p_id_venta INT,
    OUT p_mensaje  TEXT
)
RETURNS RECORD
LANGUAGE plpgsql
AS $$
DECLARE
    v_item         JSON;
    v_id_producto  INT;
    v_cantidad     INT;
    v_precio       NUMERIC(10,2);
    v_stock        INT;
    v_nombre_prod  VARCHAR(150);
    v_subtotal     NUMERIC(10,2);
    v_total        NUMERIC(10,2) := 0;
BEGIN
    -- Validar que exista el cliente
    IF NOT EXISTS (SELECT 1 FROM clientes WHERE id_cliente = p_id_cliente) THEN
        RAISE EXCEPTION 'Cliente con id % no existe', p_id_cliente;
    END IF;

    -- Validar que exista el empleado
    IF NOT EXISTS (SELECT 1 FROM empleados WHERE id_empleado = p_id_empleado) THEN
        RAISE EXCEPTION 'Empleado con id % no existe', p_id_empleado;
    END IF;

    -- Iterar sobre los items y verificar stock (con bloqueo FOR UPDATE)
    FOR v_item IN SELECT * FROM json_array_elements(p_items)
    LOOP
        v_id_producto := (v_item->>'id_producto')::INT;
        v_cantidad    := (v_item->>'cantidad')::INT;

        IF v_cantidad <= 0 THEN
            RAISE EXCEPTION 'Cantidad inválida (%) para producto %', v_cantidad, v_id_producto;
        END IF;

        SELECT precio, stock, nombre
          INTO v_precio, v_stock, v_nombre_prod
          FROM productos
         WHERE id_producto = v_id_producto
           FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Producto con id % no existe', v_id_producto;
        END IF;

        IF v_stock < v_cantidad THEN
            RAISE EXCEPTION 'Stock insuficiente para "%" (disponible: %, pedido: %)',
                            v_nombre_prod, v_stock, v_cantidad;
        END IF;

        v_subtotal := ROUND(v_precio * v_cantidad, 2);
        v_total    := v_total + v_subtotal;
    END LOOP;

    -- Insertar cabecera de venta
    INSERT INTO ventas (id_cliente, id_empleado, total)
    VALUES (p_id_cliente, p_id_empleado, ROUND(v_total, 2))
    RETURNING id_venta INTO p_id_venta;

    -- Insertar detalle y descontar stock
    FOR v_item IN SELECT * FROM json_array_elements(p_items)
    LOOP
        v_id_producto := (v_item->>'id_producto')::INT;
        v_cantidad    := (v_item->>'cantidad')::INT;

        SELECT precio INTO v_precio FROM productos WHERE id_producto = v_id_producto;
        v_subtotal := ROUND(v_precio * v_cantidad, 2);

        INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal)
        VALUES (p_id_venta, v_id_producto, v_cantidad, v_precio, v_subtotal);

        UPDATE productos
           SET stock = stock - v_cantidad
         WHERE id_producto = v_id_producto;
    END LOOP;

    p_mensaje := 'Venta #' || p_id_venta || ' registrada correctamente por Q' || ROUND(v_total, 2);

EXCEPTION
    WHEN OTHERS THEN
        -- ROLLBACK implícito al lanzar la excepción desde PL/pgSQL
        p_id_venta := NULL;
        p_mensaje  := 'ERROR: ' || SQLERRM;
        RAISE;  -- re-lanzar para que el backend haga ROLLBACK explícito
END;
$$;


-- ──────────────────────────────────────────────────────────
-- SP 2: sp_ajustar_stock
--    Ajusta el stock de un producto (entrada o salida).
--    Parámetros IN: id_producto, cantidad (puede ser negativa), motivo
--    Parámetro OUT: stock_anterior, stock_nuevo, mensaje
--    Lanza excepción si el resultado dejara stock negativo.
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION sp_ajustar_stock(
    p_id_producto   INT,
    p_cantidad      INT,         -- positivo = entrada, negativo = salida
    p_motivo        TEXT,
    OUT p_stock_anterior INT,
    OUT p_stock_nuevo    INT,
    OUT p_mensaje        TEXT
)
RETURNS RECORD
LANGUAGE plpgsql
AS $$
BEGIN
    SELECT stock INTO p_stock_anterior
      FROM productos
     WHERE id_producto = p_id_producto
       FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Producto con id % no encontrado', p_id_producto;
    END IF;

    p_stock_nuevo := p_stock_anterior + p_cantidad;

    IF p_stock_nuevo < 0 THEN
        RAISE EXCEPTION 'Ajuste inválido: stock resultante sería % (motivo: %)',
                        p_stock_nuevo, p_motivo;
    END IF;

    UPDATE productos
       SET stock = p_stock_nuevo
     WHERE id_producto = p_id_producto;

    p_mensaje := 'Stock ajustado: ' || p_stock_anterior || ' → ' || p_stock_nuevo
                 || ' (motivo: ' || COALESCE(p_motivo, 'sin motivo') || ')';

EXCEPTION
    WHEN OTHERS THEN
        p_stock_nuevo := p_stock_anterior;
        p_mensaje     := 'ERROR: ' || SQLERRM;
        RAISE;
END;
$$;


-- ──────────────────────────────────────────────────────────
-- SP 3: sp_crear_producto
--    Crea un nuevo producto con validaciones de negocio.
--    Parámetros IN: todos los campos del producto
--    Parámetro OUT: id generado, mensaje
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION sp_crear_producto(
    p_nombre       VARCHAR(150),
    p_descripcion  TEXT,
    p_precio       NUMERIC(10,2),
    p_stock        INT,
    p_id_categoria INT,
    p_id_proveedor INT,
    OUT p_id_producto INT,
    OUT p_mensaje     TEXT
)
RETURNS RECORD
LANGUAGE plpgsql
AS $$
BEGIN
    -- Validaciones
    IF p_nombre IS NULL OR TRIM(p_nombre) = '' THEN
        RAISE EXCEPTION 'El nombre del producto no puede estar vacío';
    END IF;

    IF p_precio <= 0 THEN
        RAISE EXCEPTION 'El precio debe ser mayor que cero (recibido: %)', p_precio;
    END IF;

    IF p_stock < 0 THEN
        RAISE EXCEPTION 'El stock inicial no puede ser negativo (recibido: %)', p_stock;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM categorias WHERE id_categoria = p_id_categoria) THEN
        RAISE EXCEPTION 'Categoría con id % no existe', p_id_categoria;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM proveedores WHERE id_proveedor = p_id_proveedor) THEN
        RAISE EXCEPTION 'Proveedor con id % no existe', p_id_proveedor;
    END IF;

    INSERT INTO productos (nombre, descripcion, precio, stock, id_categoria, id_proveedor)
    VALUES (TRIM(p_nombre), p_descripcion, p_precio, p_stock, p_id_categoria, p_id_proveedor)
    RETURNING id_producto INTO p_id_producto;

    p_mensaje := 'Producto "' || p_nombre || '" creado con id ' || p_id_producto;

EXCEPTION
    WHEN OTHERS THEN
        p_id_producto := NULL;
        p_mensaje     := 'ERROR: ' || SQLERRM;
        RAISE;
END;
$$;


-- ──────────────────────────────────────────────────────────
-- SP 4: sp_eliminar_cliente
--    Elimina un cliente solo si no tiene ventas asociadas.
--    Parámetros IN: id_cliente
--    Parámetro OUT: eliminado (bool), mensaje
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION sp_eliminar_cliente(
    p_id_cliente  INT,
    OUT p_eliminado BOOLEAN,
    OUT p_mensaje   TEXT
)
RETURNS RECORD
LANGUAGE plpgsql
AS $$
DECLARE
    v_num_ventas INT;
    v_nombre     VARCHAR(150);
BEGIN
    SELECT nombre INTO v_nombre
      FROM clientes
     WHERE id_cliente = p_id_cliente;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cliente con id % no existe', p_id_cliente;
    END IF;

    SELECT COUNT(*) INTO v_num_ventas
      FROM ventas
     WHERE id_cliente = p_id_cliente;

    IF v_num_ventas > 0 THEN
        RAISE EXCEPTION 'No se puede eliminar: el cliente "%" tiene % venta(s) registrada(s)',
                        v_nombre, v_num_ventas;
    END IF;

    DELETE FROM clientes WHERE id_cliente = p_id_cliente;

    p_eliminado := TRUE;
    p_mensaje   := 'Cliente "' || v_nombre || '" eliminado correctamente';

EXCEPTION
    WHEN OTHERS THEN
        p_eliminado := FALSE;
        p_mensaje   := 'ERROR: ' || SQLERRM;
        RAISE;
END;
$$;


-- ──────────────────────────────────────────────────────────
-- SP 5: sp_reporte_ventas_periodo
--    Genera un resumen de ventas entre dos fechas.
--    Parámetros IN: fecha_inicio, fecha_fin
--    Parámetro OUT: total_ventas, total_ingresos, mensaje
--    Devuelve también un resultado tabular (SETOF RECORD).
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION sp_reporte_ventas_periodo(
    p_fecha_inicio  TIMESTAMP,
    p_fecha_fin     TIMESTAMP,
    OUT p_total_ventas   INT,
    OUT p_total_ingresos NUMERIC(12,2),
    OUT p_mensaje        TEXT
)
RETURNS RECORD
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_fecha_inicio > p_fecha_fin THEN
        RAISE EXCEPTION 'La fecha de inicio (%) no puede ser mayor que la de fin (%)',
                        p_fecha_inicio, p_fecha_fin;
    END IF;

    SELECT COUNT(*), COALESCE(SUM(total), 0)
      INTO p_total_ventas, p_total_ingresos
      FROM ventas
     WHERE fecha BETWEEN p_fecha_inicio AND p_fecha_fin;

    p_mensaje := 'Reporte del ' || p_fecha_inicio::DATE || ' al ' || p_fecha_fin::DATE
                 || ': ' || p_total_ventas || ' ventas, Q' || p_total_ingresos || ' ingresos';

EXCEPTION
    WHEN OTHERS THEN
        p_total_ventas   := 0;
        p_total_ingresos := 0;
        p_mensaje        := 'ERROR: ' || SQLERRM;
        RAISE;
END;
$$;


-- ──────────────────────────────────────────────────────────
-- SP 6: sp_transferir_stock  ← TRANSACCIÓN EXPLÍCITA CON ROLLBACK
--    Transfiere stock de un producto a otro (reclasificación).
--    Parámetros IN: producto origen, producto destino, cantidad
--    Parámetro OUT: mensaje
--    Contiene BEGIN / SAVEPOINT / ROLLBACK TO SAVEPOINT explícito.
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION sp_transferir_stock(
    p_id_origen   INT,
    p_id_destino  INT,
    p_cantidad    INT,
    OUT p_mensaje TEXT
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_stock_origen  INT;
    v_stock_destino INT;
    v_nombre_origen  VARCHAR(150);
    v_nombre_destino VARCHAR(150);
BEGIN
    -- Savepoint para rollback parcial si algo falla
    SAVEPOINT sp_transferencia;

    IF p_cantidad <= 0 THEN
        RAISE EXCEPTION 'La cantidad a transferir debe ser positiva (recibido: %)', p_cantidad;
    END IF;

    IF p_id_origen = p_id_destino THEN
        RAISE EXCEPTION 'El producto origen y destino no pueden ser el mismo';
    END IF;

    -- Bloquear ambas filas en orden fijo para evitar deadlock
    SELECT stock, nombre INTO v_stock_origen, v_nombre_origen
      FROM productos WHERE id_producto = LEAST(p_id_origen, p_id_destino) FOR UPDATE;

    SELECT stock, nombre INTO v_stock_destino, v_nombre_destino
      FROM productos WHERE id_producto = GREATEST(p_id_origen, p_id_destino) FOR UPDATE;

    -- Reasignar correctamente si el orden cambió
    IF LEAST(p_id_origen, p_id_destino) = p_id_destino THEN
        -- swap
        DECLARE
            tmp_stock INT;
            tmp_nombre VARCHAR(150);
        BEGIN
            tmp_stock  := v_stock_origen;  tmp_nombre  := v_nombre_origen;
            v_stock_origen  := v_stock_destino; v_nombre_origen  := v_nombre_destino;
            v_stock_destino := tmp_stock;       v_nombre_destino := tmp_nombre;
        END;
    END IF;

    IF v_stock_origen < p_cantidad THEN
        -- ROLLBACK al savepoint: deshace cualquier cambio parcial
        ROLLBACK TO SAVEPOINT sp_transferencia;
        RAISE EXCEPTION 'Stock insuficiente en "%": disponible %, solicitado %',
                        v_nombre_origen, v_stock_origen, p_cantidad;
    END IF;

    -- Descontar origen
    UPDATE productos SET stock = stock - p_cantidad WHERE id_producto = p_id_origen;
    -- Sumar destino
    UPDATE productos SET stock = stock + p_cantidad WHERE id_producto = p_id_destino;

    RELEASE SAVEPOINT sp_transferencia;

    p_mensaje := 'Transferencia exitosa: ' || p_cantidad || ' unidades de "'
                 || v_nombre_origen || '" → "' || v_nombre_destino || '"';

EXCEPTION
    WHEN OTHERS THEN
        p_mensaje := 'ERROR en transferencia: ' || SQLERRM;
        RAISE;
END;
$$;