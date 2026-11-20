# Arquitectura del proyecto

Qué hace cada componente, por qué está separado de los demás y cómo llegó a esta forma. Las decisiones sobre los datos están en [`decisiones.md`](decisiones.md) y la historia de cambios, en [`../changelog.md`](../changelog.md).

## Capas

El proyecto tiene tres capas. Cada una depende solo de la que tiene debajo.

| Capa | Dónde | Qué contiene | Qué no contiene |
|---|---|---|---|
| Presentación | `F1/` a `F4/` | Notebooks: texto, llamadas a funciones, tablas y figuras | Lógica propia: importan todo de `pipeline` |
| Ejecución | `scripts/` | Programas de línea de comandos: obtener datos, verificar el entorno, ejecutar todo, medir | Reglas de negocio |
| Lógica | `src/pipeline/` | Funciones y clases probadas con `pytest` | Rutas fijas, gráficos o texto para el lector |

**Por qué:** un notebook no se puede probar ni importar desde otro. Al dejar la lógica en un paquete, la misma función la usan el notebook, el script, la prueba y la integración continua, y existe en una sola versión.

## Componentes de `src/pipeline/`

| Módulo | Responsabilidad | Depende de | Por qué está separado |
|---|---|---|---|
| `config.py` | Rutas y semilla | — | Notebooks, scripts y pruebas se ejecutan desde carpetas distintas y deben llegar a los mismos archivos |
| `chilecompra.py` | Descargar, filtrar y congelar los datos de la fuente, con su huella SHA-256 | `anonimizacion` | Es lo único que conoce el formato y las direcciones de ChileCompra. Si la fuente cambia, se modifica este archivo |
| `anonimizacion.py` | Reemplazar a los proveedores personas naturales por un código estable | — | Se usa en dos momentos distintos: al congelar los datos y dentro del pipeline. No depende de ningún otro módulo |
| `ordenes.py` | Funciones del pipeline: ausentes, tipos, modalidad, una fila por orden, montos extremos, indicadores y validación | `chilecompra` | Cada función hace una tarea y no guarda estado. Es el pipeline de la Fase 2, intacto |
| `transformers.py` | Clase base `Transformer` y los pasos que aprenden de los datos | `ordenes`, `anonimizacion` | Agrupa lo que necesita recordar algo entre una llamada y otra |
| `flujo.py` | `OrdersPipeline`: ejecuta los pasos en orden y lleva una bitácora | `transformers`, `ordenes` | El orden de los pasos es una decisión aparte de lo que hace cada paso |
| `sinteticos.py` | Órdenes inventadas con la forma de la fuente, a partir de una semilla | `chilecompra`, `config` | Permite probar y medir sin tocar los datos reales |
| `medicion.py` | Medidor de tiempo y memoria, y tres pares de implementaciones para comparar | `ordenes` | Las versiones lentas existen solo para medir: el pipeline nunca las importa |
| `escalamiento.py` | Las mismas comparaciones sobre tamaños crecientes | `medicion`, `sinteticos`, `ordenes` | Separa la pregunta «cuál es más rápida» de «cómo cambia con el volumen» |

Ningún módulo de la lógica importa a `flujo`, `medicion` ni `escalamiento`: se pueden cambiar o quitar sin tocar el resto.

## Flujo de datos

```
ChileCompra (archivo mensual nacional)
   │  scripts/fetch_data.py · chilecompra.py · anonimizacion.py
   ▼
data/raw/            cuatro subconjuntos congelados, con SHA-256 (25.880 líneas de órdenes)
   │  ordenes.load_orders
   ▼
OrdersPipeline       normalize_missing → cast_types → classify_modality → aggregate_orders → OutlierFlagger
   │  flujo.build_orders_pipeline
   ▼
data/processed/ordenes.csv    una fila por orden (10.285 órdenes, 14 variables)
   │  ordenes.validate_orders (ocho reglas)
   ▼
Indicadores y figuras (F4)
```

Cada paso recibe una tabla y devuelve otra, sin modificar la que recibe. La bitácora del pipeline registra cuántas filas entran y salen de cada paso: las líneas se reducen solo en `aggregate_orders`, y ese es el único lugar donde debe ocurrir.

## Diseño de clases

**Criterio:** un paso es una clase solo si aprende algo de los datos y lo usa después. Los demás siguen siendo funciones.

```
Transformer            contrato fit / transform y control del estado
├── OutlierFlagger     aprende el límite de monto extremo
├── TopSupplierMarker  aprende quiénes son los mayores proveedores
├── SupplierAnonymizer aprende el código de cada proveedor persona natural
└── FunctionStep       adapta una función sin estado
```

