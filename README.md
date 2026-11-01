# G41 - TPI - Sistema de Ventas e Inventario

Trabajo Práctico Integrador de **Desarrollo de Aplicaciones con Objetos**, Ingeniería en Sistemas de Información. **Grupo 41 — 2026**. Tema 3: Sistema de Ventas e Inventario, Centro de Distribución a Locales.

## Análisis del dominio

[Entidades, relaciones, reglas de negocio y modelo conceptual](docs/analisis_dominio.md).

- [Casos de uso de los procesos obligatorios](docs/casos_uso.md).
- [Modelo conceptual del dominio](docs/modelo_conceptual.md).
- [Diagrama de clases implementadas](docs/modelo_clases.md).
- [DER con atributos, claves y cardinalidades](docs/modelo_datos.md).
- [Ciclo de vida del bulto](docs/ciclo_bulto.md).
- [Secuencia de verificación](docs/secuencia_verificacion.md).
- [Patrones aplicados y ubicación en el código](docs/patrones.md).
- [Cobertura de requisitos obligatorios](docs/alcance_verificado.md).
- [Definiciones y filtros de los cuatro reportes](docs/reportes.md).
- [Dos opcionales: compras sugeridas y lotes/vencimientos](docs/opcionales.md).

## Funcionalidades implementadas

- Alta y modificación de locales, Centro de Distribución, categorías, productos, precios y proveedores.
- Mínimos por producto y ubicación, con consulta de faltantes incluso cuando el saldo es cero.
- Compras recibidas en el CD con varios productos, costos históricos y cálculo de **costo promedio ponderado**.
- Órdenes de reposición por local, con productos consolidados y atención parcial.
- Preparación de bultos con reserva de stock, captura de costo de transferencia, un remito por bulto y precinto único.
- Despacho, recepción, verificación o rechazo, con historial inmutable, transferencia de costo promedio al local y patrón **State**.
- **Ventas en locales** con uno o varios productos consolidados, validación contra stock disponible y verificado, conservación de precios y costos históricos, cobros simples o mixtos por medio de pago, movimientos de caja y emisión de comprobante interno.
- Inventario por ubicación con Disponible, Reservado, Pendiente, Rechazado y Costo Promedio; persistencia SQLite 3 con gestor **Singleton** y operaciones atómicas.
- **Devoluciones parciales vinculadas a ventas:** cantidades acumuladas, referencia única, reintegro al precio original y reingreso vendible o bloqueado, con stock y caja en una transacción.
- **Cuatro reportes no triviales** con agregaciones, filtros y exportación CSV: ventas/ingresos, ranking/margen, existencias/mínimos y rechazos por precinto.
- **Órdenes de compra sugeridas por faltantes** de locales y CD, con cobertura de pedidos/envíos/compras pendientes, recepción completa vinculada a una compra real y cancelación sin borrar documentos.
- **Lotes con vencimiento opcional**, selección FEFO, bloqueo de vencidos para venta y trazabilidad en compras, bultos y devoluciones. No incluye series individuales.

La aplicación está desarrollada en **Python**, con interfaz de escritorio **Tkinter/ttk** (`frontend/`) y persistencia en **SQLite 3**.

## Ejecución

Requiere Python 3.10 o superior con Tkinter y SQLite 3 (incluidos en la instalación habitual de Python para Windows). Ejecutar desde la raíz del repositorio:

```powershell
python -m backend.main
```

Los datos se guardan en `data/inventario.sqlite3`. Para utilizar datos ficticios en una base separada:

```powershell
python -m backend.main --demo
```

En Windows se puede abrir **iniciar.cmd** con doble clic para usar la base normal, o **demo.cmd** para usar la demostración. Desde PowerShell:

```powershell
.\iniciar.cmd --demo
```

Para probar el flujo completo:

