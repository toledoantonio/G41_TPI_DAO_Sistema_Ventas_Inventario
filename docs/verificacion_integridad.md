# Verificación de integridad antes de integrar los opcionales

Revisión del 31/10/2026 sobre `codex/compras-sugeridas-lotes`. No realiza merge, commit ni push y no modifica la base de uso normal.

## Resultado

**101 pruebas pasan**, incluidas las pruebas de interfaz y las 12 comprobaciones nuevas de integridad. El informe automatizado de la ejecución queda en `tmp/integridad/resultados.xml`, fuera del control de versiones. No se detectaron inconsistencias en los escenarios ejecutados después de la corrección descrita abajo.

| Área | Comprobación | Resultado |
| --- | --- | --- |
| SQLite | `PRAGMA integrity_check` y `foreign_key_check` en las conciliaciones y en copia de la base local. | `ok`, sin referencias inválidas. |
| Stock | Disponible/Reservado/Pendiente/Rechazado agregados = suma por lote = suma de movimientos; ningún saldo negativo. | Coinciden. |
| Conservación física | Comprado − vendido + devuelto = stock en ubicaciones + contenido en tránsito. | Coincide por producto. |
| Documentos y lotes | Cantidades de compras, bultos, ventas y devoluciones contrastadas con asignaciones; producto del lote correcto; acumulados por detalle y lote no exceden lo vendido. | Coinciden. |
| Logística | Secuencia de estados, estado actual, última transición y remito; expiraciones y rechazos conservan bloqueos. | Sin divergencias. |
| Caja e históricos | Detalles = total de venta = cobros = comprobante; reintegro al precio original y exactamente un egreso por devolución con importe positivo. | Sin duplicación ni diferencias. |
| Cuatro reportes | Totales contrastados con documentos y saldos independientes, pagos mixtos, márgenes históricos, vencidos y decisiones de bultos. | Coinciden. |
| Compras sugeridas | Recepción consistente con proveedor/CD/productos/cantidades; solo una compra por sugerencia; cancelación no crea stock. | Correcto. |
| Concurrencia | Dos procesos independientes intentan vender seis unidades cada uno de un stock de diez; dos hilos reciben la misma sugerencia; dos devoluciones compiten por el mismo lote. | Solo una operación se confirma en cada competencia; sin sobreventa ni duplicación. |
| Fallos tardíos | Fallar tras descontar lote, tras insertar egreso, tras cerrar sugerencia y tras crear lotes en migración. Se compara el estado persistido completo antes/después. | Rollback completo; la migración puede reintentarse. |
| Migración poblada | Versión 2 con bultos en los seis estados, venta con pago mixto y devoluciones vendible/no vendible. Comparación de tablas originales y continuación posterior de operaciones. | Conserva datos y permite continuar sobre lotes de origen desconocido. |
| Persistencia e interfaz | Generar sugerencia, recibir compra/lote, logística, venta, devolución, cuatro reportes, CSV y reapertura. | Las pruebas de interfaz pasan. |

## Secuencias reproducibles

Se ejecutan tres secuencias de **72 pasos**, con semillas 41, 2026 y 314159. Cada paso elige compras, bultos, logística, ventas, devoluciones, generación/recepción/cancelación de sugerencias u operaciones inválidas. Los pasos sin una operación aplicable no inventan movimientos. Después de cada paso se concilian documentos, libros, saldos y reportes; se reabre la base durante cada secuencia.

| Semilla | Compras finales | Bultos | Ventas | Devoluciones | Lotes | Sugerencias |
| --- | --- | --- | --- | --- | --- | --- |
| 41 | 10 | 7 | 15 | 8 | 20 | 4 |
| 2026 | 14 | 11 | 11 | 4 | 30 | 8 |
| 314159 | 11 | 7 | 19 | 9 | 23 | 4 |

La conciliación vive en `tests/soporte_integridad.py`; las secuencias y regresiones en `tests/test_integridad_sistema.py`. `tests/worker_concurrencia.py` comprueba procesos separados, sin compartir el Singleton del proceso principal.

## Hallazgo corregido

En productos nuevos, una compra podía usar el código `LEGADO-SIN-IDENTIFICAR`, reservado por las reglas a la migración, porque solo se rechazaba si ya existía un lote legado para ese producto. Ahora se rechaza ese identificador normalizado en cualquier compra nueva. La regresión verifica también que no queden compra, stock, costos ni movimientos parciales tras el rechazo.

## Base local y límites

`data/inventario.sqlite3` estaba en versión 0 y **sin operaciones ni catálogo**. Se leyó en modo solo lectura y se obtuvo una copia consistente mediante la API de backup SQLite. La copia pasó a versión 3 y superó ambas verificaciones de integridad; el SHA-256 del archivo original permaneció igual durante la prueba. Esto comprueba estructura y actualización de esa base vacía; los casos poblados se comprobaron con datos sintéticos reproducibles, no con operaciones reales de terceros.

Se conservan los límites del incremento: sin series por unidad, recepción parcial, destrucción/recuperación de vencidos ni cancelación de bultos. Un vencimiento puede dejar mercadería reservada o pendiente bloqueada; no se falsifica una rotura de precinto ni se habilita venta para resolverlo. Los promedios económicos siguen redondeados al centavo y no se presentan como contabilidad de precisión ilimitada. No se garantiza ausencia de errores en escenarios no probados.

## Repetir la revisión

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m pytest tests/test_integridad_sistema.py -q -s
```
