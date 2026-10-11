# Sistema de Ventas e Inventario

Trabajo Práctico Integrador 2026 de Desarrollo de Aplicaciones con Objetos, Ingeniería en Sistemas de Información. Tema 3: Centro de Distribución a Locales.

## Estado inicial

Este repositorio contiene la estructura inicial del proyecto. Los módulos Python son marcadores de lugar; todavía no se implementaron funcionalidades ni se eligieron el framework del frontend o el motor de base de datos.

## Estructura

```text
frontend/                       Interfaz de usuario (tecnología pendiente)
backend/
├── daos/                       Acceso y persistencia de datos
│   ├── bulto_dao.py
│   ├── producto_dao.py
│   └── venta_dao.py
├── database/
│   └── config.py               Configuración de la base de datos
├── models/
│   └── entidades.py            Entidades del dominio
├── patterns/                   Patrones de diseño
├── reports/
│   └── generador_reportes.py    Reportes del sistema
└── main.py                     Punto de entrada
```

Los archivos `__init__.py` identifican los paquetes Python y `.gitkeep` permite conservar carpetas todavía vacías en Git.

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

Se deberán aplicar al menos **dos patrones de diseño** e implementar al menos **cuatro reportes no triviales**. Su selección y diseño quedan pendientes.

Fuente principal: enunciado `TPI-tema3.pdf` proporcionado por el grupo. Este resumen orienta la estructura y no reemplaza la consigna original.
