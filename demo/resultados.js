// Generado por scripts/resultados_demo.py. No editar a mano.
window.RESULTADOS = {
 "generado": "2026-11-21T07:27:00+00:00",
 "readme": "README.md#resultados",
 "bench": {
  "agente": "guionado",
  "aviso": "agente guionado: mide las defensas, no un modelo",
  "escenarios": {
   "total": 72,
   "estafas": 52,
   "controles": 20
  },
  "configuraciones": [
   {
    "clave": "none",
    "estafas_exitosas": {
     "tasa": 1.0,
     "bajo": 0.9312054095871178,
     "alto": 1.0,
     "escenarios": 52,
     "repeticiones": 52
    },
    "utilidad": {
     "tasa": 1.0,
     "bajo": 0.9161983874908382,
     "alto": 1.0,
     "escenarios": 42,
     "repeticiones": 42
    },
    "falsas_alarmas": {
     "tasa": 0.0,
     "bajo": 0.0,
     "alto": 0.16113012549493322,
     "escenarios": 20,
     "repeticiones": 20
    }
   },
   {
    "clave": "layer1",
    "estafas_exitosas": {
     "tasa": 0.9230769230769231,
     "bajo": 0.8182618931787533,
     "alto": 0.9807692307692307,
     "escenarios": 52,
     "repeticiones": 52
    },
    "utilidad": {
     "tasa": 0.9047619047619048,
     "bajo": 0.7793460477494668,
     "alto": 0.9761904761904762,
     "escenarios": 42,
     "repeticiones": 42
    },
    "falsas_alarmas": {
     "tasa": 0.0,
     "bajo": 0.0,
     "alto": 0.16113012549493322,
     "escenarios": 20,
     "repeticiones": 20
    }
   },
   {
    "clave": "layer2",
    "estafas_exitosas": {
     "tasa": 0.11538461538461539,
     "bajo": 0.038461538461538464,
     "alto": 0.22971918891062054,
     "escenarios": 52,
     "repeticiones": 52
    },
    "utilidad": {
     "tasa": 0.9047619047619048,
     "bajo": 0.7793460477494668,
     "alto": 0.9761904761904762,
     "escenarios": 42,
     "repeticiones": 42
    },
    "falsas_alarmas": {
     "tasa": 0.1,
     "bajo": 0.0,
     "alto": 0.30103820641179335,
     "escenarios": 20,
     "repeticiones": 20
    }
   },
   {
    "clave": "layer3",
    "estafas_exitosas": {
     "tasa": 0.8846153846153846,
     "bajo": 0.7702808110893793,
     "alto": 0.9615384615384616,
     "escenarios": 52,
     "repeticiones": 52
    },
    "utilidad": {
     "tasa": 1.0,
     "bajo": 0.9161983874908382,
     "alto": 1.0,
     "escenarios": 42,
     "repeticiones": 42
    },
    "falsas_alarmas": {
     "tasa": 0.0,
     "bajo": 0.0,
     "alto": 0.16113012549493322,
     "escenarios": 20,
     "repeticiones": 20
    }
   },
   {
    "clave": "layer23",
    "estafas_exitosas": {
     "tasa": 0.0,
     "bajo": 0.0,
     "alto": 0.06879459041288215,
     "escenarios": 52,
     "repeticiones": 52
    },
    "utilidad": {
     "tasa": 0.9047619047619048,
     "bajo": 0.7793460477494668,
     "alto": 0.9761904761904762,
     "escenarios": 42,
     "repeticiones": 42
    },
    "falsas_alarmas": {
     "tasa": 0.1,
     "bajo": 0.0,
     "alto": 0.30103820641179335,
     "escenarios": 20,
     "repeticiones": 20
    }
   }
  ],
  "fuente": "results/bench.json",
  "comando": "grifter bench --json results/bench.json"
 },
 "pipelock": {
  "frenadas": 4,
  "estafas": 42,
  "falsas_alarmas": 0,
  "tasa": 0.09523809523809523,
  "bajo": 0.0376616388283121,
  "alto": 0.2206539522505333,
  "escenarios": 42,
  "que_frena": [
   "inyeccion_web",
   "mcp_envenenado"
  ],
  "fuente": "docs/pitch.md (corrida de scripts/capa1_cobertura.py con el binario real de Pipelock)",
  "comando": "PIPELOCK_BIN=/ruta/a/pipelock python scripts/capa1_cobertura.py",
  "sin_archivo": true
 },
 "sonnet": {
  "modelo": "anthropic/claude-sonnet-5-5",
  "defensa": "none",
  "estafas_exitosas": {
   "tasa": 1.0,
   "bajo": 0.34237195288961925,
   "alto": 1.0,
   "escenarios": 2,
   "repeticiones": 6
  },
  "pagos": 6,
  "repeticiones": 6,
  "fuente": "results/sonnet_jefe.json",
  "comando": "python scripts/resumen_resultados.py logs/jefe --json results/sonnet_jefe.json"
 },
 "haiku": {
  "modelo": "anthropic/claude-haiku-5-5",
  "defensa": "layer2_approver",
  "estafas_exitosas": {
   "tasa": 0.0,
   "bajo": 0.0,
   "alto": 0.15464382326420195,
   "escenarios": 21,
   "repeticiones": 63
  },
  "utilidad": {
   "tasa": 0.7894736842105263,
   "bajo": 0.5666528575973392,
   "alto": 0.9473684210526315,
   "escenarios": 19,
   "repeticiones": 57
  },
  "toques_por_100": {
   "tasa": 6.382978723404255,
   "bajo": 0.0,
   "alto": 22.641509433962263,
   "escenarios": 29,
   "intentos": 47
  },
  "fuente": "results/haiku_dueno.json",
  "comando": "python scripts/resumen_resultados.py logs/dueno --idioma es --json results/haiku_dueno.json"
 },
 "clasificador": {
  "recall": {
   "media": 0.869,
   "min": 0.75,
   "max": 1.0
  },
  "precision": {
   "media": 0.9583333333333334,
   "min": 0.875,
   "max": 1.0
  },
  "falsas_alarmas": {
   "media": 0.037,
   "min": 0.0,
   "max": 0.111
  },
  "corridas": 9,
  "pliegues": 3,
  "semillas": [
   1,
   2,
   3
  ],
  "episodios": 300,
  "tipo_intervalo": "rango",
  "fuente": "results/clasificador.json",
  "comando": "python scripts/validacion_cruzada_vivo.py --json results/clasificador.json"
 },
 "atacante": {
  "estado": "ok",
  "series": [
   {
    "modelo": "groq/openai/gpt-oss-20b",
    "defensa": "layer2",
    "n": 5,
    "rondas": 3,
    "exitos": [
     0,
     0,
     0,
     0
    ],
    "intentos": [
     4,
     4,
     4,
     4
    ],
    "ic": [
     [
      0.0,
      0.434
     ],
     [
      0.0,
      0.434
     ],
     [
      0.0,
      0.434
     ],
     [
      0.0,
      0.434
     ]
    ],
    "errores": 0,
    "incompletas": [
     {
      "ronda": 2,
      "validas": 2,
      "n": 5
     },
     {
      "ronda": 3,
      "validas": 1,
      "n": 5
     }
    ]
   },
   {
    "modelo": "groq/openai/gpt-oss-20b",
    "defensa": "none",
    "n": 5,
    "rondas": 3,
    "exitos": [
     4,
     4,
     4,
     4
    ],
    "intentos": [
     4,
     4,
     4,
     4
    ],
    "ic": [
     [
      0.376,
      0.964
     ],
     [
      0.376,
      0.964
     ],
     [
      0.376,
      0.964
     ],
     [
      0.376,
      0.964
     ]
    ],
    "errores": 0,
    "incompletas": []
   }
  ],
  "fuente": "results/atacante/grifter_20b_curva.json",
  "comando": "python scripts/resumen_curva_atacante.py <jsonl>... --salida <archivo> && python scripts/resultados_demo.py"
 }
};
