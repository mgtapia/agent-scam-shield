# Grifter

**Red-teaming y escudo para agentes de IA que pagan.**

Un agente puede recibir una factura, un correo del jefe o una llamada con una cuenta falsa e intentar pagar. Grifter pone la verificación fuera del modelo: revisa de dónde salió cada dato y retiene la acción cuando no puede comprobar que el dueño la autorizó.

## Cómo funciona

1. **Firewall técnico:** revisa inyecciones y fugas con Pipelock configurado.
2. **Política de origen:** un destino que solo aparece en un correo, una web o una herramienta externa necesita la confirmación del dueño. Con un mandato definido, también se comprueba que el cobro coincida con lo aprobado.
3. **Titular de la cuenta:** cuando existe un registro de titulares, contrasta la identidad del beneficiario con la cuenta inscrita.

El dueño puede resolver una alerta con un toque. Grifter se integra como proxy MCP o mediante un SDK Python; la política de origen es determinista y no depende del acierto de un clasificador.

## Qué construimos

- Un benchmark reproducible de estafas ficticias en español chileno e inglés.
- Un atacante adaptativo y un clasificador que aprende de los casos confirmados.
- Una demo web con operaciones en vivo, episodios de evaluación y resultados.

Las cifras, sus fuentes y sus límites están en [docs/cifras.md](https://github.com/platanus-hack/platanus-hack-26-cl-team-40/blob/main/docs/cifras.md). Los resultados miden este corpus simulado; no prometen cubrir cualquier estafa.

**[Prueba la demo](https://grifter.onrender.com)** · [Código e instalación](https://github.com/platanus-hack/platanus-hack-26-cl-team-40)

Equipo 40: Matías Tapia y Matías Ramírez. Platanus Hack 26: Santiago ft. Buk, track AI Security.
