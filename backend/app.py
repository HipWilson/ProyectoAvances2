import os
import csv
import io
import json
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, Response)
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
from models import db, Categoria, Proveedor, Producto, Empleado, Cliente, Usuario, Venta, DetalleVenta

# ──────────────────────────────────────────────
# App & ORM setup
# ──────────────────────────────────────────────
app = Flask(__name__, template_folder='../frontend/templates',
            static_folder='../frontend/static')

app.secret_key = os.environ.get('SECRET_KEY', 'clave-super-secreta-cambiar')

DB_HOST = os.environ.get('DB_HOST', 'db')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'tiendadb')
DB_USER = os.environ.get('DB_USER', 'proy3')
DB_PASS = os.environ.get('DB_PASSWORD', 'secret')

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ──────────────────────────────────────────────
# Conexión raw psycopg2 (para stored procedures)
# ──────────────────────────────────────────────
def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )

# ──────────────────────────────────────────────
# Permisos por rol
# ──────────────────────────────────────────────
# Define qué rutas (endpoints) puede acceder cada rol
ROL_PERMISOS = {
    'admin': {
        'dashboard', 'productos', 'producto_nuevo', 'producto_editar', 'producto_eliminar',
        'clientes', 'cliente_nuevo', 'cliente_editar', 'cliente_eliminar',
        'empleados', 'empleado_nuevo', 'empleado_editar', 'empleado_eliminar',
        'ventas', 'venta_nueva',
        'reportes', 'exportar_csv',
        'inventario', 'ajustar_stock', 'transferir_stock',
    },
    'supervisor': {
        'dashboard',
        'productos', 'producto_nuevo', 'producto_editar',
        'clientes', 'cliente_nuevo', 'cliente_editar',
        'empleados', 'empleado_nuevo', 'empleado_editar',
        'ventas',
        'reportes', 'exportar_csv',
        'inventario', 'ajustar_stock', 'transferir_stock',
    },
    'vendedor': {
        'dashboard',
        'productos',
        'clientes', 'cliente_nuevo', 'cliente_editar',
        'ventas', 'venta_nueva',
    },
    'bodeguero': {
        'dashboard',
        'productos',
        'inventario', 'ajustar_stock', 'transferir_stock',
        'ventas',
    },
    'reportes': {
        'dashboard',
        'reportes', 'exportar_csv',
        'productos',
        'clientes',
        'ventas',
    },
}

