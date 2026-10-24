# Plan del trabajo práctico

Actualizado: 22/10/2026. Rama: `codex/plan-avance-tp`.

## Criterios confirmados

- Completar y verificar todos los procesos obligatorios antes de abordar opcionales.
- SQLite 3 obligatorio; frontend necesario para demostrar funcionamiento. Se eligió Tkinter/ttk para una aplicación local sencilla.
- State confirmado por el grupo. State y DAO están implementados; se apunta a aproximadamente tres patrones en total, sin incorporar abstracciones innecesarias.
- Las dudas del análisis se resuelven con decisiones simples por autorización del usuario; no se espera una aprobación docente para continuar. Véase [decisiones de implementación](decisiones_implementacion.md).
- Los incrementos toman también como base las [referencias de patrones, interfaz y reportes de la cátedra](referencias_catedra.md), revisadas el 23/10/2026. Se conserva Tkinter/ttk y la separación de presentación, negocio y datos.

## Incremento ejecutable

Se implementaron catálogo y ubicaciones, precios, mínimos, compra recibida, orden por local, preparación con reserva, precintado, despacho, recepción y verificación/rechazo. La interfaz permite recorrer esos procesos y consultar inventario, contenido e historial. Una orden admite atención parcial; cada bulto tiene su propio remito.

Se verificaron persistencia, duplicados, validaciones de stock, secuencia State, rechazo, historial inmutable, reversión ante fallo, concurrencia y formularios con pruebas automatizadas. El README documenta comandos de ejecución y demostración.

Documentación vigente:

- [Casos de uso](casos_uso.md): incluye también el diseño de los procesos comerciales pendientes.
- [Modelo de objetos](modelo_clases.md): catálogo, logística y previsión comercial.
- [Modelo de datos SQLite 3](modelo_datos.md): tablas implementadas y restricciones.
- [Análisis del dominio](analisis_dominio.md): base de requisitos y razonamiento.

## Siguientes incrementos obligatorios

| Orden | Trabajo | Criterio de cierre |
| --- | --- | --- |
| 1 | Costo de inventario y transferencia, venta con varios productos, cobro y comprobante interno | Precio/costo histórico conservados; cantidades agregadas no superan Disponible; detalle, stock, caja y comprobante se confirman juntos; frontend permite demostrarlo. |
| 2 | Devolución vinculada a venta y detalle original | Cantidades acumuladas controladas, reintegro al precio original y condición de mercadería diferenciada; stock/caja se actualizan juntos. |
| 3 | Cuatro reportes no triviales | Ventas/ingresos por período/local/medio, ranking y margen, existencias/mínimos y rechazos por precinto; agregaciones contrastadas con datos conocidos. |
| 4 | Revisión de patrones, diagramas y recorrido integral | Justificación de los patrones seleccionados y demostración compra → reposición → recepción → venta → devolución → reportes desde frontend con persistencia tras reiniciar. |

La valorización promedio ponderada propuesta debe concretarse antes de calcular margen, conservando costos en transferencias y detalles históricos de venta. Tener costos de compra guardados todavía no acredita ese cálculo.

Las operaciones históricas no se eliminan. No se incluyen por ahora cancelación de bultos, retorno de rechazados ni recuperación de mercadería: requieren un proceso explícito antes de habilitarse. La administración ofrece alta y modificación, sin borrado de registros referenciados.

## Segunda parte

Una vez consolidado el alcance obligatorio, elegir opcionales de uno en uno: compras sugeridas por faltantes; promociones/descuentos/listas de precios; lotes/series/vencimientos; clientes frecuentes/cuentas corrientes/beneficios; inventario físico y conciliación. No se compromete la implementación de todos ni se adelantan para justificar patrones.

## Criterio del README

Incluir información general, funcionalidades implementadas, resultados, consultas y diagramas del TP. No incluir seguimiento personal u organizativo, informes de avance ni prioridades del grupo. Describir resultados reales sin presentar diseños pendientes como código terminado.
