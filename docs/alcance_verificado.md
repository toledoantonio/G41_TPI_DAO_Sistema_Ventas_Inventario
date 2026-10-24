# Cobertura del trabajo práctico

Revisión del 22/10/2026 contra el código, el esquema SQLite y los procesos de la consigna. No representa un porcentaje de avance: los procesos comerciales y sus validaciones siguen siendo una parte sustancial de la entrega.

## Procesos obligatorios

| Proceso | Cobertura real | Falta o límite |
| --- | --- | --- |
| 1. Administrar sucursales y CD | Alta y modificación desde frontend; código único y un CD central | No hay borrado/inactivación. No se borra historia. |
| 2. Administrar catálogo, categorías, precios, mínimos y proveedores | Alta/modificación, precios en centavos, mínimo por producto/ubicación y control de códigos duplicados | Sin listas de precios, promociones ni descuentos, que son opcionales. |
| 3. Consolidar necesidades en orden | Una orden por local, varios productos, renglones consolidados y atención parcial | Decisión simple adoptada: no hay órdenes multilocal. |
| 4. Preparar bultos, remito y precinto | Contenido con varios productos, reserva, remito por bulto y precinto único | Contenido fijo al preparar; sin cancelación ni edición de bultos. |
| 5. Registrar despacho desde CD | Salida de reservado, transición En tránsito e historial atómicos | No incluye transporte externo ni seguimiento geográfico. |
| 6. Recibir y verificar precinto | Valida local destino, mantiene Pendiente, verifica o rechaza con remito y movimientos conjuntos | Código distinto íntegro queda bloqueado. Diferencias de contenido deben resolverse antes de confirmar conformidad; no hay proceso específico de conciliación. |
| 7. Venta, cobro, comprobante y devolución | **Pendiente de implementar** | Dominio, tablas, servicios, frontend, comprobante y pruebas comerciales. |
| Integración de compras del contexto | Compra recibida en CD, proveedor, detalles/costos históricos y entrada de stock | Sin pagos a proveedores ni recepción parcial, según alcance mínimo adoptado. |

## Validaciones y mínimos de entrega

| Requisito | Cobertura |
| --- | --- |
| Disponible solo después de verificar remito y contenedor | Implementado y probado. Un remito por bulto evita resultados mixtos. |
| Precinto roto rechaza y no habilita venta | El inventario queda Rechazado y no aumenta Disponible. El rechazo no vuelve automáticamente al CD. |
| Historial inmutable del bulto | Triggers impiden UPDATE/DELETE; estado e historial se guardan juntos y se contrastan al recuperar. |
| No vender por encima de Disponible | **Pendiente:** sin venta implementada no se declara cumplida esta validación. La reserva logística ya impide sobreasignar en CD. |
| Evitar productos/proveedores duplicados | Códigos normalizados y únicos; validaciones en aplicación y SQLite. |
| Devolución vinculada a venta y reglas | **Pendiente:** requiere originales, cantidades acumuladas, condición de mercadería y reintegro. |
| Al menos dos patrones | State y DAO aplicados; documentación de participantes y pruebas. Tercer patrón sin definir. |
| Al menos cuatro reportes no triviales | **Todavía no cumplido.** Hay una consulta agregada de compras y una consulta de inventario/mínimos; no se cuentan como cuatro reportes terminados. |
| SQLite 3 y frontend | Implementados: sqlite3 y Tkinter/ttk. |

## Orden de implementación pendiente

1. Definir y aplicar costo de inventario con conservación del costo en transferencias; guardar precio y costo históricos de venta.
2. Implementar venta de uno o varios productos, cantidades agregadas, cobro completo por medio(s), caja y comprobante interno, en una transacción.
3. Implementar devolución parcial vinculada al detalle original, acumulados, reintegro al precio original y reingreso vendible o bloqueado según condición.
4. Completar los cuatro reportes previstos: ventas/ingresos por período, local y medio; productos más vendidos y margen; existencias/mínimos; rechazos por precinto con agregaciones. Contrastar los resultados con datos conocidos.
5. Ampliar diagramas y pruebas con esos procesos y demostrar el recorrido integral desde el frontend, incluida la reapertura de la base.

Las funciones opcionales se abordan después: compras sugeridas, promociones, lotes/series/vencimientos, clientes/cuentas/beneficios e inventarios físicos/conciliación.

## Documentación actualizada

- [DER y diccionario de datos implementados](modelo_datos.md): tablas, atributos, claves y cardinalidades.
- [Clases implementadas](modelo_clases.md): objetos Python y dependencias reales.
- [Modelo conceptual](modelo_conceptual.md): conceptos del dominio y previsión comercial; no se confunde con clases programadas.
- [Estados del bulto](ciclo_bulto.md): transiciones y guardas.
- [Secuencia de verificación](secuencia_verificacion.md): colaboración de State, DAO y transacción.
- [Patrones](patrones.md): problema, participantes, ubicación y pruebas.