# ──────────────────────────────────────────────
# Decoradores
# ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def rol_required(*roles_permitidos):
    """Permite acceso solo a los roles especificados."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            rol_actual = session.get('rol', '')
            if rol_actual not in roles_permitidos:
                flash(f'Acceso denegado: tu rol ({rol_actual}) no tiene permiso para esta acción.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

def puede_acceder(endpoint):
    """Verifica si el usuario en sesión puede acceder al endpoint dado."""
    rol = session.get('rol', '')
    return endpoint in ROL_PERMISOS.get(rol, set())

# Hacer disponible en templates
app.jinja_env.globals['puede_acceder'] = puede_acceder

# ──────────────────────────────────────────────
# Inicializar usuarios de prueba con hashes reales
# ──────────────────────────────────────────────
def init_usuarios():
    """Crea/actualiza los usuarios de prueba con contraseñas hasheadas reales."""
    usuarios_prueba = [
        ('admin',             'admin123',   'admin'),
        ('admin_usuario',     'secret123',  'admin'),
        ('supervisor_usuario','secret123',  'supervisor'),
        ('vendedor_usuario',  'secret123',  'vendedor'),
        ('bodeguero_usuario', 'secret123',  'bodeguero'),
        ('reportes_usuario',  'secret123',  'reportes'),
    ]
    try:
        with app.app_context():
            for username, password, rol in usuarios_prueba:
                u = Usuario.query.filter_by(username=username).first()
                if not u:
                    nuevo = Usuario(
                        username=username,
                        password_hash=generate_password_hash(password),
                        rol=rol
                    )
                    db.session.add(nuevo)
                else:
                    # Actualizar hash si el guardado en seed es placeholder
                    if not u.password_hash.startswith('scrypt') and not u.password_hash.startswith('pbkdf2'):
                        u.password_hash = generate_password_hash(password)
            db.session.commit()
            print('Usuarios de prueba inicializados correctamente.')
    except Exception as e:
        print(f'Error inicializando usuarios: {e}')

# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # ORM - CRUD operación 1: READ usuario
        u = Usuario.query.filter_by(username=username).first()
        if u and check_password_hash(u.password_hash, password):
            session['user_id']  = u.id_usuario
            session['username'] = u.username
            session['rol']      = u.rol
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
    cur.execute("SELECT COUNT(*) AS total FROM ventas")
    total_ventas = cur.fetchone()['total']
    cur.execute("SELECT COALESCE(SUM(total),0) AS suma FROM ventas")
    ingresos = cur.fetchone()['suma']
    cur.execute("SELECT COUNT(*) AS total FROM productos WHERE stock < 10")
    stock_bajo = cur.fetchone()['total']
    cur.execute("SELECT COUNT(*) AS total FROM clientes")
    total_clientes = cur.fetchone()['total']
    cur.execute("""
        SELECT v.id_venta, v.fecha, v.total,
               c.nombre AS cliente, e.nombre AS empleado
        FROM ventas v
        JOIN clientes  c ON c.id_cliente  = v.id_cliente
        JOIN empleados e ON e.id_empleado = v.id_empleado
        ORDER BY v.fecha DESC LIMIT 5
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
# PRODUCTOS  (ORM para CREATE, UPDATE, DELETE)
# ──────────────────────────────────────────────
@app.route('/productos')
@login_required
def productos():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT p.*, c.nombre AS categoria, pr.nombre AS proveedor
        FROM productos p
        JOIN categorias  c  ON c.id_categoria = p.id_categoria
        JOIN proveedores pr ON pr.id_proveedor = p.id_proveedor
        ORDER BY p.id_producto
    """)
    productos_list = cur.fetchall()
    cur.close(); conn.close()
    # ORM - CRUD operación 2: READ categorias y proveedores
    categorias  = Categoria.query.order_by(Categoria.nombre).all()
    proveedores = Proveedor.query.order_by(Proveedor.nombre).all()
    return render_template('productos.html',
                           productos=productos_list,
                           categorias=categorias,
                           proveedores=proveedores)

@app.route('/productos/nuevo', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor')
def producto_nuevo():
    d = request.form
    if not d.get('nombre') or not d.get('precio') or not d.get('stock'):
        flash('Nombre, precio y stock son obligatorios', 'danger')
        return redirect(url_for('productos'))
    # Usar stored procedure sp_crear_producto
    conn = get_db()
    conn.autocommit = False
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("BEGIN")
        cur.execute(
            "SELECT * FROM sp_crear_producto(%s,%s,%s,%s,%s,%s)",
            (d['nombre'], d.get('descripcion'), float(d['precio']),
             int(d['stock']), int(d['id_categoria']), int(d['id_proveedor']))
        )
        result = cur.fetchone()
        conn.commit()
        flash(result['p_mensaje'], 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('productos'))

@app.route('/productos/editar/<int:pid>', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor')
def producto_editar(pid):
    d = request.form
    # ORM - CRUD operación 3: UPDATE producto
    try:
        p = Producto.query.get_or_404(pid)
        p.nombre       = d['nombre']
        p.descripcion  = d.get('descripcion')
        p.precio       = float(d['precio'])
        p.stock        = int(d['stock'])
        p.id_categoria = int(d['id_categoria'])
        p.id_proveedor = int(d['id_proveedor'])
        db.session.commit()
        flash('Producto actualizado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('productos'))

@app.route('/productos/eliminar/<int:pid>', methods=['POST'])
@login_required
@rol_required('admin')
def producto_eliminar(pid):
    # ORM - CRUD operación 4: DELETE producto
    try:
        p = Producto.query.get_or_404(pid)
        db.session.delete(p)
        db.session.commit()
        flash('Producto eliminado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar (¿tiene ventas asociadas?): {e}', 'danger')
    return redirect(url_for('productos'))

# ──────────────────────────────────────────────
# CLIENTES  (ORM para CREATE y UPDATE)
# ──────────────────────────────────────────────
@app.route('/clientes')
@login_required
@rol_required('admin', 'supervisor', 'vendedor', 'reportes')
def clientes():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT c.*,
               (SELECT COUNT(*) FROM ventas v WHERE v.id_cliente = c.id_cliente) AS num_compras,
               (SELECT COALESCE(SUM(v.total),0) FROM ventas v WHERE v.id_cliente = c.id_cliente) AS total_gastado
        FROM clientes c ORDER BY c.nombre
    """)
    clientes_list = cur.fetchall()
    cur.close(); conn.close()
    return render_template('clientes.html', clientes=clientes_list)

