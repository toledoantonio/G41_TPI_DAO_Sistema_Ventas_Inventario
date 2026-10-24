# Referencias de cátedra para patrones, interfaz y reportes

Revisión: 23/10/2026. Material complementario aportado en las carpetas externas `dao/Patrones de Diseño` y `dao/Interfaces - UX`. La consigna del TPI y las aclaraciones del usuario conservan prioridad sobre ejercicios particulares. Los ejemplos no agregan requisitos obligatorios al TPI.

## Material consultado

Los números son posiciones de página dentro de cada PDF. Se inspeccionó el contenido/temario de los siete PDFs y se leyeron las secciones indicadas; no se declara auditado cada ejemplo ni ejecutados los proyectos externos. Se revisaron visualmente la página 3 de la guía de patrones, la 14 de Patrones y la 16 del material de Tkinter para contrastar código/diagramas con el texto extraído.

| Fuente en la carpeta dao | Lectura relevante | Uso en el TPI |
| --- | --- | --- |
| `Patrones de Diseño/Guia_Patrones_Strategy_State_Iterator_Python.pdf` | Completa, 7 páginas | Polimorfismo, contexto/estado, algoritmos intercambiables y recorrido encapsulado. |
| `Patrones de Diseño/TP_Patrones_Strategy_State_Iterator.pdf` | Completo, 4 páginas | Operaciones incompatibles de State; comparación con Strategy/Iterator. Sus ejercicios de descuentos y recargos no se trasladan como reglas de ventas del TPI. |
| `Patrones de Diseño/Semana 10. Patrones_Strategy_State_Iterator.pdf` | Conceptos y ejemplos, pp. 5-6 y 9-16 | Distribución de responsabilidades y diferenciación entre State, Strategy e Iterator. |
| `Patrones de Diseño/Patrones.pdf` | Conceptos, pp. 4-6, 9 y 14-15 | Describir nombre, problema, solución, consecuencias y ejemplo. Singleton, Factory y Observer se evalúan según necesidad. |
| `Interfaces - UX/Interfaz grafica.pdf` | Introducción, validación y ttk, pp. 1-2, 7-8 y 13-16 | Tkinter, eventos, Treeview, Combobox, Notebook, Scrollbar y tema clam, ya presentes en la aplicación. |
| `Interfaces - UX/Interfaz_grafica_flet.pdf` | Objetivos, eventos, clases y capas, pp. 1 y 3-6 | Presentación que colabora con negocio y datos, controles separados de valores y manejadores de eventos. |
| `Interfaces - UX/Reportes en Python.pdf` | Completo, 4 páginas | ReportLab para documentos/tablas, Matplotlib para gráficos y csv para exportación tabular. Son opciones para el incremento de reportes. |

Se inspeccionaron además ejemplos Python de `patrones/patrones/`: Singleton, Factory, Observer y el caso Observer-Singleton con SQLite. En `Interfaz_Grafica_Flet/Interfaz_Grafica_Flet/` se revisaron formularios, menú modal, tema, configuración de dependencias y el ABM de alumnos (presentación, negocio y datos).

## Interfaz: correspondencia con la implementación

La elección actual de **Tkinter/ttk** coincide con una de las alternativas enseñadas. La otra guía y el proyecto ABM usan Flet; su estructura de colaboración es aprovechable sin exigir cambiar de framework.

| Pauta observada | Aplicación actual / criterio para continuar |
| --- | --- |
| Controles y eventos | `Formulario` conserva variables/widgets; los callbacks leen entradas, llaman servicios y muestran resultados. Mantener los manejadores breves. |
| Presentación → negocio → datos | `frontend/app.py` → `backend/services/sistema.py` y dominio → `backend/daos/`. Mantener SQL fuera de los eventos y reglas del dominio fuera de las pantallas. |
| Validación | Validación de negocio en servicios/objetos, aun si la pantalla añade avisos por campo o validación al escribir. Una restricción de teclado no sustituye comprobar la operación. |
| Acciones y resultados claros | Conservar Nuevo/Guardar/Editar, renglones visibles, errores comprensibles y confirmación después de guardar. Identificar el registro que se está editando. |
| Tema compartido | El ejemplo `tema.py` concentra estilo. Cuando crezca la interfaz, separar estilos/espaciados de construcción de formularios, manteniendo el aspecto que ya funciona. |
| Composición y reutilización | Usar componentes pequeños para formularios/tablas. Heredar de Frame para construir widgets Tkinter no equivale a heredar de clases de negocio. |
| Código legible | Clases en PascalCase, métodos/variables en snake_case, anotaciones de tipos y docstrings en contratos relevantes. Aplicar gradualmente a los módulos que se amplíen. |

