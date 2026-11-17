# Referencias de cátedra para patrones, interfaz y reportes

Revisión: 27/10/2026. Material complementario aportado en las guías semanales (Capítulos 7 al 16) y carpetas `dao/Patrones de Diseño` y `dao/Interfaces - UX`. La consigna del TPI y las aclaraciones del usuario conservan prioridad sobre ejercicios particulares. Los ejemplos no agregan requisitos obligatorios al TPI.

## Material consultado

| Fuente de cátedra | Lectura relevante | Uso en el TPI |
| --- | --- | --- |
| Capítulos 7, 8, 9 y 10 (Clases, Encapsulamiento, Composición y Herencia) | Completos | Clases con `__init__`, `@property`/setters, `__str__`/`__eq__`, composición con listas internas inicializadas vacías (`Compra`, `OrdenReposicion`, `Bulto`) y herencia (`Ubicacion` → `CentroDistribucion` / `Local`). |
| Capítulo 11 y 16 (Polimorfismo, `ABC` y Patrones State y Strategy) | Completos | `EstadoBulto(ABC)` con `@abstractmethod` y transición delegada mediante `contexto.cambiar_estado(...)`. |
| Capítulo 12 (Testing unitario con `pytest`) | Completo | Pruebas organizadas en clases `Test...` usando `assert` y `with pytest.raises(...)`. |
| Capítulo 13 y 14 (SQLite3, Patrón DAO y Context Managers) | Completos | Uso de `with`, `@contextmanager`, `sqlite3.Row`, placeholders `?`, transacciones con `commit`/`rollback` y separación en DAOs. |
| `Interfaces - UX/Interfaz grafica.pdf` y `Interfaz_grafica_flet.pdf` | Introducción, validación y ttk | Tkinter, eventos, Treeview, Combobox, Notebook, Scrollbar y separación presentación → negocio → datos. |
| `Interfaces - UX/Reportes en Python.pdf` | Completo, 4 páginas | ReportLab para documentos/tablas, Matplotlib para gráficos y csv para exportación tabular. |

## Interfaz: correspondencia con la implementación

La elección actual de **Tkinter/ttk** coincide con una de las alternativas enseñadas.

| Pauta observada | Aplicación actual / criterio para continuar |
| --- | --- |
| Controles y eventos | `Formulario` conserva variables/widgets; los callbacks leen entradas, llaman servicios y muestran resultados. Mantener los manejadores breves. |
| Presentación → negocio → datos | `frontend/app.py` → `backend/services/sistema.py` y dominio → `backend/daos/`. Mantener SQL fuera de los eventos y reglas del dominio fuera de las pantallas. |
| Validación | Validación de negocio en objetos del dominio (setters/métodos) y servicios. |
| Acciones y resultados claros | Conservar Nuevo/Guardar/Editar, renglones visibles, errores comprensibles y confirmación después de guardar. |
| Composición y reutilización | Usar componentes pequeños para formularios/tablas. |
| Código legible | Clases en PascalCase, métodos/variables en snake_case y docstrings en contratos relevantes. |

## State: alineación con la guía de clase

Siguiendo los Capítulos 11.2 y 16.2 de la guía de clase:
1. `EstadoBulto` hereda de `ABC` (`from abc import ABC, abstractmethod`) y declara `@abstractmethod` en su propiedad `nombre`, impidiendo instanciar la clase abstracta directamente.
2. El contexto `Bulto` expone `cambiar_estado(nuevo_estado)` y delega las operaciones pasando `self` como argumento (`self._estado.despachar(self)`).
3. Cada estado concreto (`Preparado`, `Precintado`, `EnTransito`, `Recibido`, `Verificado`, `Rechazado`) valida si la acción está permitida e invoca `contexto.cambiar_estado(...)` para efectuar la transición.

## Otros patrones

- **DAO:** se mantiene para separar persistencia (Cap. 13.10).
- **Observer:** candidato concreto para futuras vistas de inventario, logística y reportes que necesiten reaccionar de forma independiente a cambios confirmados.
- **Strategy:** evaluar al implementar cobros, políticas de precios o reportes si aparecen algoritmos alternativos reales (Cap. 16.3).
- **Singleton:** aplicado en `BaseDatos` como gestor único de configuración por proceso; cada operación conserva su propia conexión. Rechaza cambios de ruta y protege la inicialización concurrente; las pruebas se aíslan mediante reinicio explícito del gestor.

## Reportes

Para el TPI, primero obtener consultas correctas con agregaciones/filtros y datos históricos; después sumar su presentación o exportación.

### Comprobación del incremento del 31/10/2026

Se volvieron a leer las cuatro páginas de `dao/Interfaces - UX/Reportes en Python.pdf` y las dos páginas de `dao/TPI-tema3.pdf`. Se contrastaron visualmente la página 4 del apunte (CSV) y la página 2 de la consigna (reportes y requisitos mínimos).

| Fuente | Pauta observada | Aplicación en el incremento |
| --- | --- | --- |
| Consigna, p. 2 | Al menos cuatro reportes no triviales; sugiere ventas/ingresos, ranking/margen, existencias/mínimos y rechazos por precinto, entre otros. | Se implementan esas cuatro familias, con filtros, sumas, agrupaciones, rankings, tasas y valoración histórica contrastadas con datos conocidos. |
| Apunte, pp. 1–2 | Ejemplo de informe PDF con título, texto y tabla usando ReportLab; permite adaptar el contenido y formato. | Los resultados tienen título, notas, secciones y tablas. No se afirma haber implementado ese ejemplo PDF. |
| Apunte, pp. 2–3 | Ejemplo de gráfico Matplotlib incorporado a un PDF. | La pestaña Gráfico presenta los mismos resultados filtrados mediante barras en Tkinter. |
| Apunte, p. 4 | Presenta `csv` de la biblioteca estándar como opción suficiente para lectura/escritura básica de datos tabulares. | Exportación CSV con filtros, notas, encabezados, secciones e importes. No requiere dependencias adicionales de ejecución. |

La consigna deja abierto el formato de presentación. La aplicación ofrece gráficos y tablas en Tkinter/ttk y exportación CSV. Las definiciones y decisiones del grupo se detallan en [reportes](reportes.md). La comprobación funcional incluye pruebas de servicios, interfaz, exportación, datos vacíos, filtros, pagos mixtos sin duplicación, devoluciones de otro período y persistencia tras reabrir.

## Aplicación a los próximos incrementos

Mantener el alcance obligatorio primero. Para ventas/devoluciones: modelar las clases del dominio con encapsulamiento (`@property`) y composición (lista de detalles inicializada vacía en `__init__` y método `agregar_detalle`), persistencia en DAOs, formularios orientados a registrar y consultar operaciones, y pruebas unitarias escritas con `pytest`.
