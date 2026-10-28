# Plan del trabajo práctico

Actualizado: 27/10/2026. Rama: `codex/plan-avance-tp`.

## Criterios confirmados

- Completar y verificar todos los procesos obligatorios antes de abordar opcionales.
- SQLite 3 obligatorio; frontend necesario para demostrar funcionamiento. Se eligió Tkinter/ttk para una aplicación local sencilla.
- Patrones implementados: **State** (Cap. 16.2), **Singleton** (Cap. 15.3) y **DAO** (Cap. 13.10).
- Las dudas del análisis se resuelven con decisiones simples por autorización del usuario; no se espera una aprobación docente para continuar. Véase [decisiones de implementación](decisiones_implementacion.md).
- Los incrementos siguen la estructura y sintaxis de las guías semanales de la cátedra ([referencias de cátedra](referencias_catedra.md)): clases con encapsulamiento (`@property`), métodos mágicos (`__str__`, `__eq__`), composición con colecciones inicializadas vacías en `__init__`, herencia con `super()`, clases abstractas `ABC` y pruebas unitarias en `pytest`.

## Incremento ejecutable actual

Se implementaron y verificaron:
1. Catálogo y ubicaciones (`Ubicacion`, `CentroDistribucion`, `Local`, `Categoria`, `Proveedor`, `Producto`), precios y mínimos.
2. Compra recibida (`Compra`, `DetalleCompra`) con actualización de **costo promedio ponderado** en el CD.
3. Orden de reposición por local (`OrdenReposicion`, `DetalleReposicion`), preparación con reserva y captura del costo histórico de transferencia en `ContenidoBulto`, precintado, despacho, recepción y verificación/rechazo (`Bulto`, `Remito`, `EstadoBulto(ABC)`), transfiriendo el costo promedio ponderado al local al verificar.
4. **Incremento obligatorio 1 completado:** Venta con uno o varios productos (`Venta`, `DetalleVenta`), consolidación de cantidades, conservación de precio y costo histórico, cobro completo simple o mixto (`Cobro`), movimiento de caja (`movimiento_caja`) y emisión de comprobante interno (`Comprobante`), todo confirmado en una misma transacción y demostrable desde la pestaña **6. Ventas y caja** de la interfaz.

Documentación vigente:

- [Casos de uso](casos_uso.md): incluye el diseño de los procesos obligatorios.
- [Modelo de objetos](modelo_clases.md): catálogo, logística, ventas y patrones implementados.
- [Modelo de datos SQLite 3](modelo_datos.md): tablas implementadas y restricciones.
- [Análisis del dominio](analisis_dominio.md): base de requisitos y razonamiento.

## Siguientes incrementos obligatorios

| Orden | Trabajo | Estado / Criterio de cierre |
| --- | --- | --- |
| 1 | Costo de inventario y transferencia, venta con varios productos, cobro y comprobante interno | **Completado.** Precio/costo histórico conservados; cantidades agregadas no superan Disponible; detalle, stock, caja y comprobante se confirman juntos; frontend permite demostrarlo. |
| 2 | Devolución vinculada a venta y detalle original | **Pendiente.** Cantidades acumuladas controladas, reintegro al precio original y condición de mercadería diferenciada; stock/caja se actualizan juntos. |
| 3 | Cuatro reportes no triviales | **Pendiente.** Ventas/ingresos por período/local/medio, ranking y margen, existencias/mínimos y rechazos por precinto; agregaciones contrastadas con datos conocidos. |
| 4 | Revisión final y recorrido integral | **Pendiente.** Demostración compra → reposición → recepción → venta → devolución → reportes desde frontend con persistencia tras reiniciar. |

## Segunda parte

Una vez consolidado el alcance obligatorio, elegir opcionales de uno en uno: compras sugeridas por faltantes; promociones/descuentos/listas de precios; lotes/series/vencimientos; clientes frecuentes/cuentas corrientes/beneficios; inventario físico y conciliación.

## Criterio del README

Incluir información general, funcionalidades implementadas, resultados, consultas y diagramas del TP. Describir resultados reales sin presentar diseños pendientes como código terminado.
