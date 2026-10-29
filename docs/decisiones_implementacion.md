# Decisiones de implementación

Actualizado: 28/10/2026. El usuario indicó resolver las dudas con alternativas simples, basadas en el dominio de la consigna, sin esperar aclaraciones docentes. Estas decisiones reemplazan las propuestas incompatibles del análisis del 12/10. No se atribuyen al profesor.

## Alcance del incremento implementado

Aplicación de escritorio Python con Tkinter y SQLite 3, sin dependencias externas de ejecución. Implementa alta y modificación de catálogo/ubicaciones, mínimos, compra recibida, pedido por local, preparación, precintado, despacho, recepción, verificación/rechazo e inventario consultable. Hay varios productos por compra, orden y bulto; los renglones repetidos se consolidan antes de validar cantidades.

También se implementaron ventas de varios productos, cobros simples o mixtos, caja y comprobantes internos; precio y costo históricos quedan conservados por detalle. La operación completa se confirma o revierte junta. El inventario Disponible se valoriza por promedio ponderado, y las transferencias conservan el costo fijo de preparación del bulto. Devoluciones y cuatro reportes no triviales siguen pendientes; el TP aún no está terminado.

## Reglas adoptadas

| Referencia anterior | Decisión | Motivo y alcance |
| --- | --- | --- |
| A01 / D03 | Una orden por local destino, con necesidades consolidadas por producto | No mezcla destinos; diferencia dirección del pedido y dirección de la mercadería. |
| A02 / D04 / D10 | **Un remito por bulto**, con una orden, CD y destino identificados | El PDF no obliga a agrupar varios bultos en un remito. Evita remitos con resultados mixtos: cada remito se verifica o rechaza junto con su bulto. Sustituye el bloqueo global propuesto antes. |
| A03 | Se permiten varios bultos/remitos para atender parcialmente una orden | Cada contenido consume parte de la cantidad por asignar. No supera lo pedido ni lo disponible en CD. Un rechazo no libera lo ya enviado; para reponerlo se registra otra necesidad. |
| A04/A05 | Una categoría por producto; precio vigente por producto; mínimo por producto/ubicación; códigos internos únicos | Códigos normalizados a mayúsculas y sin espacios externos. No se usan CUIT ni código de barras como requisito. |
| A06 | Compra registrada al recibir y aceptar mercadería completa en el CD | Conserva proveedor, referencia única, cantidades, costo unitario y fecha. No incluye cuentas de proveedores, recepción parcial ni sugerencias automáticas. |
| A07 / D11 | Reservar al preparar, descontar físico al despachar | Disponible disminuye y Reservado aumenta al preparar; la reserva forma parte del físico. El contenido queda fijo desde la preparación. No se implementa cancelación o edición de bultos en este incremento. |
| A10 / D17 | SQLite 3, acceso sqlite3, conexión y transacción por operación | `BEGIN IMMEDIATE` serializa operaciones de escritura que validan stock. Los DAOs comparten conexión y no hacen commits propios. |
| A12 / D09 | Ciclo hacia adelante; rechazo por precinto roto; código distinto íntegro permanece pendiente | El rechazo se conserva en destino sin habilitar venta. No hay retorno, merma automática ni recuperación de rechazados. Corregir la evidencia de una inspección fallida y reintentar es posible mientras continúe Recibido. Diferencias de contenido deben resolverse antes de confirmar conformidad. |
| A13 | Stock inicial cero; ingresar mercadería mediante compra | La demostración utiliza una compra real dentro de una base separada, no saldos insertados sin procedencia. |
| A14 / D20 | Cantidades enteras en unidades; importes con hasta dos decimales, guardados en centavos | Validación con Decimal; importes negativos o más de dos decimales se rechazan. Sin integración monetaria ni fiscal. El límite de entrada por cantidad/importe es 1.000.000.000. |
| Frontend | Tkinter/ttk | Incluido con la distribución habitual de Python para Windows; se ejecuta localmente, sin servidor ni herramientas de frontend adicionales. |
| Patrones | State, DAO y Singleton aplicados | State delega en seis estados concretos; DAO separa SQL. Singleton conserva un gestor por proceso, con ruta fija y conexión independiente por operación. |
| D18 / Costos | Promedio ponderado del Disponible, redondeado al centavo | Preparar retira unidades del conjunto que se promedia. Reservado, Pendiente, En tránsito y Rechazado conservan el costo del contenido del bulto. Comprar no revaloriza esas unidades. Verificar incorpora su costo al promedio Disponible del local. |

La venta exige pago completo y emite un comprobante interno; los medios de pago se registran sin pasarela. Próximo incremento: devolución vinculada al detalle original, en el mismo local, con cantidades acumuladas controladas y reintegro al precio original. Sin plazo arbitrario agregado por el sistema: la política base validará origen, cantidad y condición de mercadería. La vendibilidad se inspeccionará independientemente del reintegro. La devolución todavía no está programada.

Las bases anteriores reconstruyen costos mediante una migración versionada y transaccional desde documentos y movimientos. No se reescriben ventas ni costos de bultos ya registrados; si no hay respaldo suficiente se revierte la migración. Los límites y el tratamiento de históricos están detallados en [modelo de datos](modelo_datos.md#migración-de-costos).

## Garantías verificadas

- Historial del bulto protegido mediante triggers SQLite contra UPDATE/DELETE; el servicio contrasta el estado reconstruido con su última transición.
- Estado, historial, remito, saldos y movimientos se confirman o revierten en una misma transacción.
- State rechaza saltos y repeticiones; repetir despacho/recepción/verificación no agrega otro movimiento.
- Compra repetida, precinto repetido, producto/proveedor duplicado, origen/destino equivocado y sobreasignación se rechazan.
- Disponible del local solo aumenta cuando **bulto y remito** están Verificados. Recibido queda Pendiente; Rechazado no se vende.
- Los mínimos se consultan también con saldo cero. Los movimientos explican las variaciones de cada condición de inventario.
- La venta consolida cantidades, no supera Disponible y exige cobros por el total exacto. Un comprobante duplicado revierte venta, stock y caja.
- Una compra entre preparación y despacho mantiene el costo de lo reservado. Se verifica conservación de valor con datos conocidos, respetando el redondeo unitario a centavos.
- La migración conserva saldos e historial, revierte cambios ante inconsistencias y no se repite al reabrir. El Singleton rechaza otra ruta y serializa la inicialización concurrente.

La inmutabilidad exigida es del historial de estados en la aplicación y la base local; no se añade un sistema de auditoría criptográfica ni permisos de usuarios.
