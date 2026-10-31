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
CREATE TABLE IF NOT EXISTS devolucion (
    id INTEGER PRIMARY KEY,
    referencia TEXT NOT NULL UNIQUE,
    venta_id INTEGER NOT NULL REFERENCES venta(id),
    local_id INTEGER NOT NULL REFERENCES ubicacion(id),
    motivo TEXT NOT NULL,
    medio_reintegro TEXT NOT NULL,
    fecha TEXT NOT NULL,
    total_centavos INTEGER NOT NULL CHECK (total_centavos >= 0)
);
CREATE TABLE IF NOT EXISTS detalle_devolucion (
    id INTEGER PRIMARY KEY,
    devolucion_id INTEGER NOT NULL REFERENCES devolucion(id),
    detalle_venta_id INTEGER NOT NULL REFERENCES detalle_venta(id),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    condicion TEXT NOT NULL CHECK (condicion IN ('VENDIBLE', 'NO_VENDIBLE')),
    UNIQUE (devolucion_id, detalle_venta_id, condicion)
);
CREATE INDEX IF NOT EXISTS devolucion_por_detalle ON detalle_devolucion(detalle_venta_id);
CREATE TRIGGER IF NOT EXISTS validar_detalle_devolucion BEFORE INSERT ON detalle_devolucion
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM devolucion d JOIN venta v ON v.id = d.venta_id
        JOIN detalle_venta dv ON dv.venta_id = v.id
        WHERE d.id = NEW.devolucion_id AND dv.id = NEW.detalle_venta_id AND d.local_id = v.local_id
    ) THEN RAISE(ABORT, 'El detalle no pertenece a la venta y local de la devolución') END;
    SELECT CASE WHEN NEW.cantidad + COALESCE((
        SELECT SUM(cantidad) FROM detalle_devolucion WHERE detalle_venta_id = NEW.detalle_venta_id
    ), 0) > (SELECT cantidad FROM detalle_venta WHERE id = NEW.detalle_venta_id)
    THEN RAISE(ABORT, 'La devolución supera la cantidad vendida') END;
END;
