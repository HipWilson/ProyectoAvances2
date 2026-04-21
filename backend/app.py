import os
import csv
import io
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, Response)
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='../frontend/templates',
            static_folder='../frontend/static')
app.secret_key = os.environ.get('SECRET_KEY', 'clave-super-secreta-cambiar')

# ──────────────────────────────────────────────
# Conexión a la base de datos
# ──────────────────────────────────────────────
def get_db():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'db'),
        port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ.get('DB_NAME', 'tiendadb'),
        user=os.environ.get('DB_USER', 'proy2'),
        password=os.environ.get('DB_PASSWORD', 'secret')
    )

# ──────────────────────────────────────────────
# Decorador de autenticación
# ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ──────────────────────────────────────────────
# Crear admin por defecto al arrancar
# ──────────────────────────────────────────────
def init_admin():
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT id_usuario FROM usuarios WHERE username = 'admin'")
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO usuarios (username, password_hash, rol) VALUES (%s, %s, %s)",
                ('admin', generate_password_hash('admin123'), 'admin')
            )
            conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error creando admin: {e}")

# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM usuarios WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id_usuario']
            session['username'] = user['username']
            session['rol']      = user['rol']
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # KPIs simples
    cur.execute("SELECT COUNT(*) AS total FROM ventas")
    total_ventas = cur.fetchone()['total']

    cur.execute("SELECT COALESCE(SUM(total),0) AS suma FROM ventas")
    ingresos = cur.fetchone()['suma']

    cur.execute("SELECT COUNT(*) AS total FROM productos WHERE stock < 10")
    stock_bajo = cur.fetchone()['total']

    cur.execute("SELECT COUNT(*) AS total FROM clientes")
    total_clientes = cur.fetchone()['total']

    # ── JOIN 1: últimas 5 ventas con nombre de cliente y empleado ──
    cur.execute("""
        SELECT v.id_venta, v.fecha, v.total,
               c.nombre AS cliente, e.nombre AS empleado
        FROM ventas v
        JOIN clientes  c ON c.id_cliente  = v.id_cliente
        JOIN empleados e ON e.id_empleado = v.id_empleado
        ORDER BY v.fecha DESC
        LIMIT 5
    """)
    ultimas_ventas = cur.fetchall()

    cur.close(); conn.close()
    return render_template('dashboard.html',
                           total_ventas=total_ventas,
                           ingresos=ingresos,
                           stock_bajo=stock_bajo,
                           total_clientes=total_clientes,
                           ultimas_ventas=ultimas_ventas)

# ──────────────────────────────────────────────
# PRODUCTOS  (CRUD completo)
# ──────────────────────────────────────────────
@app.route('/productos')
@login_required
def productos():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # ── JOIN 2: productos con categoría y proveedor ──
    cur.execute("""
        SELECT p.*, c.nombre AS categoria, pr.nombre AS proveedor
        FROM productos p
        JOIN categorias  c  ON c.id_categoria = p.id_categoria
        JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor
        ORDER BY p.id_producto
    """)
    productos_list = cur.fetchall()
    cur.execute("SELECT * FROM categorias ORDER BY nombre")
    categorias = cur.fetchall()
    cur.execute("SELECT * FROM proveedores ORDER BY nombre")
    proveedores = cur.fetchall()
    cur.close(); conn.close()
    return render_template('productos.html',
                           productos=productos_list,
                           categorias=categorias,
                           proveedores=proveedores)

@app.route('/productos/nuevo', methods=['POST'])
@login_required
def producto_nuevo():
    d = request.form
    if not d.get('nombre') or not d.get('precio') or not d.get('stock'):
        flash('Nombre, precio y stock son obligatorios', 'danger')
        return redirect(url_for('productos'))
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO productos (nombre, descripcion, precio, stock, id_categoria, id_proveedor)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (d['nombre'], d.get('descripcion'), float(d['precio']),
              int(d['stock']), int(d['id_categoria']), int(d['id_proveedor'])))
        conn.commit()
        flash('Producto creado correctamente', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('productos'))

@app.route('/productos/editar/<int:pid>', methods=['POST'])
@login_required
def producto_editar(pid):
    d = request.form
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE productos
            SET nombre=%s, descripcion=%s, precio=%s, stock=%s,
                id_categoria=%s, id_proveedor=%s
            WHERE id_producto=%s
        """, (d['nombre'], d.get('descripcion'), float(d['precio']),
              int(d['stock']), int(d['id_categoria']), int(d['id_proveedor']), pid))
        conn.commit()
        flash('Producto actualizado', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('productos'))

@app.route('/productos/eliminar/<int:pid>', methods=['POST'])
@login_required
def producto_eliminar(pid):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM productos WHERE id_producto=%s", (pid,))
        conn.commit()
        flash('Producto eliminado', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar (¿tiene ventas asociadas?): {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('productos'))

# ──────────────────────────────────────────────
# CLIENTES  (CRUD completo)
# ──────────────────────────────────────────────
@app.route('/clientes')
@login_required
def clientes():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # ── Subquery: clientes que han realizado al menos 1 venta ──
    cur.execute("""
        SELECT c.*,
               (SELECT COUNT(*) FROM ventas v WHERE v.id_cliente = c.id_cliente) AS num_compras,
               (SELECT COALESCE(SUM(v.total),0) FROM ventas v WHERE v.id_cliente = c.id_cliente) AS total_gastado
        FROM clientes c
        ORDER BY c.nombre
    """)
    clientes_list = cur.fetchall()
    cur.close(); conn.close()
    return render_template('clientes.html', clientes=clientes_list)

@app.route('/clientes/nuevo', methods=['POST'])
@login_required
def cliente_nuevo():
    d = request.form
    if not d.get('nombre'):
        flash('El nombre es obligatorio', 'danger')
        return redirect(url_for('clientes'))
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO clientes (nombre, email, telefono, direccion)
            VALUES (%s,%s,%s,%s)
        """, (d['nombre'], d.get('email'), d.get('telefono'), d.get('direccion')))
        conn.commit()
        flash('Cliente creado', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('clientes'))

