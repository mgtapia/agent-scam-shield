# Revisión de seguridad con Daybreak Blue

- **Fecha:** 2026-11-21
- **Alcance:** cambios locales de la rama `codex/cerrar-hallazgos-daybreak-172`, incluidos los archivos nuevos sin seguimiento.
- **Modelo y acceso:** `gpt-daybreak-blue-latest`, programa `daybreak_blue`, ejecutado mediante Codex CLI.
- **Método:** revisión estática. No se ejecutaron pruebas ni se modificó código durante la auditoría.

## Resultado

La revisión estática de Daybreak Blue no informó vulnerabilidades accionables. Una comprobación dinámica posterior reprodujo un **P1 que esa revisión no detectó**; su conclusión no bastaba para cerrar los hallazgos.

La revisión consideró la reconstrucción de credenciales Base64 fragmentadas en prosa y URL/form data; casos de falsos positivos y negativos; los cambios a la huella de política y a la ruta del registro de aprobaciones; la verificación antes de abrir conexiones y enviar credenciales; y el uso de conexiones después de aprobar cambios de servidores.

## Hallazgo posterior y corrección

**P1 — Conexión con configuración no aprobada.** Secuencia: aprobar una política; arrancar el proxy con un YAML que apunta a otro servidor; rechazar ese cambio; restaurar el YAML aprobado; reintentar la conexión mediante `tools/list`. La integridad comprobaba el archivo restaurado, pero la conexión utilizaba el servidor alterado retenido en memoria. La firma HMAC no evitaba esa divergencia.

La corrección compara la huella de toda la configuración efectiva en memoria con el registro aprobado y verificado antes de abrir cualquier transporte. Si difieren, retiene las conexiones y exige reiniciar con la configuración aprobada. La aprobación explícita aplica también dominios y rutas de política antes de volver a verificar. No reutiliza conexiones de servidores que acaban de cambiar.

`tests/test_integridad_conexiones.py` reproduce el rechazo → restauración → reintento, además de la restauración antes de la primera conexión, con stdio y HTTP, con y sin HMAC, y con servidores alterados o reglas debilitadas. Los 16 casos fallaban antes de la corrección. Comprueba que no hay procesos ni conexiones HTTP, que el registro aprobado no cambia y que un reinicio con el YAML aprobado recupera la conexión correcta.

La revisión independiente del reintento detectó además un **P2 de conexiones parciales**: si un segundo MCP fallaba, el primer contexto permanecía abierto y se duplicaba en el siguiente intento. Cada intento tiene ahora su propio contexto; un fallo cierra los transportes y restaura sesiones, rutas y herramientas antes del reintento. `tests/test_mcp_conexiones.py` cubre fallos en `initialize` y `list_tools` con contextos AnyIO reales.

## Limitaciones

El resultado original corresponde a una revisión estática del diff local y no cubre las correcciones posteriores aquí descritas. Las regresiones dinámicas verifican estas secuencias concretas; no constituyen una garantía de ausencia de otras vulnerabilidades.
