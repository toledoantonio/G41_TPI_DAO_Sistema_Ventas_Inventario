# Material histórico para la consulta docente

**Actualización 22/10/2026:** no se obtuvieron respuestas docentes. El usuario autorizó avanzar con decisiones simples; las [decisiones de implementación](decisiones_implementacion.md) reemplazan estas preguntas como bloqueos. Este documento conserva la preparación original del 15/10, no describe el estado actual.

Charla prevista: jueves 15/10/2026. Propuesta de exposición, sin respuestas docentes registradas todavía.

## Qué mostrar

1. [Casos de uso](casos_uso.md): correspondencia con los siete procesos obligatorios y tratamiento de compras, errores y efectos de stock/caja.
2. [Modelo de objetos preliminar](modelo_clases.md): catálogo/comercial, logística y participantes de State.
3. El ejemplo numérico de este documento: permite discutir cuándo una cantidad se vuelve disponible y cómo se conserva el historial.

Estos materiales son resultados de análisis y diseño. No acreditan que el sistema esté implementado. El objetivo de la charla es validar las decisiones que afectan el modelo antes de fijar el DER y escribir los flujos completos.

## Recorrido para explicar en cinco a diez minutos

Propuesta: un CD, un local, un producto P y operaciones sin stock inicial arbitrario. Cantidades enteras solo para facilitar el ejemplo; costos y unidad definitivos siguen por acordar.

| Paso | Físico en CD | Reservado en CD | En tránsito | Pendiente en local | Disponible en local | Rechazado en local |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Compra recibida: 20 unidades | 20 | 0 | 0 | 0 | 0 | 0 |
| Local solicita 10 | 20 | 0 | 0 | 0 | 0 | 0 |
| Preparar y precintar un bulto con 10 | 20 | 10 | 0 | 0 | 0 | 0 |
| Despachar | 10 | 0 | 10 | 0 | 0 | 0 |
| Recibir | 10 | 0 | 0 | 10 | 0 | 0 |
| Verificar bulto y remito | 10 | 0 | 0 | 0 | 10 | 0 |
| Vender 3 | 10 | 0 | 0 | 0 | 7 | 0 |
| Devolver 1 aceptada como vendible | 10 | 0 | 0 | 0 | 8 | 0 |

La reserva está incluida en el físico del CD, no se suma a este. Las 20 unidades quedan explicadas tras la devolución: 10 en CD, 8 en el local y 2 netas entregadas al público.

Si el precio aplicado es 100 unidades monetarias, la venta cobra 300 y la devolución reintegra 100: ingreso neto de caja 200. Ese valor no es ganancia; el margen requiere costo histórico. Se propone un comprobante interno.

**Alternativa de rechazo:** desde la fila Recibir, si llega roto el precinto, las 10 pasan de Pendiente a Rechazado; Disponible queda en cero. No se vende ni se devuelve automáticamente al CD. Repetir verificación/despacho tampoco duplica movimientos.

**Caso crítico para discutir:** un remito tiene dos bultos de 5 unidades, uno íntegro y otro roto. El análisis propone bloquear también las 5 intactas mientras el remito no esté Verificado. Mostrar esa consecuencia y consultar si la cátedra espera aceptación parcial y cómo documentarla.

## Preguntas prioritarias

Llevar primero las cinco primeras; las demás pueden resolverse si queda tiempo. Todas incluyen una propuesta para que el docente evalúe una solución concreta.

