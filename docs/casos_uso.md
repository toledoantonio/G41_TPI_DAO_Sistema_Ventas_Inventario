# Casos de uso de los procesos obligatorios

Actualizado: 31/10/2026. Catálogo, compras, logística, ventas, devoluciones y cuatro reportes implementados. Las [decisiones adoptadas](decisiones_implementacion.md) reemplazan las dudas iniciales. Referencias R, D y A: [análisis de dominio](analisis_dominio.md). Actores operativos inferidos; no implican autenticación ni perfiles de usuario.

Las propuestas históricas se interpretan según las decisiones de implementación vigentes. Los errores no deben dejar operaciones parcialmente registradas. SQLite 3, frontend y State están confirmados; cada caso describe comportamiento del dominio; el README identifica las funcionalidades efectivamente implementadas.

## Correspondencia con la consigna

| Proceso obligatorio del enunciado | Caso de uso |
| --- | --- |
| 1. Administrar locales y CD | CU01 |
| 2. Administrar productos, categorías, precios, mínimos y proveedores | CU02 |
| 3. Consolidar necesidades en orden de reposición | CU04 |
| 4. Empaquetar, asignar remito y precinto | CU05 |
| 5. Registrar despacho | CU06 |
| 6. Registrar recepción y verificar precinto | CU07 |
| 7. Ventas, cobros, comprobantes y devoluciones | CU08 y CU09 |
| Integración con compras exigida por el contexto | CU03; alcance concreto a consultar |
| Mínimo de cuatro reportes no triviales | CU10 |

## CU01 — Administrar locales y Centro de Distribución

- **Actor:** responsable del comercio. **Requisitos:** R02.
- **Entrada:** código, denominación, ubicación y función (local o CD).
- **Precondiciones:** ninguna para el alta; una ubicación registrada para modificarla.
- **Flujo:** ingresar datos, validar identificación y función, guardar y consultar la ubicación. Propuesta: un CD central y varios locales.
- **Errores:** datos requeridos vacíos o código repetido; no guardar el alta. Si tiene operaciones históricas, proponer inactivación en lugar de borrado físico (D15).
- **Resultado:** ubicación identificable para compras, movimientos y ventas. Darla de alta no crea existencias.
- **Por definir:** si se necesita permitir más de un CD en el modelo; el alcance actual describe uno central.

## CU02 — Administrar catálogo, precios y mínimos

- **Actor:** responsable del comercio. **Requisitos:** R03 y R14.
- **Entrada:** categorías; producto con código, descripción, categoría, unidad y precio; proveedor con identificador y denominación; mínimo por producto/ubicación.
- **Precondiciones:** categoría y ubicación existentes para asignarlas. Los identificadores de negocio se proponen internos y únicos (D12).
- **Flujo:** registrar categoría y proveedor; registrar producto; configurar mínimos por ubicación; consultar o modificar datos comerciales.
- **Errores:** producto/proveedor duplicado, referencia inexistente, mínimo negativo o valores comerciales inválidos; no confirmar cambios. Un precio o costo negativo se rechaza; precisar si precio cero es admisible.
- **Resultado:** catálogo utilizable. Cambiar el precio vigente no modifica precios de ventas anteriores ni reintegros vinculados a ellas.
- **Por definir:** unidad entera/fraccionaria, moneda, precisión, criterio de código único y política de inactivación (A04, A05, A14).

## CU03 — Registrar compra recibida en el CD

- **Actor:** responsable de compras. **Requisito:** R01; diseño mínimo propuesto D08.
- **Entrada:** referencia, fecha, proveedor, CD y detalles de producto, cantidad y costo unitario.
- **Precondiciones:** proveedor, productos y CD registrados; mercadería efectivamente recibida y aceptada.
- **Flujo:** ingresar detalles, validar cantidades positivas y costos, calcular importe, confirmar compra y entrada al inventario del CD en una transacción.
- **Errores:** cantidades inválidas, referencias inexistentes, registro repetido o fallo al guardar movimientos; no producir entrada parcial ni duplicada.
- **Resultado:** compra trazada con costos históricos y stock del CD aumentado una vez. Actualiza el promedio ponderado del Disponible sin revalorizar las reservas (D18).
- **Por definir:** recepción parcial, pagos a proveedores y devoluciones al proveedor (A06). No incluye generación automática de compras sugeridas, que es opcional.

## CU04 — Consolidar necesidades en una orden de reposición