@app.route('/clientes/nuevo', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor', 'vendedor')
def cliente_nuevo():
    d = request.form
    if not d.get('nombre'):
        flash('El nombre es obligatorio', 'danger')
        return redirect(url_for('clientes'))
    # ORM - CRUD operación 5: CREATE cliente
    try:
        c = Cliente(nombre=d['nombre'], email=d.get('email'),
                    telefono=d.get('telefono'), direccion=d.get('direccion'))
        db.session.add(c)
        db.session.commit()
        flash('Cliente creado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('clientes'))

@app.route('/clientes/editar/<int:cid>', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor', 'vendedor')
def cliente_editar(cid):
    d = request.form
    # ORM - CRUD operación 6: UPDATE cliente
    try:
        c = Cliente.query.get_or_404(cid)
        c.nombre    = d['nombre']
        c.email     = d.get('email')
        c.telefono  = d.get('telefono')
        c.direccion = d.get('direccion')
        db.session.commit()
        flash('Cliente actualizado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('clientes'))

@app.route('/clientes/eliminar/<int:cid>', methods=['POST'])
@login_required
@rol_required('admin')
def cliente_eliminar(cid):
    # Usar stored procedure sp_eliminar_cliente (con validación de ventas)
    conn = get_db()
    conn.autocommit = False
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("BEGIN")
        cur.execute("SELECT * FROM sp_eliminar_cliente(%s)", (cid,))
        result = cur.fetchone()
        conn.commit()
        flash(result['p_mensaje'], 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error: {e}', 'danger')
    finally:
        cur.close(); conn.close()
    return redirect(url_for('clientes'))

# ──────────────────────────────────────────────
# VENTAS (stored procedure sp_registrar_venta)
# ──────────────────────────────────────────────
@app.route('/ventas')
@login_required
@rol_required('admin', 'supervisor', 'vendedor', 'bodeguero', 'reportes')
def ventas():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT v.id_venta, v.fecha, v.total,
               c.nombre AS cliente, e.nombre AS empleado,
               COUNT(dv.id_detalle) AS items
        FROM ventas v
        JOIN clientes  c  ON c.id_cliente  = v.id_cliente
        JOIN empleados e  ON e.id_empleado = v.id_empleado
        LEFT JOIN detalle_venta dv ON dv.id_venta = v.id_venta
        GROUP BY v.id_venta, v.fecha, v.total, c.nombre, e.nombre
        ORDER BY v.fecha DESC
    """)
    ventas_list = cur.fetchall()
    cur.close(); conn.close()
    # ORM para listas de selección
    clientes_list  = Cliente.query.order_by(Cliente.nombre).all()
    empleados_list = Empleado.query.order_by(Empleado.nombre).all()
    productos_list = Producto.query.filter(Producto.stock > 0).order_by(Producto.nombre).all()
    return render_template('ventas.html',
                           ventas=ventas_list,
                           clientes=clientes_list,
                           empleados=empleados_list,
                           productos=productos_list)

@app.route('/ventas/nueva', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor', 'vendedor')
def venta_nueva():
    """Registra venta llamando al stored procedure sp_registrar_venta con transacción explícita."""
    id_cliente  = request.form.get('id_cliente')
    id_empleado = request.form.get('id_empleado')
    ids_prod    = request.form.getlist('producto_id[]')
    cantidades  = request.form.getlist('cantidad[]')

    if not id_cliente or not id_empleado or not ids_prod:
        flash('Faltan datos para registrar la venta', 'danger')
        return redirect(url_for('ventas'))

    # Construir JSON de items para el SP
    items = []
    for pid, qty in zip(ids_prod, cantidades):
        try:
            qty_int = int(qty)
            if qty_int > 0:
                items.append({'id_producto': int(pid), 'cantidad': qty_int})
        except ValueError:
            pass

    if not items:
        flash('No se seleccionó ningún producto válido', 'danger')
        return redirect(url_for('ventas'))

    conn = get_db()
    conn.autocommit = False
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("BEGIN")   # ── BEGIN EXPLÍCITO ──
        cur.execute(
            "SELECT * FROM sp_registrar_venta(%s, %s, %s)",
            (int(id_cliente), int(id_empleado), json.dumps(items))
        )
        result = cur.fetchone()
        conn.commit()          # ── COMMIT ──
        flash(result['p_mensaje'], 'success')
    except Exception as e:
        conn.rollback()        # ── ROLLBACK ──
        msg = str(e)
        if 'ERROR:' in msg:
            msg = msg.split('ERROR:')[-1].strip()
        flash(f'Error al registrar venta (se canceló): {msg}', 'danger')
    finally:
        conn.autocommit = True
        cur.close(); conn.close()
    return redirect(url_for('ventas'))

# ──────────────────────────────────────────────
# INVENTARIO (solo bodeguero y admin/supervisor)
# ──────────────────────────────────────────────
@app.route('/inventario')
@login_required
@rol_required('admin', 'supervisor', 'bodeguero')
def inventario():
    # ORM - CRUD operación 7: READ productos para inventario
    productos_list = Producto.query.join(Categoria).join(Proveedor)\
        .order_by(Producto.nombre).all()
    return render_template('inventario.html', productos=productos_list)

@app.route('/inventario/ajustar', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor', 'bodeguero')
def ajustar_stock():
    """Ajusta stock llamando al stored procedure sp_ajustar_stock."""
    id_producto = request.form.get('id_producto')
    cantidad    = request.form.get('cantidad')
    motivo      = request.form.get('motivo', 'Ajuste manual')

    conn = get_db()
    conn.autocommit = False
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("BEGIN")
        cur.execute(
            "SELECT * FROM sp_ajustar_stock(%s, %s, %s)",
            (int(id_producto), int(cantidad), motivo)
        )
        result = cur.fetchone()
        conn.commit()
        flash(result['p_mensaje'], 'success')
    except Exception as e:
        conn.rollback()
        msg = str(e).split('ERROR:')[-1].strip()
        flash(f'Error al ajustar stock: {msg}', 'danger')
    finally:
        conn.autocommit = True
        cur.close(); conn.close()
    return redirect(url_for('inventario'))

@app.route('/inventario/transferir', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor', 'bodeguero')
def transferir_stock():
    """Transfiere stock entre productos usando sp_transferir_stock (con ROLLBACK)."""
    id_origen  = request.form.get('id_origen')
    id_destino = request.form.get('id_destino')
    cantidad   = request.form.get('cantidad')

    conn = get_db()
    conn.autocommit = False
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("BEGIN")
        cur.execute(
            "SELECT sp_transferir_stock(%s, %s, %s) AS p_mensaje",
            (int(id_origen), int(id_destino), int(cantidad))
        )
        result = cur.fetchone()
        conn.commit()
        flash(result['p_mensaje'], 'success')
    except Exception as e:
        conn.rollback()
        msg = str(e).split('ERROR:')[-1].strip()
        flash(f'Error en transferencia (se canceló): {msg}', 'danger')
    finally:
        conn.autocommit = True
        cur.close(); conn.close()
    return redirect(url_for('inventario'))

# ──────────────────────────────────────────────
# EMPLEADOS (ORM para todos los CRUD)
# ──────────────────────────────────────────────
@app.route('/empleados')
@login_required
@rol_required('admin', 'supervisor')
def empleados():
    # ORM - CRUD operación 8: READ empleados
    emp = Empleado.query.order_by(Empleado.nombre).all()
    return render_template('empleados.html', empleados=emp)

@app.route('/empleados/nuevo', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor')
def empleado_nuevo():
    d = request.form
    if not d.get('nombre'):
        flash('El nombre es obligatorio', 'danger')
        return redirect(url_for('empleados'))
    # ORM - CRUD operación 9: CREATE empleado
    try:
        e = Empleado(nombre=d['nombre'], cargo=d.get('cargo'),
                     email=d.get('email'), telefono=d.get('telefono'))
        db.session.add(e)
        db.session.commit()
        flash('Empleado creado', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('empleados'))

@app.route('/empleados/editar/<int:eid>', methods=['POST'])
@login_required
@rol_required('admin', 'supervisor')
def empleado_editar(eid):
    d = request.form
    # ORM - CRUD operación 10: UPDATE empleado
    try:
        e = Empleado.query.get_or_404(eid)
        e.nombre   = d['nombre']
        e.cargo    = d.get('cargo')
        e.email    = d.get('email')
        e.telefono = d.get('telefono')
        db.session.commit()
        flash('Empleado actualizado', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'Error: {ex}', 'danger')
    return redirect(url_for('empleados'))

@app.route('/empleados/eliminar/<int:eid>', methods=['POST'])
@login_required
@rol_required('admin')
def empleado_eliminar(eid):
    # ORM - CRUD operación 11: DELETE empleado
    try:
        e = Empleado.query.get_or_404(eid)
        db.session.delete(e)
        db.session.commit()
        flash('Empleado eliminado', 'success')
    except Exception as ex:
        db.session.rollback()
        flash(f'Error (¿tiene ventas?): {ex}', 'danger')
    return redirect(url_for('empleados'))

# ──────────────────────────────────────────────
# REPORTES
# ──────────────────────────────────────────────
@app.route('/reportes')
@login_required
@rol_required('admin', 'supervisor', 'reportes')
def reportes():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("SELECT * FROM vista_reporte_ventas ORDER BY ingresos_totales DESC LIMIT 20")
    reporte_productos = cur.fetchall()

    cur.execute("""
        SELECT c.nombre AS categoria,
               COUNT(DISTINCT v.id_venta) AS num_ventas,
               SUM(dv.subtotal) AS total_ingresos,
               AVG(dv.subtotal) AS promedio_por_item
        FROM detalle_venta dv
        JOIN productos  p ON p.id_producto  = dv.id_producto
        JOIN categorias c ON c.id_categoria = p.id_categoria
        JOIN ventas     v ON v.id_venta     = dv.id_venta
        GROUP BY c.nombre
        HAVING COUNT(DISTINCT v.id_venta) > 1
        ORDER BY total_ingresos DESC
    """)
    reporte_categorias = cur.fetchall()

    cur.execute("""
        WITH gasto_clientes AS (
            SELECT c.id_cliente, c.nombre,
                   COUNT(v.id_venta) AS num_compras,
                   SUM(v.total)      AS total_gastado
            FROM clientes c
            JOIN ventas v ON v.id_cliente = c.id_cliente
            GROUP BY c.id_cliente, c.nombre
        )
        SELECT * FROM gasto_clientes ORDER BY total_gastado DESC LIMIT 5
    """)
    top_clientes = cur.fetchall()

    # Llamar al stored procedure sp_reporte_ventas_periodo
    cur.execute(
        "SELECT * FROM sp_reporte_ventas_periodo(%s, %s)",
        ('2026-01-01 00:00:00', '2026-12-31 23:59:59')
    )
    resumen_sp = cur.fetchone()

    cur.close(); conn.close()
    return render_template('reportes.html',
                           reporte_productos=reporte_productos,
                           reporte_categorias=reporte_categorias,
                           top_clientes=top_clientes,
                           resumen_sp=resumen_sp)

@app.route('/reportes/exportar-csv')
@login_required
@rol_required('admin', 'supervisor', 'reportes')
def exportar_csv():
    conn = get_db()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM vista_reporte_ventas ORDER BY ingresos_totales DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['producto', 'categoria',
                            'unidades_vendidas', 'ingresos_totales', 'num_ventas'])
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in writer.fieldnames})
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=reporte_ventas.csv'})

# ──────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        init_usuarios()
    app.run(host='0.0.0.0', port=5000, debug=True)