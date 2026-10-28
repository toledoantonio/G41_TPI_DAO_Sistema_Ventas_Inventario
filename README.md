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

## Funcionalidades implementadas

- Alta y modificación de locales, Centro de Distribución, categorías, productos, precios y proveedores.
- Mínimos por producto y ubicación, con consulta de faltantes incluso cuando el saldo es cero.
- Compras recibidas en el CD con varios productos, costos históricos y cálculo de **costo promedio ponderado**.
- Órdenes de reposición por local, con productos consolidados y atención parcial.
- Preparación de bultos con reserva de stock, captura de costo de transferencia, un remito por bulto y precinto único.
- Despacho, recepción, verificación o rechazo, con historial inmutable, transferencia de costo promedio al local y patrón **State**.
- **Ventas en locales** con uno o varios productos consolidados, validación contra stock disponible y verificado, conservación de precios y costos históricos, cobros simples o mixtos por medio de pago, movimientos de caja y emisión de comprobante interno.
- Inventario por ubicación con Disponible, Reservado, Pendiente, Rechazado y Costo Promedio; persistencia SQLite 3 con gestor **Singleton** y operaciones atómicas.

La interfaz utiliza Tkinter/ttk. Las devoluciones comerciales y los reportes restantes se abordarán en los siguientes incrementos.

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
1. En **4. Bultos y remitos** seleccionar el bulto, despacharlo y recibirlo en Local Centro (mantiene 10 unidades pendientes y cero disponibles).
2. Introducir `PRECINTO-DEMO-01` y verificar: bulto y remito quedan Verificados y las 10 unidades pasan a Disponible en el local con su costo promedio transferido.
3. En **6. Ventas y caja** seleccionar Local Centro, agregar productos, registrar el cobro (o usar *Saldar resto con medio seleccionado*) y confirmar la venta para emitir el comprobante interno y actualizar stock y caja.

## Verificación

```powershell
python -m pytest -v
```

Las pruebas están escritas con `pytest` (Cap. 12) usando bases temporales y verifican modelos de dominio (encapsulamiento, composición, herencia, clases abstractas `ABC` y patrón `Singleton`), persistencia, costos promedio ponderados, ventas, cobros, comprobantes, historial, estados, rechazo, duplicados, sobreasignación, transacciones, concurrencia y formularios de interfaz.

## Patrones de diseño

- **State (Cap. 16.2):** `Bulto` delega sus acciones en `EstadoBulto(ABC)` y sus seis estados concretos. Cada estado determina la transición válida e invoca `contexto.cambiar_estado(...)` o rechaza la operación.
- **Singleton (Cap. 15.3):** `BaseDatos` garantiza una única instancia del gestor de conexiones y transacciones SQLite mediante `__new__`, `_instance`, `_initialized` y `reset_for_testing()`.
- **DAO (Cap. 13.10):** `ProductoDAO`, `BultoDAO`, `CatalogoDAO`, `OperacionesDAO`, `VentaDAO` y `ConsultasDAO` concentran el acceso a SQLite compartiendo la transacción del servicio.

La [justificación técnica](docs/patrones.md) identifica participantes, archivos y pruebas.

### Integrantes del grupo

| Legajo | Apellido y Nombre |
| --- | --- |
| 81864 | Toledo, Antonio |
| 95433 | De la Vega, Ezequiel |
| 402587 | Sutara, Facundo |
| 408591 | Flores, Brian Benjamin |