| Principio | Dónde está | Fragmento |
|---|---|---|
| Herencia | Las cuatro clases heredan de `Transformer` y solo escriben `_learn` y `_apply` | `class OutlierFlagger(Transformer):` |
| Polimorfismo | El pipeline llama igual a todos los pasos, sin preguntar de qué clase son | `current = step.fit_transform(current) if learn else step.transform(current)` |
| Encapsulamiento | Lo aprendido vive en `_params`; hacia afuera se entrega una copia, y no se puede transformar antes de ajustar | `return dict(self._params)` |

**Por qué separar `fit` de `transform`:** el límite de monto extremo se aprende con un período y se aplica a otro. Así septiembre de 2025 se mide con la misma vara que septiembre de 2024. Si cada período calculara su propio límite, la comparación entre años mezclaría el cambio en los datos con el cambio en la vara.

## Patrones

| Patrón | Problema que había | Cómo lo resuelve | Qué habría pasado sin él |
|---|---|---|---|
| *Template Method* (`Transformer.fit` y `transform`) | Todos los pasos repiten lo mismo: revisar columnas, guardar lo aprendido, impedir que se transforme sin ajustar | La clase base fija esa secuencia y cada hija completa dos métodos | Cada clase repetiría las comprobaciones, y una que las olvidara fallaría en silencio |
| *Adapter* (`FunctionStep`) | Cuatro de los cinco pasos son funciones de la Fase 2 que no aprenden nada, y el pipeline espera objetos con `fit` y `transform` | Envuelve la función y le da esa interfaz | Habría que reescribir como clases cuatro funciones ya probadas, o dar al pipeline dos formas de llamar a un paso |

No se usan más patrones: el proyecto no los necesita.

## Cohesión y acoplamiento, con un caso

**Si cambia la regla de montos extremos, se modifica un archivo.** La regla está en `ordenes.extreme_amount_limit`. `OutlierFlagger` la llama, no la repite, y el pipeline, los notebooks y la validación usan la clase o la función. Lo mismo ocurre con la anonimización (`anonimizacion.py`) y con el formato de la fuente (`chilecompra.py`).

**Las clases no duplican lógica.** `OutlierFlagger._learn` tiene una línea: llama a la función que ya estaba probada. Por eso el pipeline con clases entrega exactamente el mismo archivo que las funciones encadenadas, y una prueba lo comprueba con `assert_frame_equal`.

## Recursión

No se usa. Los datos son tablas planas: no hay estructuras anidadas ni jerarquías que recorrer. El pipeline es una lista de pasos que se ejecuta con un ciclo, y la división del problema se hace por funciones.

## Pruebas

Un archivo de pruebas por módulo, en `tests/`. Cada uno cubre casos normales, casos límite y errores esperados.

| Qué se verifica | Dónde |
|---|---|
| Cada función del pipeline, incluidos los montos en cero, los datos sin montos positivos y un archivo ausente | `test_ordenes.py` |
| Que la copia congelada no cambió ni trae datos personales | `test_datos_congelados.py`, `test_anonimizacion.py` |
| Contrato de las clases y equivalencia con la Fase 2 | `test_f3_clases.py` |
| Que las versiones comparadas dan el mismo resultado | `test_eficiencia.py`, `test_escalamiento.py` |
| Que el generador sintético es reproducible | `test_sinteticos.py` |

`python scripts/run_all.py` ejecuta el entorno, las pruebas y todos los notebooks, y deja un registro en `docs/evidencias/`. La integración continua hace lo mismo en un equipo limpio en cada `push`.

## Evolución

| Fase | Qué había | Qué cambió | Por qué |
|---|---|---|---|
| F1 | Estructura por carpetas y entorno fijado | — | Poder ejecutar lo mismo en cualquier equipo desde el primer día |
| F2 | Funciones sin estado en `ordenes.py` y cinco notebooks | Se agregaron la anonimización y los montos extremos | Observaciones del docente a la primera entrega |
| F3 | Las mismas funciones | Clases para lo que aprende de los datos, pipeline con bitácora, mediciones | Comparar dos períodos con la misma vara; saber qué versión conviene y por qué |
| F4 | El mismo pipeline | Mediciones por tamaño, figuras e informe final | Comunicar los resultados y mostrar cómo escala el código |

El resultado de la Fase 2 no cambió en ninguna de las fases siguientes: una prueba compara el archivo que produce el pipeline actual con el de entonces.

## Fuentes

- Gamma, E., Helm, R., Johnson, R. y Vlissides, J. (1994). *Design patterns: Elements of reusable object-oriented software*. Addison-Wesley.
- The pandas development team. (2026). *pandas documentation*. https://pandas.pydata.org/docs/
- Python Software Foundation. (2026). *timeit: Measure execution time of small code snippets*. https://docs.python.org/3/library/timeit.html
- Python Software Foundation. (2026). *tracemalloc: Trace memory allocations*. https://docs.python.org/3/library/tracemalloc.html
