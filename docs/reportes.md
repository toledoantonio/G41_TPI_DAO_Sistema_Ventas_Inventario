# Cuatro reportes no triviales

Implementados el 31/10/2026. Presentación en **8. Reportes**, consultas en `ReportesDAO`, validación y exportación en `GeneradorReportes`. Todas las secciones se leen dentro de una misma transacción SQLite, sin modificar operaciones.

Se contrastaron con las familias sugeridas en la consigna y el apunte de reportes de la cátedra. La pestaña **Gráfico** muestra barras construidas con los mismos resultados filtrados que las tablas. La exportación conserva las secciones tabulares en CSV. [Referencias de cátedra](referencias_catedra.md#comprobación-del-incremento-del-31102026).

## REP01 — Ventas e ingresos

- Sección comercial por local: cantidad de ventas/devoluciones, venta bruta, reintegros y venta neta. Se agregan cabeceras, sin unirlas con los cobros para evitar multiplicar una venta de pago mixto.
- Sección caja por local/medio: cantidad de movimientos, ingresos, egresos y neto. Cada cobro y reintegro aparece una vez.
- Período y local filtran ambas secciones. El medio filtra **solo caja**; no atribuye el total completo de una venta mixta a cada medio.
- Un producto de precio original cero se devuelve con documento y movimiento de stock, pero sin egreso ficticio.

## REP02 — Ranking y margen estimado

Agrupa por producto/local y ordena por unidades netas descendentes, luego margen y código. Muestra unidades vendidas/devueltas/netas, ingreso neto, costo neto, costo no recuperado y margen.

- Ingreso neto = ventas al precio histórico − reintegros al precio original.
- Costo neto = costo histórico de ventas − costo original de devoluciones **vendibles**.
- En devoluciones no vendibles no se revierte costo como si se hubiera recuperado mercadería disponible. Se informa como costo no recuperado, incluido ya en costo neto (no se suma dos veces).
- Margen estimado = ingreso neto − costo neto. No incluye gastos ni impuestos y no constituye utilidad contable final. La mercadería bloqueada mantiene trazabilidad; no se registra destrucción automática.

## REP03 — Existencias y mínimos

Foto **actual**, sin filtro temporal. Detalle por ubicación/producto y resumen por ubicación con productos bajo mínimo, unidades faltantes y valorización. Con lotes/vencimientos, faltante = máximo entre cero y mínimo − Vendible no vencido. Se muestran Disponible registrado, Vendible y Vencido, sin eliminar mercadería por vencer. Incluye combinaciones de catálogo sin fila de stock y productos con saldo cero.

Disponible se valora al promedio vigente. Reservado se valora desde bultos Preparados/Precintados, Pendiente desde bultos Recibidos, y bloqueado desde bultos Rechazados y devoluciones NO_VENDIBLE. Esos orígenes se agregan antes de unirlos para evitar duplicaciones. El tránsito queda fuera del físico de ubicaciones y no se suma como disponible. Importes unitarios redondeados al centavo.

## REP04 — Rechazos por precinto

El período corresponde a la **decisión final** Verificado/Rechazado. Por destino calcula bultos evaluados/rechazados, tasa de rechazo, unidades rechazadas, valor comprometido y horas promedio de tránsito despacho → recepción de los bultos evaluados. Otra sección agrupa productos/cantidades comprometidos.

Tasa = rechazados / (verificados + rechazados) × 100. Bultos sin decisión no integran el denominador. El contenido se agrega antes de contar decisiones: un bulto con dos productos sigue siendo un bulto. Rechazo logístico y devolución comercial son procesos distintos. Valor comprometido no equivale a pérdida definitiva.

## Fechas, resultados vacíos y CSV

Fechas inclusivas `AAAA-MM-DD` sobre la fecha civil guardada en el evento (la aplicación registra el huso local). Se puede dejar un extremo o ambos vacíos. Fechas inválidas, períodos invertidos y ubicaciones inexistentes se rechazan. Las devoluciones se agrupan por su fecha real: puede haber reintegros sin ventas y netos negativos en un período. No se reexpresan ventas de meses anteriores.

Con cero eventos se presentan tablas vacías, sin divisiones por cero. Elegir filtros y pulsar **Generar reporte**; cambiar filtros requiere volver a generar. **Exportar resultado a CSV** guarda la consulta ya generada, filtros, notas y secciones, en UTF-8 con BOM y separador `;`. Textos que podrían interpretarse como fórmulas se exportan como texto. No requiere librerías externas.

`tests/test_devoluciones_reportes.py` contrasta importes conocidos: venta de 500, reintegro de 250, caja neta de 250 y margen de 50, con cobros mixtos y condiciones de devolución distintas; tasa de rechazo de un bulto de dos productos, mínimos con saldo cero y períodos separados. `tests/test_interfaz.py` prueba las cuatro vistas, CSV y reapertura tras devolución.
