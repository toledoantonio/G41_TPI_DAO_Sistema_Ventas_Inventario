"""Datos de demostración explícitos; nunca se precargan en una base con datos."""


def cargar_demo(sistema):
    if sistema.listar("ubicaciones") or sistema.listar("productos"):
        return False
    cd = sistema.guardar_ubicacion("CD", "Centro de Distribución", "Depósito central", "CD")
    local = sistema.guardar_ubicacion("L01", "Local Centro", "Sucursal Centro", "LOCAL")
    categoria = sistema.guardar_categoria("Almacén")
    proveedor = sistema.guardar_proveedor("PR01", "Proveedor de demostración")
    producto = sistema.guardar_producto("P01", "Producto de demostración", categoria, "100.00")
    sistema.configurar_minimo(local, producto, 5)
    sistema.registrar_compra("COMPRA-DEMO-01", proveedor, cd, [(producto, 20, "60.00")])
    orden = sistema.crear_orden(cd, local, [(producto, 10)])
    bulto = sistema.preparar_bulto(orden, "REMITO-DEMO-01", [(producto, 10)])
    sistema.precintar(bulto, "PRECINTO-DEMO-01")
    return True
