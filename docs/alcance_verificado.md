# Cobertura del trabajo práctico

Revisión del 28/10/2026 contra el código, el esquema SQLite y los procesos de la consigna.

## Procesos obligatorios

| Proceso | Cobertura real | Falta o límite |
| --- | --- | --- |
| 1. Administrar sucursales y CD | Alta y modificación desde frontend; jerarquía `Ubicacion` → `CentroDistribucion` / `Local`; código único y un CD central | No hay borrado/inactivación. No se borra historia. |
| 2. Administrar catálogo, categorías, precios, mínimos y proveedores | Alta/modificación, precios en centavos, mínimo por producto/ubicación y control de códigos duplicados | Sin listas de precios, promociones ni descuentos, que son opcionales. |
| 3. Consolidar necesidades en orden | Una orden por local (`OrdenReposicion`), varios productos, renglones consolidados y atención parcial | Decisión simple adoptada: no hay órdenes multilocal. |
| 4. Preparar bultos, remito y precinto | Contenido con varios productos y costo histórico de transferencia (`ContenidoBulto`), reserva, remito por bulto y precinto único | Contenido fijo al preparar; sin cancelación ni edición de bultos. |
| 5. Registrar despacho desde CD | Salida de reservado, transición En tránsito e historial atómicos | No incluye transporte externo ni seguimiento geográfico. |
| 6. Recibir y verificar precinto | Valida local destino, mantiene Pendiente, verifica o rechaza con remito, transfiere costo promedio ponderado al local y registra movimientos conjuntos | Código distinto íntegro queda bloqueado. |
| 7. Venta, cobro, comprobante y devolución | **Ventas, cobros, caja y comprobante implementados** (`Venta`, `DetalleVenta`, `Cobro`, `Comprobante`, `VentaDAO`, pestaña 6). **Falta devolución comercial.** | Falta implementar `Devolucion` / `DetalleDevolucion` vinculada a la venta original. |
| Integración de compras del contexto | Compra recibida en CD (`Compra`, `DetalleCompra`), proveedor, detalles/costos históricos, entrada de stock y cálculo de costo promedio ponderado | Sin pagos a proveedores ni recepción parcial, según alcance mínimo adoptado. |

## Validaciones y mínimos de entrega

| Requisito | Cobertura |
| --- | --- |
| Disponible solo después de verificar remito y contenedor | Implementado y probado. Un remito por bulto evita resultados mixtos. |
| Precinto roto rechaza y no habilita venta | El inventario queda Rechazado, no aumenta Disponible ni altera el costo promedio del local. |
| Historial inmutable del bulto | Triggers impiden UPDATE/DELETE; estado e historial se guardan juntos y se contrastan al recuperar. |
| No vender por encima de Disponible | **Implementado y probado.** `Venta` consolida renglones por producto y valida contra el stock `disponible` del local antes de confirmar. |
| Evitar productos/proveedores duplicados | Códigos normalizados y únicos; validaciones en objetos de dominio, servicios y SQLite. |
| Devolución vinculada a venta y reglas | **Pendiente (Incremento 2):** requiere originales, cantidades acumuladas, condición de mercadería y reintegro. |
| Al menos dos patrones | **Cumplido:** **State** (GoF), **Singleton** (GoF) y **DAO** aplicados, documentados y probados con `pytest`. |
| Al menos cuatro reportes no triviales | **Pendiente (Incremento 3).** |
| SQLite 3 y frontend | Implementados: `sqlite3` y `Tkinter/ttk`. |

Correcciones verificadas: costos fijos de reservas separados del promedio Disponible; conservación de valor en compras intercaladas con transferencias y ventas; reconstrucción transaccional/versionada de costos anteriores, con reapertura y rollback; configuración única que rechaza otra ruta e inicialización concurrente protegida. Véanse [regresiones](../tests/test_costos_migracion.py) y [límites de migración y redondeo](modelo_datos.md#migración-de-costos).

## Orden de implementación pendiente

1. Implementar devolución parcial vinculada al detalle original, acumulados, reintegro al precio original y reingreso vendible o bloqueado según condición (Incremento 2).
2. Completar los cuatro reportes previstos: ventas/ingresos por período, local y medio; productos más vendidos y margen; existencias/mínimos; rechazos por precinto con agregaciones (Incremento 3).
3. Demostrar el recorrido integral completo desde el frontend (Incremento 4).

## Documentación actualizada

- [DER y diccionario de datos implementados](modelo_datos.md): tablas, atributos, claves y cardinalidades.
- [Clases implementadas](modelo_clases.md): objetos Python y dependencias reales.
- [Modelo conceptual](modelo_conceptual.md): conceptos del dominio.
- [Estados del bulto](ciclo_bulto.md): transiciones y guardas.
- [Secuencia de verificación](secuencia_verificacion.md): colaboración de State, DAO y transacción.
- [Patrones](patrones.md): problema, participantes, ubicación y pruebas de State, Singleton y DAO.
