"""Grifter sobre MCP real: un proxy que aplica la capa 2 y dos servidores de prueba.

- `proxy`: se pone entre el agente y los servidores MCP de abajo y retiene los pagos cuyo destino
  solo apareció en contenido no confiable.
- `servidor_proveedor`: el portal ficticio de Silicio Austral, con un modo envenenado.
- `servidor_banco`: un banco sandbox que solo anota los pagos en un JSONL.
"""