| Prioridad / referencia | Consulta concreta | Propuesta para mostrar y motivo |
| --- | --- | --- |
| 1 — A01 | ¿La consolidación debe producir una orden que reúna varios locales, o es válido consolidar productos en una orden por local? | Una orden por destino. Simplifica remito y traslado, pero queremos confirmar que satisface la consolidación exigida. |
| 2 — A02 | Con un remito y dos bultos, uno íntegro y otro rechazado, ¿cómo se espera habilitar el íntegro respetando que remito y contenedor estén Verificados? | Bloqueo de todo el remito bajo D10 como base provisional. Comparar con aceptación parcial o separación documental si el docente las admite; no asumir que están exigidas. |
| 3 — A06 | Para integrar compras, ¿alcanza registrar compra recibida con proveedor, cantidades, costos y entrada al CD? ¿Se requieren pagos, recepción parcial o devolución al proveedor? | Compra recibida completa; compras sugeridas se dejan para la segunda parte. Determina entidades y alcance económico. |
| 4 — A11 | State está elegido para Bulto. ¿DAO cuenta dentro del mínimo de dos patrones? ¿Se exige que sean GoF? ¿Qué criterio usar para justificar el restante? | State confirmado, DAO candidato y objetivo del grupo de aproximadamente tres. Elegir el restante por una colaboración real del sistema. |
| 5 — A08 | ¿Podemos definir devoluciones parciales en el mismo local con precio original y condición de vendibilidad? ¿Hay plazo o restricciones obligatorios? | Control de cantidades acumuladas y reintegro original; plazo por acordar. Evita devolver más de lo vendido y reponer mercadería dañada. |
| 6 — A03/A07 | ¿Se admite atender una orden en varios despachos? ¿Está bien reservar al preparar y descontar físico al despachar? | Atención parcial trazada sin superar lo solicitado; reserva incluida en físico. Consultar cómo cancelar una preparación preservando historial. |
| 7 — A12 | ¿Cómo tratar precinto diferente o diferencias de contenido, y qué alcance se espera para resolver un rechazo? | Conservar evidencia y bloquear venta; no inventar recuperación ni retorno automático. |
| 8 — A09/A14 | ¿Es válido un comprobante interno, cobro completo con medios mixtos y valores exactos? ¿Hay unidades/moneda exigidas? | Registrar sin integración fiscal ni pasarela; definir precisión antes del esquema. |
| 9 — REP01-REP04 | ¿Estos cuatro reportes cubren el requisito de ser no triviales? ¿Se exige exportación PDF o alcanza visualización en frontend? | Agregaciones por períodos/locales/medios, ranking y margen, mínimos con saldo cero y rechazos con proporciones. |

## Cómo registrar las respuestas

Completar una fila por decisión efectivamente conversada; si no se trató, dejar pendiente. Anotar condición y ejemplo, además de la respuesta breve.

| Referencia | Respuesta docente / condición | Decisión del grupo | Documentos y componentes afectados |
| --- | --- | --- | --- |
| A01 | Pendiente | Pendiente | Orden, detalles, remitos, CU04 y modelo |
| A02 | Pendiente | Pendiente | Verificación, inventario, CU07 y State |
| A06 | Pendiente | Pendiente | Compra, pagos y CU03 |
| A11 | Pendiente | State confirmado; restantes pendientes | Justificación y participantes de patrones |
| A08 | Pendiente | Pendiente | Devolución, caja, inventario y CU09 |

## Orden de trabajo después de la charla

1. Incorporar las respuestas y ajustar casos de uso/cardinalidades; resolver especialmente A01/A02 antes de cerrar logística.
2. Elaborar el DER lógico de SQLite 3 y un diccionario de datos: claves, unicidad, referencias, históricos y restricciones. Contrastar con el modelo de objetos, sin convertir todas sus clases en tablas.
3. Elegir frontend por facilidad de ejecución y demostración. Implementar el primer incremento: catálogo, ubicaciones y mínimos, persistencia y pantalla mínima. Verificar duplicados y reinicio.
4. Construir compra e inventario del CD; luego reposición/logística con State, venta/cobro y devolución, incorporando interfaz y pruebas por flujo.
5. Completar cuatro reportes y demostrar todos los procesos obligatorios antes de abordar opcionales.

Antes de la charla conviene recorrer los documentos y ensayar los dos ejemplos (normal y rechazo). No es necesario tener todos los procesos programados para que el profesor pueda evaluar estas decisiones; si la clase exige específicamente un prototipo ejecutable, ese criterio debe incorporarse a la preparación.
