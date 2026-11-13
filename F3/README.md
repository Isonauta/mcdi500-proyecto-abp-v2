# Fase 3 · Desarrollo: núcleo algorítmico, eficiencia y POO

Entrega: Sumativa 2 (20 %), miércoles 18-nov-2026, 23:59.

La Fase 3 no cambia los datos ni el resultado de la Fase 2: reorganiza el mismo pipeline en piezas que se pueden probar, medir y reutilizar.

| Archivo | Contenido |
|---|---|
| `F3_Nucleo.ipynb` | Notebook de la fase: de funciones a clases, pipeline, verificación de equivalencia con la F2, eficiencia y validación |

## Cómo ejecutarlo

```bash
python scripts/run_all.py        # entorno, pruebas y notebooks de F1, F2 y F3, en orden
jupyter lab F3/F3_Nucleo.ipynb   # de forma interactiva
```

El notebook compara su resultado con `data/processed/ordenes.csv`, que genera `F2/04_transformacion.ipynb`. Por eso la F2 debe ejecutarse antes; `run_all.py` respeta ese orden.

## Dónde está el código

El notebook no contiene lógica propia: importa los módulos de `src/pipeline/`.

| Módulo | Responsabilidad |
|---|---|
| `ordenes.py` | Funciones del pipeline de la Fase 2: cada una hace una tarea y no guarda estado |
| `anonimizacion.py` | Funciones para anonimizar a los proveedores que son personas naturales |
| `transformers.py` | Clase base `Transformer` y los pasos que aprenden de los datos: `OutlierFlagger`, `TopSupplierMarker`, `SupplierAnonymizer`; y `FunctionStep`, que adapta una función |
| `flujo.py` | `OrdersPipeline`: encadena los pasos, los ejecuta en orden y lleva una bitácora |

## Criterio de diseño

Un paso es una clase solo si aprende algo de los datos y lo usa después. Los que no aprenden nada siguen siendo funciones y entran al pipeline por un adaptador.

| Principio o patrón | Dónde se ve |
|---|---|
| Herencia | Las cuatro clases de `transformers.py` heredan de `Transformer` |
| Polimorfismo | `OrdersPipeline` llama a `fit`, `transform` y `summary` sin distinguir la clase de cada paso |
| Encapsulamiento | Lo aprendido queda en atributos internos, se expone como copia y no se puede transformar antes de ajustar |
| *Template Method* | `Transformer.fit` y `transform` fijan el esqueleto; cada hija completa `_learn` y `_apply` |
| *Adapter* | `FunctionStep` da a una función la interfaz de un transformador |