@app.route('/clientes/editar/<int:cid>', methods=['POST'])
@login_required
def cliente_editar(cid):
    d = request.form
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE clientes SET nombre=%s, email=%s, telefono=%s, direccion=%s
            WHERE id_cliente=%s
        """, (d['nombre'], d.get('email'), d.get('telefono'), d.get('direccion'), cid))
        conn.commit()
        flash('Cliente actualizado', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('clientes'))

@app.route('/clientes/eliminar/<int:cid>', methods=['POST'])
@login_required
def cliente_eliminar(cid):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM clientes WHERE id_cliente=%s", (cid,))
        conn.commit()
        flash('Cliente eliminado', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error al eliminar (¿tiene ventas?): {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('clientes'))

# ──────────────────────────────────────────────
# VENTAS  (crear con transacción explícita)
# ──────────────────────────────────────────────
@app.route('/ventas')
@login_required
def ventas():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # ── JOIN 3: ventas con cliente, empleado y cantidad de items ──
    cur.execute("""
        SELECT v.id_venta, v.fecha, v.total,
               c.nombre  AS cliente,
               e.nombre  AS empleado,
               COUNT(dv.id_detalle) AS items
        FROM ventas v
        JOIN clientes  c  ON c.id_cliente  = v.id_cliente
        JOIN empleados e  ON e.id_empleado = v.id_empleado
        LEFT JOIN detalle_venta dv ON dv.id_venta = v.id_venta
        GROUP BY v.id_venta, v.fecha, v.total, c.nombre, e.nombre
        ORDER BY v.fecha DESC
    """)
    ventas_list = cur.fetchall()

    cur.execute("SELECT * FROM clientes  ORDER BY nombre")
    clientes    = cur.fetchall()
    cur.execute("SELECT * FROM empleados ORDER BY nombre")
    empleados   = cur.fetchall()
    # ── Subquery EXISTS: productos disponibles (stock > 0) ──
    cur.execute("""
        SELECT p.*, c.nombre AS categoria
        FROM productos p
        JOIN categorias c ON c.id_categoria = p.id_categoria
        WHERE EXISTS (SELECT 1 FROM productos p2
                      WHERE p2.id_producto = p.id_producto AND p2.stock > 0)
        ORDER BY p.nombre
    """)
    productos   = cur.fetchall()
    cur.close(); conn.close()
    return render_template('ventas.html',
                           ventas=ventas_list,
                           clientes=clientes,
                           empleados=empleados,
                           productos=productos)

@app.route('/ventas/nueva', methods=['POST'])
@login_required
def venta_nueva():
    """
    Crea una venta con TRANSACCIÓN EXPLÍCITA.
    Si algo falla (stock insuficiente, etc.) hace ROLLBACK completo.
    """
    id_cliente  = request.form.get('id_cliente')
    id_empleado = request.form.get('id_empleado')
    ids_prod    = request.form.getlist('producto_id[]')
    cantidades  = request.form.getlist('cantidad[]')

    if not id_cliente or not id_empleado or not ids_prod:
        flash('Faltan datos para registrar la venta', 'danger')
        return redirect(url_for('ventas'))

    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # ── BEGIN explícito ──
        conn.autocommit = False

        total = 0.0
        items = []
        for pid, qty in zip(ids_prod, cantidades):
            pid = int(pid); qty = int(qty)
            if qty <= 0:
                continue
            cur.execute("SELECT precio, stock, nombre FROM productos WHERE id_producto=%s FOR UPDATE", (pid,))
            prod = cur.fetchone()
            if not prod:
                raise ValueError(f'Producto {pid} no encontrado')
            if prod['stock'] < qty:
                raise ValueError(f'Stock insuficiente para "{prod["nombre"]}" '
                                 f'(disponible: {prod["stock"]}, pedido: {qty})')
            subtotal = round(prod['precio'] * qty, 2)
            total   += subtotal
            items.append((pid, qty, prod['precio'], subtotal))

        if not items:
            raise ValueError('No se seleccionó ningún producto válido')

        # Insertar cabecera de venta
        cur.execute("""
            INSERT INTO ventas (id_cliente, id_empleado, total)
            VALUES (%s,%s,%s) RETURNING id_venta
        """, (id_cliente, id_empleado, round(total, 2)))
        id_venta = cur.fetchone()['id_venta']

        for pid, qty, precio, subtotal in items:
            cur.execute("""
                INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (%s,%s,%s,%s,%s)
            """, (id_venta, pid, qty, precio, subtotal))
            cur.execute("UPDATE productos SET stock = stock - %s WHERE id_producto = %s",
                        (qty, pid))

        conn.commit()   # ── COMMIT ──
        flash(f'Venta #{id_venta} registrada por Q{total:.2f}', 'success')
    except Exception as e:
        conn.rollback()  # ── ROLLBACK ──
        flash(f'Error al registrar venta (se canceló): {e}', 'danger')
    finally:
        conn.autocommit = True
        cur.close(); conn.close()
    return redirect(url_for('ventas'))

# ──────────────────────────────────────────────
# REPORTES
# ──────────────────────────────────────────────
@app.route('/reportes')
@login_required
def reportes():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── VIEW: reporte de ventas por producto ──
    cur.execute("SELECT * FROM vista_reporte_ventas ORDER BY ingresos_totales DESC LIMIT 20")
    reporte_productos = cur.fetchall()

    # ── GROUP BY + HAVING + agregación: categorías con más de 1 venta ──
    cur.execute("""
        SELECT c.nombre AS categoria,
               COUNT(DISTINCT v.id_venta)  AS num_ventas,
               SUM(dv.subtotal)            AS total_ingresos,
               AVG(dv.subtotal)            AS promedio_por_item
        FROM detalle_venta dv
        JOIN productos  p ON p.id_producto  = dv.id_producto
        JOIN categorias c ON c.id_categoria = p.id_categoria
        JOIN ventas     v ON v.id_venta     = dv.id_venta
        GROUP BY c.nombre
        HAVING COUNT(DISTINCT v.id_venta) > 1
        ORDER BY total_ingresos DESC
    """)
    reporte_categorias = cur.fetchall()

    # ── CTE: top 5 clientes por gasto total ──
    cur.execute("""
        WITH gasto_clientes AS (
            SELECT c.id_cliente, c.nombre,
                   COUNT(v.id_venta)   AS num_compras,
                   SUM(v.total)        AS total_gastado
            FROM clientes c
            JOIN ventas v ON v.id_cliente = c.id_cliente
            GROUP BY c.id_cliente, c.nombre
        )
        SELECT *
        FROM gasto_clientes
        ORDER BY total_gastado DESC
        LIMIT 5
    """)
    top_clientes = cur.fetchall()

    cur.close(); conn.close()
    return render_template('reportes.html',
                           reporte_productos=reporte_productos,
                           reporte_categorias=reporte_categorias,
                           top_clientes=top_clientes)

@app.route('/reportes/exportar-csv')
@login_required
def exportar_csv():
    """Exporta el reporte de ventas por producto a CSV."""
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM vista_reporte_ventas ORDER BY ingresos_totales DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()

    output = io.StringIO()
    writer = csv.DictWriter(output,
                            fieldnames=['producto', 'categoria', 'unidades_vendidas',
                                        'ingresos_totales', 'num_ventas'])
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in writer.fieldnames})

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=reporte_ventas.csv'}
    )

# ──────────────────────────────────────────────
# EMPLEADOS (CRUD)
# ──────────────────────────────────────────────
@app.route('/empleados')
@login_required
def empleados():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM empleados ORDER BY nombre")
    emp = cur.fetchall()
    cur.close(); conn.close()
    return render_template('empleados.html', empleados=emp)

@app.route('/empleados/nuevo', methods=['POST'])
@login_required
def empleado_nuevo():
    d = request.form
    if not d.get('nombre'):
        flash('El nombre es obligatorio', 'danger')
        return redirect(url_for('empleados'))
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("INSERT INTO empleados (nombre, cargo, email, telefono) VALUES (%s,%s,%s,%s)",
                    (d['nombre'], d.get('cargo'), d.get('email'), d.get('telefono')))
        conn.commit()
        flash('Empleado creado', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('empleados'))

@app.route('/empleados/editar/<int:eid>', methods=['POST'])
@login_required
def empleado_editar(eid):
    d = request.form
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("UPDATE empleados SET nombre=%s,cargo=%s,email=%s,telefono=%s WHERE id_empleado=%s",
                    (d['nombre'],d.get('cargo'),d.get('email'),d.get('telefono'),eid))
        conn.commit()
        flash('Empleado actualizado','success')
    except Exception as e:
        conn.rollback(); flash(f'Error:{e}','danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('empleados'))

@app.route('/empleados/eliminar/<int:eid>', methods=['POST'])
@login_required
def empleado_eliminar(eid):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM empleados WHERE id_empleado=%s",(eid,))
        conn.commit()
        flash('Empleado eliminado','success')
    except Exception as e:
        conn.rollback(); flash(f'Error (¿tiene ventas?):{e}','danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('empleados'))

# ──────────────────────────────────────────────
if __name__ == '__main__':
    init_admin()
    app.run(host='0.0.0.0', port=5000, debug=True)