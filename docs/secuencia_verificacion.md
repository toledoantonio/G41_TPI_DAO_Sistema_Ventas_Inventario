# Secuencia de verificación y transacción

Colaboración implementada entre frontend, servicio, dominio y DAOs. Todos los DAOs usan la conexión de la misma transacción. El bloque de error representa una excepción en cualquier paso: los pasos posteriores no se ejecutan y los cambios previos se revierten.

```mermaid
sequenceDiagram
    actor Operador
    participant UI as Aplicacion
    participant S as Sistema
    participant DB as BaseDatos
    participant BD as BultoDAO
    participant B as Bulto
    participant E as Recibido
    participant OD as OperacionesDAO
    participant CD as CatalogoDAO
    Operador->>UI: Verificar bulto con precinto observado
    UI->>S: verificar(bulto, local, precinto, roto, motivo)
    S->>DB: transaccion() / BEGIN IMMEDIATE
    S->>BD: obtener(bulto)
    BD-->>S: Bulto reconstruido y datos del remito
    Note over BD,B: Ultimo historial debe coincidir con estado actual
    S->>CD: ubicacion(local, LOCAL)
    Note over S: Validar que el local sea el destino
    S->>B: verificar(precinto, roto)
    Note over B,E: Codigo distinto integro lanza error antes de delegar
    B->>E: verificar(self, roto)
    E->>B: cambiar_estado(Verificado o Rechazado)
    Note over S: Exigir motivo si se rechaza
    S->>OD: cambiar_estado_remito()
    S->>BD: contenido(bulto)
    loop Por producto del bulto
        S->>OD: estado_remito()
        Note over S: Habilitar solo si bulto y remito estan Verificados
        S->>CD: mover(Pendiente a Disponible o Rechazado)
    end
    S->>BD: registrar_estado(bulto, anterior, fecha, evidencia)
    alt Operacion completa
        S->>DB: commit
        S-->>UI: confirmacion
        UI-->>Operador: estado e inventario actualizados
    else Error en cualquier paso
        S->>DB: rollback
        S-->>UI: error sin confirmar cambios
        UI-->>Operador: mensaje de rechazo de la operacion
    end
```

El historial, el remito y el inventario no se confirman separadamente. La prueba de fallo al insertar historial comprueba que los cambios de remito/saldos se revierten. Un bulto ya Verificado o Rechazado no vuelve a llegar a las escrituras: State rechaza la repetición.

Fuente editable: [secuencia_verificacion.mmd](diagramas/secuencia_verificacion.mmd). Casos de prueba: [test_logistica.py](../tests/test_logistica.py).