- **Actor:** responsable del local u operador del CD. **Requisito:** R04.
- **Entrada:** local solicitante/destinatario, CD abastecedor, fecha, productos y cantidades necesarias.
- **Precondiciones:** local, CD y productos existentes.
- **Flujo propuesto:** reunir necesidades del mismo local, consolidar cantidades por producto, registrar una orden por destino y consultar cantidades pendientes de atender (D03).
- **Errores:** cantidad no positiva, destino inválido o mezcla de destinos bajo D03; solicitar corrección. La falta de stock del CD no vuelve ficticio el stock del local: la necesidad queda pendiente.
- **Resultado:** orden registrada sin cambios de stock. Solicitud dirigida al CD; traslado posterior desde CD al local.
- **Decisiones:** una orden por local (A01) y atención parcial mediante varios bultos/remitos (A03).

## CU05 — Preparar y precintar bultos

- **Actor:** operador del CD. **Requisitos:** R05 y R12.
- **Entrada:** orden, remito, productos/cantidades por bulto y código de precinto.
- **Precondiciones:** orden con cantidades pendientes, disponibilidad asignable del CD y destino coherente.
- **Flujo propuesto:** crear un remito por bulto para una orden/destino; distribuir contenido; reservar cantidades y registrar estado inicial Preparado; asignar precinto, cerrar contenido y pasar a Precintado. Cada confirmación registra sus efectos y su historial conjuntamente.
- **Errores:** contenido vacío, cantidades superiores al pendiente o asignable, precinto repetido o intento de modificar un bulto ya precintado; no confirmar la operación inválida.
- **Resultado:** bulto identificado, contenido reservado y trazabilidad de preparación/precintado. La reserva es parte del físico del CD; no suma stock físico ni disponibilidad al local.
- **Decisiones:** un remito por bulto y despachos parciales. La preparación queda fija y no se implementa cancelación en esta versión; no se agrega un estado Cancelado.

## CU06 — Despachar bultos desde el CD

- **Actor:** operador del CD. **Requisitos:** R06 y R12.
- **Entrada:** bulto(s) precintado(s), fecha y referencia operativa.
- **Precondiciones:** contenido, reserva, remito y destino coherentes; estado Precintado.
- **Flujo:** validar salida, consumir reserva, disminuir físico del CD, registrar tránsito y transición a En tránsito en una transacción.
- **Errores:** estado incorrecto, reserva insuficiente, despacho ya aplicado o fallo persistente; no duplicar salida ni dejar historial separado del stock.
- **Resultado:** mercadería trazada en tránsito, fuera del físico del CD y todavía no disponible en destino.

## CU07 — Recibir, verificar o rechazar

- **Actor:** responsable del local. **Requisitos:** R07, R11 y R12.
- **Entrada:** bulto, local receptor, fecha, precinto observado y resultado de inspección/correspondencia con remito.
- **Precondiciones:** bulto En tránsito hacia ese local.
- **Flujo:** registrar llegada y estado Recibido sin habilitar venta; inspeccionar precinto y correspondencia; registrar Verificado si cumple, o Rechazado si el precinto está roto. Evaluar la verificación del remito y habilitar cantidades una sola vez únicamente si remito y bulto están Verificados.
- **Errores:** destino equivocado o secuencia inválida; no confirmar recepción. Precinto distinto o diferencias de contenido no se aceptan silenciosamente: registrar la incidencia y mantener bloqueo hasta definir su resolución (A12). Fallo en habilitación revierte sus cambios de estado/movimientos correspondientes.
- **Resultado:** llegada y resultado conservados en el historial. Un rechazo no supone retorno automático al CD ni destrucción de mercadería.
- **Decisión A02 resuelta:** un remito contiene un único bulto. D10 fue simplificada a un remito por bulto, por lo que no hay aceptación parcial dentro de un remito.

## CU08 — Registrar venta, cobro y comprobante

- **Actor:** vendedor/cajero. **Requisitos:** R08, R09 y R13.
- **Entrada:** local, fecha, productos/cantidades y cobros por medio de pago.
- **Precondiciones:** productos registrados y stock disponible/verificado suficiente en el local.
- **Flujo propuesto:** consolidar cantidad por producto; conservar precio y costo aplicados; calcular total; validar pago completo, eventualmente mixto (D06); registrar venta/detalles, salida de Disponible, cobros/caja y comprobante interno en una transacción.
- **Errores:** cantidad no positiva, sobreventa agregada, cobro distinto del total o fallo al registrar cualquier componente; no confirmar venta parcial ni conservar cobro aislado.
- **Resultado:** venta histórica, stock reducido y cobros documentados. Modificar catálogo posteriormente no altera esta operación.
- **Decisión aplicada:** pagos simples o mixtos por el total exacto; importes en centavos y comprobante interno sin integración fiscal.

