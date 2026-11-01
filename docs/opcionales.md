# Dos procesos opcionales implementados

Incremento del 31/10/2026, rama `codex/compras-sugeridas-lotes`, desde `main` con el alcance obligatorio integrado. Se eligen **compras sugeridas por faltantes** y **registro de lotes/vencimientos**. La segunda familia admite lotes, series **o** fechas: esta versión implementa lotes con vencimiento opcional; no incluye números de serie por unidad.

## 1. Órdenes de compra sugeridas

En **9. Compras / lotes → Órdenes de compra sugeridas**, elegir CD y proveedor, consultar faltantes e ingresar referencia única. Generar crea un documento SUGERIDA con sus detalles, sin stock, caja ni compra recibida ficticia.

Por producto se calcula:

1. Vendible = unidades disponibles de lotes sin vencimiento o con vencimiento no anterior al día de la operación.
2. Para cada local, necesidad por mínimo = máximo entre cero y mínimo − Vendible − bultos no vencidos en camino al local. En camino incluye Preparado, Precintado, En tránsito y Recibido, sin habilitarlos para venta.
3. Necesidad del local = máximo entre esa necesidad por mínimo y los pedidos de reposición todavía sin asignar. No se suman ambos porque podrían expresar la misma necesidad.
4. Compra sugerida = máximo entre cero y mínimo del CD + suma de necesidades locales − Vendible del CD − cantidades de órdenes de compra SUGERIDAS pendientes.

Se excluyen lotes vencidos del stock útil y de los envíos que cubren mínimos. Las reservas ya están fuera del Disponible del CD. Un rechazo no libera cantidades previamente asignadas a una orden de reposición; como en el alcance obligatorio, una reposición nueva exige una necesidad nueva. Los mínimos permiten detectar nuevamente el faltante del local.

Al generar se recalculan cantidades bajo `BEGIN IMMEDIATE`. Si otra ventana ya cubrió el faltante, no se duplica la sugerencia. La API permite cantidades parciales hasta el faltante vigente; la pantalla genera el conjunto completo de faltantes actuales. El proveedor es elegido por el operador: no se supone que un producto tenga un único proveedor ni se adivinan precios de compra.

### Recepción y cancelación

Seleccionar la sugerencia y **Preparar recepción en Compras**. La pestaña 2 muestra la orden vinculada y las cantidades que deben ingresarse. Registrar productos, cantidades, costos reales y lotes/vencimientos; **Confirmar compra recibida** crea la compra, stock, costos, lotes y movimientos, y cambia la orden a RECIBIDA con su compra asociada, en una misma transacción.

La recepción es completa, con los mismos productos/cantidades, CD y proveedor. No se incluye recepción parcial. Una sugerencia recibida no se vuelve a recibir ni cancelar. CANCELADA libera su cobertura pendiente, conserva el documento y no cambia stock. Un fallo o compra duplicada revierte todos los efectos, incluyendo el estado de la sugerencia. **Usar compra independiente** permite salir de la vinculación antes de confirmar.

## 2. Lotes y fechas de vencimiento

Cada renglón de compra admite código de lote y vencimiento `AAAA-MM-DD`, ambos visibles en pantalla. Sin código se genera uno por compra/producto; sin fecha no se presume vencimiento. Se permiten varios lotes del mismo producto en una compra con el mismo costo unitario, conservando la regla económica previa de un costo por producto/compra.

La identidad es producto + código normalizado. Un lote existente conserva su vencimiento: repetir el código con otra fecha se rechaza. Una compra ya vencida se rechaza sin dejar documento, costo ni stock parcial. La fecha de vencimiento es inclusiva: el producto se puede usar durante ese día y deja de ser vendible al día siguiente.

### Asignación y trazabilidad

- Preparación: se eligen lotes no vencidos por FEFO (vence primero, sale primero), con los que no tienen fecha al final; empate por id. Se registran reserva y asignación al bulto.
- Despacho y recepción mantienen los lotes del bulto. Un lote que venció después de prepararse no puede despacharse. Si vence en tránsito se puede registrar su recepción, pero no habilitarlo mediante verificación; queda pendiente y se informa el bloqueo. Un rechazo por precinto roto puede registrarse, sin fingir una rotura para resolver un vencimiento.
- Venta: usa FEFO entre lotes disponibles y no vencidos y conserva las cantidades por detalle de venta. El costo económico sigue siendo el promedio ponderado histórico del producto, no un costo FIFO/FEFO por lote.
- Devolución: vuelve al lote realmente vendido. Con varios lotes se exige seleccionar el que se devuelve; se controla su acumulado, además del acumulado del detalle original. Un lote vencido solo puede devolverse como NO_VENDIBLE. La pantalla permite elegir el lote y muestra las cantidades todavía devolvibles.
- En **9 → Lotes y vencimientos** se consultan saldos y el libro de movimientos por lote y ubicación, identificando causa, documento y fecha. En logística se pueden consultar los lotes de cada bulto.

Los cuatro saldos agregados coinciden con la suma por lote. Los movimientos, asignaciones y saldos se confirman o revierten junto con la operación de negocio. No se editan lotes históricos ni se reasignan ventas pasadas desde la aplicación.

### Disponible registrado y Vendible

El vencimiento no elimina mercadería ni registra una pérdida por sí solo. **Disponible registrado** conserva el saldo físico y su costo promedio; **Vendible** excluye las unidades vencidas. Inventario y reporte de existencias muestran ambas cantidades y Vencido. Faltantes y compras sugeridas usan Vendible. Los reportes de ventas y márgenes siguen usando operaciones históricas, sin reescribirlas al vencer un lote.

No se incorporan destrucción de vencidos, recuperación de rechazados, cancelación de bultos ni conciliación física: requieren un proceso explícito. Los lotes vencidos reservados o pendientes permanecen trazados y bloqueados hasta una resolución operativa externa a este incremento.

## Actualización de bases

Esquema versión 3, en la misma transacción de apertura. Versiones 0/1 conservan los pasos económicos anteriores; versión 2 añade estos opcionales sin reconstruir costos. El stock previo se agrupa en un lote **LEGADO-SIN-IDENTIFICAR** por producto, con bandera de origen desconocido y sin fecha inventada. Se preservan saldos y asignaciones necesarias para continuar bultos/ventas/devoluciones anteriores, pero el libro por lote comienza con una instantánea MIGRACION: no atribuye lotes físicos ni movimientos que no se registraron en el pasado. Las compras nuevas identifican sus lotes propios.

La condición legado se informa en pantalla; no acredita que el stock previo haya sido inspeccionado para vencimiento. No se permite usar ese código como si fuera un lote de una compra nueva. Reabrir una base ya actualizada no repite la migración.

## Verificación

Las pruebas de `tests/test_opcionales.py` contrastan FEFO, vencimientos en distintos pasos, devoluciones con varios lotes, compatibilidad de metadatos, saldos agregado/lote/libro, rollback ante fallos, sugerencias concurrentes, mínimos/pedidos/tránsito sin duplicación, recepción completa y migración desde versión 2. La prueba de interfaz recorre sugerencia → compra real con lote → recepción → consulta y reapertura.

La [revisión de integridad previa al merge](verificacion_integridad.md) agrega secuencias reproducibles con conciliación tras cada paso, fallos tardíos y competencia entre procesos independientes.
