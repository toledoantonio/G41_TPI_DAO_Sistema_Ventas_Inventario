# Patrones aplicados

Revisión contra el código del 31/10/2026. Se encuentran aplicados **tres patrones**: **State** (GoF), **Singleton** (GoF) y **DAO** (acceso a datos). Con ello se cumple holgadamente el requisito obligatorio de aplicar al menos dos patrones de diseño y el objetivo de tres patrones planteado por el grupo.

Material complementario revisado: [referencias de cátedra](referencias_catedra.md). Tanto la clase abstracta `EstadoBulto(ABC)` y la transición mediante `contexto.cambiar_estado(...)` (Cap. 11.2 y Cap. 16.2) como la implementación de `BaseDatos` mediante `__new__`, `_instance`, `_initialized` y `reset_for_testing()` (Cap. 15.3 y Cap. 15.5.2) siguen la estructura de las guías docentes.

## 1. State: ciclo de vida del bulto (Cap. 16.2)

**Problema:** no todas las acciones son válidas en cualquier estado. No se puede despachar un bulto Preparado, recibirlo dos veces ni habilitar mercadería rechazada.

| Participante | Implementación | Responsabilidad |
| --- | --- | --- |
| Contexto | `Bulto` en [entidades.py](../backend/models/entidades.py) | Conserva identidad, precinto, contenido y estado actual; expone `cambiar_estado()` y delega las acciones pasando `self` al estado. |
| Contrato común | `EstadoBulto(ABC)` en [estados_bulto.py](../backend/patterns/estados_bulto.py) | Clase base abstracta (`ABC` con `@abstractmethod`) que expone `precintar`, `despachar`, `recibir` y `verificar`, rechazando por defecto acciones incompatibles. |
| Estados concretos | `Preparado`, `Precintado`, `EnTransito`, `Recibido`, `Verificado` y `Rechazado` | Cada estado habilita su operación e invoca `contexto.cambiar_estado(...)` con el siguiente estado permitido. |
| Reconstrucción | `recuperar_estado()` | Traduce el nombre persistido al objeto de estado. |
| Coordinación | `Sistema._operar_bulto()` en [sistema.py](../backend/services/sistema.py) | Valida ubicación/evidencia y coordina remito, inventario e historial en una transacción. |

Pruebas: `test_estado_bulto_es_clase_abstracta`, `test_patron_state_transiciones_en_bulto`, `test_state_rechaza_saltos_y_operaciones_duplicadas`, `test_codigo_precinto_distinto_sigue_pendiente` y `test_precinto_roto_no_habilita_ni_retorna_cd` en [test_logistica.py](../tests/test_logistica.py).

## 2. Singleton: gestor único de base de datos (Cap. 15.3 y 15.5.2)

**Problema:** garantizar que todos los componentes del sistema utilicen una única instancia del gestor de configuración y conexiones SQLite (`BaseDatos`), evitando reinicializaciones redundantes del esquema en cada invocación.

| Participante | Implementación | Responsabilidad |
| --- | --- | --- |
| Singleton | `BaseDatos` en [config.py](../backend/database/config.py) | Retiene la única instancia en el atributo de clase `_instance`, controla su creación sobrescribiendo `__new__(cls, ruta=None)` y protege la inicialización única mediante `_initialized`. |
| Acceso y pruebas | `obtener_instancia()` y `reset_for_testing()` | Proporciona punto de acceso de clase y método de limpieza para aislar pruebas unitarias (Cap. 15.5.2). |

Pruebas: `test_patron_singleton_base_datos` en [test_logistica.py](../tests/test_logistica.py).

La configuración es única **por proceso**. Las rutas se expanden y resuelven antes de compararlas; solicitar otra base produce `ValueError` sin alterar el gestor existente ni crear el archivo solicitado. Un `RLock` protege creación e inicialización concurrentes. Cada operación abre su propia conexión SQLite: no se comparte una conexión entre hilos. `reset_for_testing()` solo se usa para aislar pruebas; para cambiar de base en uso normal se reinicia la aplicación. Las pruebas de rutas y concurrencia están en [test_costos_migracion.py](../tests/test_costos_migracion.py).

## 3. DAO: acceso a datos (Cap. 13.10)

**Problema:** guardar/recuperar documentos y saldos sin introducir SQL en objetos de dominio ni formularios.

| Implementación | Responsabilidad |
| --- | --- |
| [ProductoDAO](../backend/daos/producto_dao.py) | Guarda y obtiene productos. |
| [BultoDAO](../backend/daos/bulto_dao.py) | Reconstruye `Bulto` con su `Remito` y `ContenidoBulto`, contrasta estado con historial y persiste transiciones. |
| [CatalogoDAO](../backend/daos/catalogo_dao.py) | Accede a ubicaciones, categorías, proveedores, mínimos y movimientos/saldos con cálculo de costo promedio ponderado. |
| [OperacionesDAO](../backend/daos/operaciones_dao.py) | Persiste compras, órdenes, remitos y contenido; consulta cantidades por asignar. |
| [VentaDAO](../backend/daos/venta_dao.py) | Persiste y reconstruye ventas, detalles históricos de venta, cobros, comprobantes y movimientos de caja. |
| [DevolucionDAO](../backend/daos/devolucion_dao.py) | Originales, acumulados y documentos de devolución. |
| [ReportesDAO](../backend/daos/reportes_dao.py) | Consultas agregadas de los cuatro reportes sobre una instantánea compartida. |
| [ConsultasDAO](../backend/daos/consultas_dao.py) | Ejecuta lecturas para las tablas de la interfaz. |

`Sistema` abre una operación mediante el Singleton `BaseDatos` y entrega la misma conexión transaccional a los DAOs participantes. Ningún DAO hace commit por su cuenta.

Pruebas: `test_fallo_en_historial_revierte_estado_remito_y_stock`, `test_fallo_en_comprobante_revierte_venta_stock_y_caja`, `test_recorrido_persistencia_historial_y_reconciliacion` y `test_dos_preparaciones_concurrentes_no_sobreasignan`.

Diagramas: [clases implementadas](modelo_clases.md), [ciclo de vida](ciclo_bulto.md) y [secuencia de verificación](secuencia_verificacion.md).

Los opcionales añaden `LoteDAO` y `CompraSugeridaDAO` para persistencia y consultas. FEFO es una única política de selección, no se presenta como otro patrón Strategy. Las necesidades de compra se calculan mediante `NecesidadCompra`; no se agrega un patrón para aumentar el conteo.
