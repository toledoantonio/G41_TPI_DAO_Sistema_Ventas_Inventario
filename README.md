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
- Compras recibidas en el CD con varios productos y costos históricos.
- Órdenes de reposición por local, con productos consolidados y atención parcial.
- Preparación de bultos con reserva de stock, un remito por bulto y precinto único.
- Despacho, recepción, verificación o rechazo, con historial inmutable y patrón State.
- Inventario por ubicación con Disponible, Reservado, Pendiente y Rechazado; persistencia SQLite 3 y operaciones atómicas.

La interfaz utiliza Tkinter/ttk. Ventas, cobros, comprobantes, devoluciones y los reportes restantes todavía no están implementados.

## Ejecución

Requiere Python 3.11 o superior con Tkinter y SQLite 3 (incluidos en la instalación habitual de Python para Windows). No requiere paquetes de pip. Ejecutar desde la raíz del repositorio:

```powershell
python -m backend.main
```

Los datos se guardan en `data/inventario.sqlite3`. Para utilizar datos ficticios en una base separada:

```powershell
python -m backend.main --demo
```

La primera apertura de una base de demostración vacía carga un CD, un local, un producto, una compra de 20 unidades y un bulto precintado de 10. Las siguientes aperturas conservan las operaciones realizadas. Se puede elegir otro archivo con `--db ruta/al/archivo.sqlite3`.

En Windows se puede abrir **iniciar.cmd** con doble clic para usar la base normal, o **demo.cmd** para usar la demostración. Desde PowerShell:

```powershell
.\iniciar.cmd --demo
```

El iniciador CMD utiliza un runtime local disponible o Python instalado y admite los argumentos `--demo`, `--db` y `--help`. No ejecuta scripts de PowerShell ni modifica su política de ejecución. Si aparece el mensaje «la ejecución de scripts está deshabilitada», se estaba intentando abrir `iniciar.ps1`; utilizar `iniciar.cmd` o `demo.cmd`.

Para probar el flujo, en **Bultos y remitos** seleccionar el bulto, despacharlo y recibirlo en Local Centro. Registrar recepción mantiene 10 unidades pendientes y cero disponibles en el local. Introducir `PRECINTO-DEMO-01` y verificar: bulto y remito quedan Verificados y las 10 pasan a Disponible. Si se marca precinto roto y se indica un motivo, quedan Rechazadas.

## Verificación

```powershell
python -m unittest discover -v
```

Las pruebas usan bases temporales y verifican persistencia, historial, estados, rechazo, duplicados, sobreasignación, transacciones, concurrencia y formularios de interfaz. Las pruebas de interfaz requieren Tk disponible.

## Patrones de diseño

**State:** Bulto delega sus acciones en EstadoBulto y sus seis estados concretos. Cada estado determina la transición válida o rechaza la operación.

**DAO:** ProductoDAO, BultoDAO, CatalogoDAO, OperacionesDAO y ConsultasDAO concentran el acceso a SQLite. Los servicios comparten una transacción entre los DAOs participantes.

Son los dos patrones aplicados; DAO es un patrón de acceso a datos, no un patrón GoF. Todavía no hay un tercer patrón incorporado. La [justificación técnica](docs/patrones.md) identifica participantes, archivos y pruebas.

## Alcance del enunciado

- Administrar locales y Centro de Distribución.
- Administrar productos, categorías, precios, mínimos de existencia y proveedores.
- Consolidar necesidades de locales en órdenes de reposición con origen y destino.
- Preparar bultos con remito y precinto, registrar su despacho y recibirlos verificando el precinto.
- Registrar ventas, cobros, comprobantes y devoluciones con impacto en stock y caja.

### Reglas principales

- El stock del destino solo queda disponible cuando el remito y el contenedor están verificados. Un precinto roto implica rechazo y no habilita la venta.
- Mantener trazabilidad inmutable de los estados del bulto: Preparado, Precintado, En tránsito, Recibido y Verificado/Rechazado.
- No vender por encima del stock disponible y verificado.
- Evitar productos y proveedores duplicados según los identificadores definidos.
- Validar que las devoluciones correspondan a ventas registradas y cumplan las reglas establecidas.

### Integrantes del grupo

| Legajo | Apellido y Nombre |
| --- | --- |
| 81864 | Toledo, Antonio |
| 95433 | De la Vega, Ezequiel |
| 402587 | Sutara, Facundo |
| 408591 | Flores, Brian Benjamin |
