CREATE TABLE IF NOT EXISTS ubicacion (
    id INTEGER PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    direccion TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('CD', 'LOCAL'))
);
CREATE UNIQUE INDEX IF NOT EXISTS unico_cd ON ubicacion(tipo) WHERE tipo = 'CD';
CREATE TABLE IF NOT EXISTS categoria (
    id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS proveedor (
    id INTEGER PRIMARY KEY, codigo TEXT NOT NULL UNIQUE, nombre TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS producto (
    id INTEGER PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    categoria_id INTEGER NOT NULL REFERENCES categoria(id),
    precio_centavos INTEGER NOT NULL CHECK (precio_centavos >= 0)
);
CREATE TABLE IF NOT EXISTS existencia (
    ubicacion_id INTEGER NOT NULL REFERENCES ubicacion(id),
    producto_id INTEGER NOT NULL REFERENCES producto(id),
    disponible INTEGER NOT NULL DEFAULT 0 CHECK (disponible >= 0),
    reservado INTEGER NOT NULL DEFAULT 0 CHECK (reservado >= 0),
    pendiente INTEGER NOT NULL DEFAULT 0 CHECK (pendiente >= 0),
    rechazado INTEGER NOT NULL DEFAULT 0 CHECK (rechazado >= 0),
    minimo INTEGER NOT NULL DEFAULT 0 CHECK (minimo >= 0),
    costo_centavos INTEGER NOT NULL DEFAULT 0 CHECK (costo_centavos >= 0),
    PRIMARY KEY (ubicacion_id, producto_id)
);
CREATE TABLE IF NOT EXISTS compra (
    id INTEGER PRIMARY KEY,
    referencia TEXT NOT NULL UNIQUE,
    proveedor_id INTEGER NOT NULL REFERENCES proveedor(id),
    cd_id INTEGER NOT NULL REFERENCES ubicacion(id),
    fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS detalle_compra (
    compra_id INTEGER NOT NULL REFERENCES compra(id),
    producto_id INTEGER NOT NULL REFERENCES producto(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    costo_centavos INTEGER NOT NULL CHECK (costo_centavos >= 0),
    PRIMARY KEY (compra_id, producto_id)
);
CREATE TABLE IF NOT EXISTS orden_reposicion (
    id INTEGER PRIMARY KEY,
    cd_id INTEGER NOT NULL REFERENCES ubicacion(id),
    local_id INTEGER NOT NULL REFERENCES ubicacion(id),
    fecha TEXT NOT NULL,
    CHECK (cd_id <> local_id)
);
CREATE TABLE IF NOT EXISTS detalle_reposicion (
    orden_id INTEGER NOT NULL REFERENCES orden_reposicion(id),
    producto_id INTEGER NOT NULL REFERENCES producto(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (orden_id, producto_id)
);
CREATE TABLE IF NOT EXISTS remito (
    id INTEGER PRIMARY KEY,
    numero TEXT NOT NULL UNIQUE,
    orden_id INTEGER NOT NULL REFERENCES orden_reposicion(id),
    estado TEXT NOT NULL DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Verificado', 'Rechazado'))
);
CREATE TABLE IF NOT EXISTS bulto (
    id INTEGER PRIMARY KEY,
    remito_id INTEGER NOT NULL UNIQUE REFERENCES remito(id),
    precinto TEXT UNIQUE,
    estado TEXT NOT NULL CHECK (estado IN ('Preparado', 'Precintado', 'En tránsito', 'Recibido', 'Verificado', 'Rechazado'))
);
CREATE TABLE IF NOT EXISTS contenido_bulto (
    bulto_id INTEGER NOT NULL REFERENCES bulto(id),
    producto_id INTEGER NOT NULL REFERENCES producto(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    costo_centavos INTEGER NOT NULL DEFAULT 0 CHECK (costo_centavos >= 0),
    PRIMARY KEY (bulto_id, producto_id)
);
CREATE TABLE IF NOT EXISTS historial_bulto (
    id INTEGER PRIMARY KEY,
    bulto_id INTEGER NOT NULL REFERENCES bulto(id),
    anterior TEXT,
    nuevo TEXT NOT NULL,
    fecha TEXT NOT NULL,
    observacion TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS historial_no_modificar BEFORE UPDATE ON historial_bulto
BEGIN SELECT RAISE(ABORT, 'El historial es inmutable'); END;
CREATE TRIGGER IF NOT EXISTS historial_no_borrar BEFORE DELETE ON historial_bulto
BEGIN SELECT RAISE(ABORT, 'El historial es inmutable'); END;
CREATE TABLE IF NOT EXISTS movimiento_inventario (
    id INTEGER PRIMARY KEY,
    ubicacion_id INTEGER NOT NULL REFERENCES ubicacion(id),
    producto_id INTEGER NOT NULL REFERENCES producto(id),
    disponible INTEGER NOT NULL,
    reservado INTEGER NOT NULL,
    pendiente INTEGER NOT NULL,
    rechazado INTEGER NOT NULL,
    causa TEXT NOT NULL,
    referencia_id INTEGER NOT NULL,
    fecha TEXT NOT NULL,
    UNIQUE (ubicacion_id, producto_id, causa, referencia_id)
);
CREATE TABLE IF NOT EXISTS venta (
    id INTEGER PRIMARY KEY,
    local_id INTEGER NOT NULL REFERENCES ubicacion(id),
    fecha TEXT NOT NULL,
    total_centavos INTEGER NOT NULL CHECK (total_centavos >= 0)
);
CREATE TABLE IF NOT EXISTS detalle_venta (
    id INTEGER PRIMARY KEY,
    venta_id INTEGER NOT NULL REFERENCES venta(id),
    producto_id INTEGER NOT NULL REFERENCES producto(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario_centavos INTEGER NOT NULL CHECK (precio_unitario_centavos >= 0),
    costo_unitario_centavos INTEGER NOT NULL CHECK (costo_unitario_centavos >= 0),
    UNIQUE (venta_id, producto_id)
);
CREATE TABLE IF NOT EXISTS cobro (
    id INTEGER PRIMARY KEY,
    venta_id INTEGER NOT NULL REFERENCES venta(id),
    medio_pago TEXT NOT NULL,
    importe_centavos INTEGER NOT NULL CHECK (importe_centavos > 0),
    fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comprobante (
    id INTEGER PRIMARY KEY,
    numero TEXT NOT NULL UNIQUE,
    venta_id INTEGER NOT NULL UNIQUE REFERENCES venta(id),
    fecha TEXT NOT NULL,
    total_centavos INTEGER NOT NULL CHECK (total_centavos >= 0)
);
CREATE TABLE IF NOT EXISTS movimiento_caja (
    id INTEGER PRIMARY KEY,
    local_id INTEGER NOT NULL REFERENCES ubicacion(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('INGRESO', 'EGRESO')),
    medio_pago TEXT NOT NULL,
    importe_centavos INTEGER NOT NULL CHECK (importe_centavos > 0),
    causa TEXT NOT NULL,
    referencia_id INTEGER NOT NULL,
    fecha TEXT NOT NULL
);