1. En **4. Logística** seleccionar el bulto, despacharlo y recibirlo en Local Centro (mantiene 10 unidades pendientes y cero disponibles).
2. Introducir `PRECINTO-DEMO-01` y verificar: bulto y remito quedan Verificados y las 10 unidades pasan a Disponible en el local con su costo promedio transferido.
3. En **6. Ventas y caja** seleccionar Local Centro, agregar productos, registrar el cobro (o usar *Saldar resto con medio seleccionado*) y confirmar la venta para emitir el comprobante interno y actualizar stock y caja.
4. En **7. Devoluciones → Nueva devolución**, seleccionar la venta y pulsar **Cargar venta**. Seleccionar un detalle original, indicar cantidad y condición e incorporarlo; completar referencia única, motivo y medio de reintegro y confirmar. **Historial y consulta** permite recuperar el documento. Una devolución no vendible queda bloqueada y no se puede volver a vender.
5. En **8. Reportes**, elegir uno de los cuatro reportes, filtros y **Generar reporte**. El filtro de medio afecta solo la sección de caja. Existencias muestra la situación actual y no admite fechas históricas. Cada sección tiene una pestaña; el resultado puede exportarse a CSV.
6. Cerrar y reabrir con la misma base: ventas, devoluciones, caja e inventario se conservan. La carga inicial de demo no vuelve a repetirse.

Para los opcionales, configurar mínimos y abrir **9. Compras / lotes**. Consultar faltantes, elegir proveedor y generar una sugerencia. **Preparar recepción en Compras** vincula la orden con la pestaña 2; ingresar allí sus productos/cantidades y costos/lotes reales para recibirla. Los lotes se registran en cada renglón de compra, con vencimiento opcional. La segunda sección de la pestaña 9 muestra saldos y trazabilidad. Véanse las [reglas y límites](docs/opcionales.md).

En inventario, **Disponible registrado** es el saldo físico; **Vendible** descuenta lotes vencidos y es la cantidad usada para vender y calcular faltantes. Vencer no elimina unidades ni crea una merma automática. Las bases anteriores se actualizan a versión 3 con saldos identificados como legado de origen desconocido, sin inventar fechas ni lotes históricos.

## Verificación

Instalar la dependencia de pruebas (la aplicación no requiere paquetes externos):

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

Las pruebas están escritas con `pytest` (Cap. 12) usando bases temporales y verifican modelos de dominio (encapsulamiento, composición, herencia, clases abstractas `ABC` y patrón `Singleton`), persistencia, costos promedio ponderados, ventas, cobros, comprobantes, historial, estados, rechazo, duplicados, sobreasignación, transacciones, concurrencia y formularios de interfaz.

El costo promedio mostrado corresponde al **Disponible**. Los bultos conservan su costo desde la preparación; una compra posterior no revaloriza lo reservado. Los promedios se redondean al centavo con `ROUND_HALF_UP`.

Al abrir una base anterior se reconstruyen los costos desde compras y movimientos registrados, en una migración transaccional y versionada. Se conservan cantidades y documentos históricos. Si faltan respaldos o los saldos no coinciden, la apertura informa el problema y revierte la migración; véanse los [criterios de migración](docs/modelo_datos.md#migración-de-costos).

## Patrones de diseño

- **State (Cap. 16.2):** `Bulto` delega sus acciones en `EstadoBulto(ABC)` y sus seis estados concretos. Cada estado determina la transición válida e invoca `contexto.cambiar_estado(...)` o rechaza la operación.
- **Singleton (Cap. 15.3):** `BaseDatos` garantiza una única instancia del gestor de conexiones y transacciones SQLite mediante `__new__`, `_instance`, `_initialized` y `reset_for_testing()`.
- **DAO (Cap. 13.10):** `ProductoDAO`, `BultoDAO`, `CatalogoDAO`, `OperacionesDAO`, `VentaDAO`, `DevolucionDAO`, `ReportesDAO`, `LoteDAO`, `CompraSugeridaDAO` y `ConsultasDAO` concentran el acceso a SQLite compartiendo la transacción del servicio.

La [justificación técnica](docs/patrones.md) identifica participantes, archivos y pruebas.

### Integrantes del grupo

| Legajo | Apellido y Nombre |
| --- | --- |
| 81864 | Toledo, Antonio |
| 95433 | De la Vega, Ezequiel |
| 402587 | Sutara, Facundo |
| 408591 | Flores, Brian Benjamin |