El `pyproject.toml` del ejemplo Flet declara Python >=3.12, Flet y flet-desktop fijados a 1.0.4, Ruff y Pyright con configuración estricta. Son datos del ejemplo local inspeccionado, no una comprobación de versiones actuales del framework ni requisitos nuevos del TPI. Este proyecto conserva Python >=3.11 y no incorpora las dependencias de Flet. Tampoco copia sintaxis exclusiva de Python 3.12 en módulos que deben funcionar con 3.11.

## State: coincidencia conceptual y diferencia de implementación

La guía, pp. 3-5, usa un estado que recibe el contexto y ejecuta `pedido.cambiar_estado(...)`. El contexto delega con `self.estado.avanzar(self)`; el método del estado no devuelve el siguiente estado.

El código actual del TPI usa otra forma: `Bulto` delega en el objeto de estado y conserva el siguiente objeto que ese estado devuelve. Por ejemplo, `Precintado.despachar()` devuelve `EnTransito()`. Los estados siguen controlando las acciones permitidas y la pantalla no elige libremente el próximo estado.

Esta diferencia se conserva documentada; no se presenta el código del TPI como una copia literal del ejemplo docente. Una eventual adaptación al estilo de contexto pasado como argumento debe mantener las mismas pruebas, encapsular el cambio y actualizar los diagramas. No hace falta modificar reglas de negocio para adoptar esa forma.

En el ejemplo se usa ABC/abstractmethod; la base actual `EstadoBulto` implementa rechazo por defecto para las acciones incompatibles. Ambas decisiones deben explicarse al presentar el patrón: el contrato común, la delegación y las seis clases concretas son identificables en el código real.

## Otros patrones

- **DAO:** se mantiene para separar persistencia. El ejemplo ABM confirma la colaboración presentación-negocio-datos, aunque use nombres DataLayer/BusinessLayer. No es necesario renombrar carpetas o clases para conservar esa separación.
- **Observer:** candidato concreto para futuras vistas de inventario, logística y reportes que necesiten reaccionar de forma independiente a cambios confirmados. El ejemplo define Subject, suscripción y Observer con update. La lista actual de callbacks de refresco no se contabiliza como implementación formal del patrón. Notificar después del commit; los cambios obligatorios de stock nunca dependen de un observador opcional.
- **Strategy:** evaluar solo si aparecen algoritmos alternativos reales. No adelantar promociones ni recargos por medios de pago para copiar el ejercicio. Un cálculo único de costo promedio tampoco necesita estrategias intercambiables.
- **Iterator:** recorrer listas con for no se presenta como un patrón propio del grupo. Solo justificar un iterador específico si encapsula un recorrido necesario que la solución simple no ofrece.
- **Singleton/Factory:** los ejemplos sirven para comprender estructura; no obligan a convertir la conexión en global ni el mapa de reconstrucción de State en Factory Method.

Se mantienen **State y DAO aplicados** y el objetivo aproximado de tres patrones. La selección del tercero continúa pendiente de una necesidad concreta, con Observer como candidato a revisar al ampliar consumidores de cambios.

## Reportes

El material muestra salida PDF con ReportLab, gráficos incorporados desde Matplotlib y exportación CSV. Para el TPI, primero obtener consultas correctas con agregaciones/filtros y datos históricos; después sumar su presentación o exportación. La existencia de una tabla o un archivo PDF no demuestra por sí misma un reporte no trivial.

Si se incorporan PDF/gráficos, declarar las dependencias y verificar los archivos producidos. CSV es una opción de la biblioteca estándar. El código del material se toma como orientación: conservar estilos explícitos, cerrar figuras y validar resultados antes de reutilizarlo. Estas opciones no están implementadas todavía ni se declaran obligatorias por aparecer en el apunte.

## Aplicación a los próximos incrementos

Mantener el alcance obligatorio primero. Para ventas/devoluciones: reglas y cantidades en objetos/servicios, persistencia en DAOs, y formularios orientados a registrar y consultar operaciones. Al incorporar reportes, reutilizar consultas verificadas, separar exportación de cálculo y volver a evaluar la necesidad del tercer patrón.

Esta revisión incorpora referencias y criterios técnicos a la documentación; no cambia el framework, los patrones aplicados ni el comportamiento del programa.
