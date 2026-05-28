# ============================================================
# PROYECTO 3 - Modelos ORM (SQLAlchemy)
# ============================================================
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Categoria(db.Model):
    __tablename__ = 'categorias'
    id_categoria = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(100), nullable=False)
    descripcion  = db.Column(db.Text)
    productos    = db.relationship('Producto', backref='categoria_obj', lazy=True)

class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    id_proveedor = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(150), nullable=False)
    telefono     = db.Column(db.String(20))
    email        = db.Column(db.String(100))
    direccion    = db.Column(db.Text)
    productos    = db.relationship('Producto', backref='proveedor_obj', lazy=True)

class Producto(db.Model):
    __tablename__ = 'productos'
    id_producto  = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(150), nullable=False)
    descripcion  = db.Column(db.Text)
    precio       = db.Column(db.Numeric(10, 2), nullable=False)
    stock        = db.Column(db.Integer, nullable=False, default=0)
    id_categoria = db.Column(db.Integer, db.ForeignKey('categorias.id_categoria'), nullable=False)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('proveedores.id_proveedor'), nullable=False)

class Empleado(db.Model):
    __tablename__ = 'empleados'
    id_empleado = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(150), nullable=False)
    cargo       = db.Column(db.String(100))
    email       = db.Column(db.String(100))
    telefono    = db.Column(db.String(20))

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id_cliente = db.Column(db.Integer, primary_key=True)
    nombre     = db.Column(db.String(150), nullable=False)
    email      = db.Column(db.String(100))
    telefono   = db.Column(db.String(20))
    direccion  = db.Column(db.Text)
    ventas     = db.relationship('Venta', backref='cliente_obj', lazy=True)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id_usuario    = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    rol           = db.Column(db.String(20), nullable=False, default='vendedor')

class Venta(db.Model):
    __tablename__ = 'ventas'
    id_venta    = db.Column(db.Integer, primary_key=True)
    fecha       = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    id_cliente  = db.Column(db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False)
    id_empleado = db.Column(db.Integer, db.ForeignKey('empleados.id_empleado'), nullable=False)
    total       = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    detalles    = db.relationship('DetalleVenta', backref='venta_obj', lazy=True)
    empleado    = db.relationship('Empleado', backref='ventas_obj', lazy=True)

class DetalleVenta(db.Model):
    __tablename__ = 'detalle_venta'
    id_detalle      = db.Column(db.Integer, primary_key=True)
    id_venta        = db.Column(db.Integer, db.ForeignKey('ventas.id_venta'), nullable=False)
    id_producto     = db.Column(db.Integer, db.ForeignKey('productos.id_producto'), nullable=False)
    cantidad        = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal        = db.Column(db.Numeric(10, 2), nullable=False)
    producto        = db.relationship('Producto', backref='detalles', lazy=True)