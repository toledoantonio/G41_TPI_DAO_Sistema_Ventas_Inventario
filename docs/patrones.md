# Patrones aplicados

Revisión contra el código del 22/10/2026. Hay dos patrones aplicados: State y DAO. El objetivo del grupo de aproximadamente tres patrones continúa vigente; el tercero no fue seleccionado ni implementado.

Material complementario revisado el 23/10/2026: [referencias de cátedra](referencias_catedra.md). La guía docente de State pasa el contexto al estado; el TPI devuelve el siguiente objeto al contexto. La comparación y su fundamento están documentados allí. Observer queda como candidato a evaluar para vistas independientes; todavía no se declara implementado.

## State: ciclo de vida del bulto

**Problema:** no todas las acciones son válidas en cualquier estado. No se puede despachar un bulto Preparado, recibirlo dos veces ni habilitar mercadería rechazada.

| Participante | Implementación | Responsabilidad |
| --- | --- | --- |
| Contexto | `Bulto` en [entidades.py](../backend/models/entidades.py) | Conserva identidad, precinto y objeto de estado; delega acciones en ese objeto. |
| Contrato común | `EstadoBulto` en [estados_bulto.py](../backend/patterns/estados_bulto.py) | Expone precintar, despachar, recibir y verificar. Rechaza por defecto acciones incompatibles. Es una clase base Python, no una interfaz abstracta formal. |
| Estados concretos | Preparado, Precintado, EnTransito, Recibido, Verificado y Rechazado | Cada estado habilita su operación y devuelve el siguiente objeto de estado permitido. |
| Reconstrucción | `recuperar_estado()` | Traduce el nombre persistido al objeto de estado. El mapa no se contabiliza como otro patrón. |
| Coordinación | `Sistema._operar_bulto()` en [sistema.py](../backend/services/sistema.py) | Valida ubicación/evidencia y coordina remito, inventario e historial en una transacción. |

Ejemplo real: `Bulto.despachar()` llama a `self._estado.despachar()`. `Precintado` devuelve `EnTransito`; `Preparado` hereda el rechazo de la operación. El comportamiento cambia según el objeto de estado, no por una lista de strings interpretada desde la pantalla.

Los condicionales del servicio distinguen el caso de uso y sus efectos de inventario; la autorización de la transición queda en State. El patrón no sustituye la transacción ni la condición conjunta de verificación de remito y bulto.

Pruebas: `test_state_rechaza_saltos_y_operaciones_duplicadas`, `test_codigo_precinto_distinto_sigue_pendiente` y `test_precinto_roto_no_habilita_ni_retorna_cd` en [test_logistica.py](../tests/test_logistica.py).

## DAO: acceso a datos

**Problema:** guardar/recuperar documentos y saldos sin introducir SQL en objetos de dominio ni formularios.

| Implementación | Responsabilidad |
| --- | --- |
| [ProductoDAO](../backend/daos/producto_dao.py) | Guarda y obtiene productos. |
| [BultoDAO](../backend/daos/bulto_dao.py) | Reconstruye Bulto, contrasta estado con historial y persiste transiciones. |
| [CatalogoDAO](../backend/daos/catalogo_dao.py) | Accede a ubicaciones, categorías, proveedores, mínimos y movimientos/saldos. |
| [OperacionesDAO](../backend/daos/operaciones_dao.py) | Persiste compras, órdenes, remitos y contenido; consulta cantidades por asignar. |
| [ConsultasDAO](../backend/daos/consultas_dao.py) | Ejecuta lecturas para las tablas de la interfaz. |
| [BaseDatos](../backend/database/config.py) | Abre conexiones SQLite 3 con claves foráneas y controla confirmación/reversión de la transacción. |

`Sistema` abre una operación y entrega la misma conexión a los DAOs participantes. Ningún DAO hace commit por su cuenta. Por ejemplo, verificar un bulto persiste remito, movimientos, saldos y transición juntos; si falla el historial, todo se revierte.

DAO es un patrón de acceso a datos y **no pertenece al catálogo GoF**. Se cuenta aquí conforme al requisito literal de al menos dos patrones y al material de la materia que lo trata como patrón; no se afirma que haya dos patrones GoF aplicados.

Pruebas: `test_fallo_en_historial_revierte_estado_remito_y_stock`, `test_recorrido_persistencia_historial_y_reconciliacion` y `test_dos_preparaciones_concurrentes_no_sobreasignan`.

## Tercer patrón

No se incorporó un tercer patrón. `Sistema` es un servicio de aplicación; no se lo cuenta automáticamente como Facade. Tampoco se cuentan SQLite como Singleton, el mapa de estados como Factory Method ni la lista de refrescos de pantalla como Observer.

La selección restante se hará al implementar operaciones comerciales y reportes, si aparece una necesidad real. El TP exige como mínimo dos; el objetivo aproximado de tres del grupo no obliga a agregar complejidad artificial.

Diagramas: [clases implementadas](modelo_clases.md), [ciclo de vida](ciclo_bulto.md) y [secuencia de verificación](secuencia_verificacion.md).
