"""Modo «Centro de operaciones» en vivo.

Los agentes y los correos son simulados: el flujo reproduce el corpus de escenarios con variaciones.
La defensa es real: la capa 1 (`reglas_inyeccion`), la capa 2 (`politica_origen`), la bóveda de
indicadores y el clasificador que aprende corren de verdad sobre cada evento.

Módulos:
    flujo        genera los correos desde `scamshield/scenarios/{es,en}`, con variaciones.
    lectura      marca los tramos del cuerpo con las funciones de origen de la capa 2.
    boveda       indicadores de compromiso (cuentas, dominios y plantillas).
    clasificador regresión logística en línea con señales y hashing de texto (numpy).
    motor        orquesta a los agentes y emite los eventos del contrato.
"""