## CU09 — Registrar devolución comercial

- **Actor:** vendedor/cajero o responsable del local. **Requisitos:** R10 y R15.
- **Entrada:** venta original, detalles/cantidades a devolver, fecha, motivo, condición de mercadería y medio de reintegro.
- **Precondiciones:** venta registrada y política de devolución satisfecha. Propuesta: mismo local de venta.
- **Flujo:** recuperar originales y devoluciones previas; validar pertenencia y cantidad acumulada; calcular reintegro con precio original; inspeccionar condición; registrar devolución, movimiento de inventario y egreso de caja en una transacción.
- **Errores:** venta inexistente, producto ajeno, cantidad acumulada superior a la vendida, plazo/condición incumplidos o fallo persistente; no aceptar devolución parcial inconsistente.
- **Resultado:** reintegro trazado; producto vendible vuelve a Disponible y producto no vendible queda bloqueado. El reintegro no determina por sí solo vendibilidad.
- **Decisión aplicada:** mismo local, motivo y referencia única, sin plazo arbitrario; se admite elegir medio de reintegro. Se consolidan renglones repetidos y se controla el acumulado de ambas condiciones. Vendible vuelve al costo original; NO_VENDIBLE queda en Rechazado con causa DEVOLUCION. Precio cero implica reintegro cero sin movimiento ficticio de caja.

## CU10 — Consultar cuatro reportes

- **Actor:** responsable del comercio. **Requisito:** R17.
- **Entrada:** período, ubicación y filtros aplicables.
- **Precondiciones:** operaciones conservadas; con cero datos mostrar resultado vacío o cero según indicador, sin dividir por cero.
- **Flujo:** consultar ventas/ingresos por local y medio; ranking de productos y margen estimado; existencias/mínimos; rechazos por precinto. Definiciones detalladas: REP01-REP04 del análisis.
- **Errores:** período inválido o referencias incorrectas; solicitar corrección.
- **Resultado:** consultas con agregaciones, sin modificar operaciones. Cobros mixtos no duplican total de venta; mínimos incluyen saldo cero; rechazo no equivale automáticamente a pérdida económica.
- **Implementado:** presentación tabular por secciones y CSV. Devoluciones por fecha real; margen histórico con reversión de costo solo para vendibles. Existencias es una foto actual. El medio filtra únicamente la sección caja. Véanse [definiciones](reportes.md).

## CU11 — Generar y recibir compra sugerida (opcional)

- **Actor:** responsable de compras. **Entrada:** CD, proveedor elegido y referencia única.
- **Flujo:** consultar faltantes netos, generar una orden SUGERIDA sin cambiar stock, consultar sus productos y preparar la recepción. Registrar una compra real completa con los productos/cantidades de la orden, costos y lotes; confirmar documento, inventario, trazabilidad y estado RECIBIDA juntos.
- **Reglas:** mínimos locales y pedidos no se duplican; descuentan stock no vencido, bultos en camino y sugerencias abiertas. Recalcular bajo transacción al generar. No recibir dos veces ni usar otro proveedor/CD o cantidades distintas. Una sugerencia pendiente puede cancelarse sin borrar historia ni afectar stock.
- **Resultado:** necesidad documentada y, al recibir, compra vinculada. No incluye cotizaciones, envío al proveedor ni recepción parcial. [Fórmula y decisiones](opcionales.md).

## CU12 — Registrar y trazar lotes/vencimientos (opcional)

- **Actor:** compras, operador logístico y vendedor. **Entrada:** producto, código de lote y vencimiento opcional al recibir.
- **Flujo:** registrar lote o reutilizarlo conservando su fecha; asignar unidades FEFO a bultos y ventas; consultar saldos y movimientos por lote. En devoluciones seleccionar el lote vendido cuando existan varios y controlar su acumulado.
- **Errores:** fecha inválida, compra vencida, cambio de vencimiento del mismo lote, stock no vencido insuficiente o retorno de lote ajeno. Un vencido no se despacha, vende ni devuelve como vendible. Si venció en tránsito, recibir mantiene Pendiente y verificar no lo habilita.
- **Resultado:** trazabilidad actual persistente, con libro inmutable y coincidencia entre saldos agregados y por lote. El stock anterior conserva origen desconocido; no se inventan fechas históricas. No incluye series por unidad ni destrucción/recuperación de vencidos. [Límites](opcionales.md).
