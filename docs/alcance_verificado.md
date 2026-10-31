# Cobertura del trabajo práctico

Revisión del 31/10/2026 contra el código, el esquema SQLite y los procesos de la consigna.

## Procesos obligatorios

| Proceso | Cobertura real | Falta o límite |
| --- | --- | --- |
| 1. Administrar sucursales y CD | Alta y modificación desde frontend; jerarquía `Ubicacion` → `CentroDistribucion` / `Local`; código único y un CD central | No hay borrado/inactivación. No se borra historia. |
| 2. Administrar catálogo, categorías, precios, mínimos y proveedores | Alta/modificación, precios en centavos, mínimo por producto/ubicación y control de códigos duplicados | Sin listas de precios, promociones ni descuentos, que son opcionales. |
| 3. Consolidar necesidades en orden | Una orden por local (`OrdenReposicion`), varios productos, renglones consolidados y atención parcial | Decisión simple adoptada: no hay órdenes multilocal. |
| 4. Preparar bultos, remito y precinto | Contenido con varios productos y costo histórico de transferencia (`ContenidoBulto`), reserva, remito por bulto y precinto único | Contenido fijo al preparar; sin cancelación ni edición de bultos. |
| 5. Registrar despacho desde CD | Salida de reservado, transición En tránsito e historial atómicos | No incluye transporte externo ni seguimiento geográfico. |
| 6. Recibir y verificar precinto | Valida local destino, mantiene Pendiente, verifica o rechaza con remito, transfiere costo promedio ponderado al local y registra movimientos conjuntos | Código distinto íntegro queda bloqueado. |
| 7. Venta, cobro, comprobante y devolución | **Ventas, cobros, caja, comprobantes y devoluciones implementados.** Pestañas 6 y 7; devolución al detalle original, cantidad acumulada y condición inspeccionada. | Mismo local, referencia única, reintegro completo del detalle devuelto al precio original; sin pasarela ni recuperación de mercadería bloqueada. |
| Integración de compras del contexto | Compra recibida en CD (`Compra`, `DetalleCompra`), proveedor, detalles/costos históricos, entrada de stock y cálculo de costo promedio ponderado | Sin pagos a proveedores ni recepción parcial, según alcance mínimo adoptado. |

## Validaciones y mínimos de entrega

| Requisito | Cobertura |
| --- | --- |
| Disponible solo después de verificar remito y contenedor | Implementado y probado. Un remito por bulto evita resultados mixtos. |
| Precinto roto rechaza y no habilita venta | El inventario queda Rechazado, no aumenta Disponible ni altera el costo promedio del local. |
| Historial inmutable del bulto | Triggers impiden UPDATE/DELETE; estado e historial se guardan juntos y se contrastan al recuperar. |
| No vender por encima de Disponible | **Implementado y probado.** `Venta` consolida renglones por producto y valida contra el stock `disponible` del local antes de confirmar. |
| Evitar productos/proveedores duplicados | Códigos normalizados y únicos; validaciones en objetos de dominio, servicios y SQLite. |
| Devolución vinculada a venta y reglas | **Implementado y probado:** pertenencia, mismo local, acumulados, condiciones, precio/costo original, reintentos, rollback y concurrencia. |
| Al menos dos patrones | **Cumplido:** **State** (GoF), **Singleton** (GoF) y **DAO** aplicados, documentados y probados con `pytest`. |
| Al menos cuatro reportes no triviales | **Implementado y probado:** cuatro reportes con agregaciones, filtros y CSV; [definiciones y cálculos](reportes.md). |
| SQLite 3 y frontend | Implementados: `sqlite3` y `Tkinter/ttk`. |

Correcciones verificadas: costos fijos de reservas separados del promedio Disponible; conservación de valor en compras intercaladas con transferencias y ventas; reconstrucción transaccional/versionada de costos anteriores, con reapertura y rollback; configuración única que rechaza otra ruta e inicialización concurrente protegida. Véanse [regresiones](../tests/test_costos_migracion.py) y [límites de migración y redondeo](modelo_datos.md#migración-de-costos).

## Verificación del incremento y cierre

Las pruebas de devoluciones/reportes contrastan cantidades e importes conocidos, pago mixto sin duplicar ventas, devoluciones de otro período, existencias cero y tasas de rechazo de bultos con varios productos. La prueba integral de interfaz recorre compra demo → logística → venta → devolución → cuatro reportes/CSV → reapertura. También se prueba la actualización de versión 1 a 2 sin alterar ventas ni costos.

Pendiente del grupo: revisión humana de la presentación final, ensayo de exposición y comprobación del entorno de entrega. Los opcionales siguen fuera de este incremento.

## Documentación actualizada

- [DER y diccionario de datos implementados](modelo_datos.md): tablas, atributos, claves y cardinalidades.
- [Clases implementadas](modelo_clases.md): objetos Python y dependencias reales.
- [Modelo conceptual](modelo_conceptual.md): conceptos del dominio.
- [Estados del bulto](ciclo_bulto.md): transiciones y guardas.
- [Secuencia de verificación](secuencia_verificacion.md): colaboración de State, DAO y transacción.
- [Patrones](patrones.md): problema, participantes, ubicación y pruebas de State, Singleton y DAO.
