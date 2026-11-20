# Trazabilidad: rúbrica → evidencia

La primera tabla corresponde a la entrega final (Sumativa 3). La segunda se conserva tal como quedó al entregar la Sumativa 1.

## Sumativa 3 (proyecto final, Fase 4)

Los 26 criterios de la rúbrica (150 puntos), en el orden de los apartados del informe. Estado al 2026-11-20.

| Apartado | Criterio (pts) | Evidencia en el repositorio | Estado |
|---|---|---|---|
| 1 | Portada e índice (3) | Informe | pendiente |
| 2 | Introducción y contextualización (6) | `F1/F1_Definición.ipynb` §1 · `README.md` | cumplido en el repositorio; falta el informe |
| 3 | Problemática y objetivos (6) | `F1/F1_Definición.ipynb` §2 a §5 | parcial: el notebook aún menciona las licitaciones |
| 4 | Herramientas científicas (9) | `src/pipeline/` · notebooks F1 a F4 · `requirements.txt` | cumplido |
| 5 | Reproducibilidad técnica (6) | `requirements.txt` · `docs/entorno.md` · `scripts/run_all.py` · `docs/evidencias/` · integración continua | cumplido; regenerar la evidencia al cerrar |
| 6 | Control de versiones (6) | Historial con ramas y *merge commit* · `.mailmap` · etiquetas de entrega | cumplido; repartir los commits de la Fase 4 |
| 7 | Documentación del proceso (6) | `docs/decisiones.md` · `changelog.md` · texto de los notebooks | cumplido |
| 8 | Repositorio GitHub (6) | Carpetas `F1/` a `F4/` · `README.md` · sección Contribuciones | parcial: `F4/` sin contenido |
| 10 | Codificación funcional (9) | `src/pipeline/ordenes.py` · `anonimizacion.py` · `tests/` | cumplido |
| 11 | Preprocesamiento del dataset (6) | `F2/03_limpieza.ipynb` · `F2/04_transformacion.ipynb` · `F2/05_validacion.ipynb` · `docs/decisiones.md` | cumplido |
| 12 | Validación técnica (6) | `tests/` (casos normales, límite y excepciones) · `tests/test_f3_clases.py` (regresión contra la F2) · `docs/evidencias/` | cumplido |
| 13 | Eficiencia y optimización (6) | `F3/F3_eficiencia.ipynb` · `F3/F3_escalamiento.ipynb` · `src/pipeline/medicion.py` · `escalamiento.py` | cumplido |
| 14 | Diseño estructurado (6) | `docs/arquitectura.md` · `src/pipeline/` | cumplido |
| 15 | Notebook final (3) | `F4/` · `scripts/run_all.py` | pendiente |
| 17 | Programación orientada a objetos (6) | `src/pipeline/transformers.py` · `flujo.py` · `F3/F3_Nucleo.ipynb` | cumplido |
| 18 | Documentación de arquitectura (6) | `docs/arquitectura.md` · `F3/README.md` | cumplido |
| 20 | Preprocesamiento para visualizar (6) | `F4/` | pendiente |
| 21 | Visualizaciones analíticas (6) | `F4/` · `F4/figuras/` | pendiente |
| 22 | Metodología (6) | Informe | pendiente |
| 23 | Validación y reflexión técnica (3) | Informe · `docs/arquitectura.md` (Evolución) | pendiente |
| 24 | Resultados (3) | Informe · `F4/` | pendiente |
| 25 | Discusión (3) | Informe | pendiente |
| 26 | Conclusiones (3) | Informe | pendiente |
| 27 | Trazabilidad de mejoras (3) | `changelog.md` (tabla de observaciones y mejoras) | cumplido; agregar la Fase 4 al cerrar |
| 28 | Presentación audiovisual (12) | Video en Canvas Studio · `F4/presentacion/` | pendiente |
| 29 | Aspectos formales (9) | Informe | pendiente |

Los apartados 9, 16 y 19 son encabezados de sección y no tienen puntaje propio.

### Verificación final antes de entregar
- [ ] `python scripts/run_all.py` termina sin errores desde un clon limpio y su registro queda en `docs/evidencias/`.
- [ ] La ejecución en GitHub Actions está en verde en `main`.
- [ ] Cada cifra del informe coincide con la salida del notebook que la produce.
- [ ] `git shortlog -sn` muestra tres autores, y los tres tienen commits de la Fase 4.
- [ ] `changelog.md` incluye la Fase 4 con sus commits.
- [ ] Etiqueta `entrega-s3` en el commit entregado.

## Sumativa 1 (Fases 1 y 2), entregada el 2026-11-11

Lista de verificación de los 15 criterios de la rúbrica de la Sumativa 1 (99 puntos). Cada fila indica dónde está la evidencia en el repositorio o en el informe. Se actualiza en cada avance y se revisa completa antes de la entrega.

| # | Criterio (pts) | Qué exige el nivel Excelente | Evidencia (archivo · commit · sección del informe) | Estado |
|---|---|---|---|---|
| 1 | Portada e índice (3) | Portada institucional completa e índice automático coherente | Informe, portada e índice | cumplido |
| 2 | Introducción y contextualización (6) | Contexto, situación que origina el análisis, relevancia, propósito y relación con F1–F4 | Informe II · `F1/F1_Definición.ipynb` §1 | cumplido |
| 3 | Problemática y objetivos (6) | Problemática delimitada, pregunta técnica, objetivos, alcance, restricciones y supuestos | Informe III · `F1/F1_Definición.ipynb` §2–5 | cumplido |
| 4 | Herramientas científicas (9) | NumPy, Pandas, Jupyter y Git integrados de forma coherente con el problema | Informe IV · notebooks F2 · `src/pipeline/` | cumplido |
| 5 | Reproducibilidad técnica (6) | Ambiente virtual, dependencias completas, instalación verificada, ejecución sin errores | `requirements.txt` · `docs/entorno.md` · `scripts/run_all.py` · CI | cumplido |
| 6 | Control de versiones (6) | Commits descriptivos y frecuentes, ramas, historial verificable | Historial de `git log --graph` · ramas `feature/*` | cumplido |
| 7 | Documentación del proceso (6) | Decisiones justificadas, flujo explicado, cambios con motivo e impacto | `docs/decisiones.md` · markdown de notebooks | cumplido |
| 8 | Repositorio GitHub (6) | Carpetas F1 y F2, README estructurado, commits por integrante | `README.md` · `F1/` · `F2/` · sección Contribuciones | cumplido |
| 9 | Codificación funcional (9) | Funciones con parámetros claros, flujo verificable, código limpio | `src/pipeline/` · `tests/` | cumplido |
| 10 | Preprocesamiento y transformación (6) | Limpieza exhaustiva, NA, casting, normalización, escalamiento y validación justificados | `F2/03_limpieza.ipynb` · `F2/04_transformacion.ipynb` | cumplido |
| 11 | Validación técnica (6) | Casos normales, límite y excepciones con evidencia trazable | `F2/05_validacion.ipynb` · `tests/` · `docs/evidencias/` | cumplido |
| 12 | Notebook F1 (9) | Problemática, objetivos, narrativa, código base, ejecución sin errores, coherencia con el informe | `F1/F1_Definición.ipynb` | cumplido |
| 13 | Notebook F2 (9) | Ejecución sin errores, orden obtención→validación, explicación por bloque, resultados intermedios | `F2/01`–`05` | cumplido |
| 14 | Vinculación con el mapa conceptual (6) | Cada elemento del mapa materializado o proyectado, con justificación | Informe VIII · `F1/mapa-conceptual/` · `F1/F1_Definición.ipynb` §6 | cumplido |
| 15 | Aspectos formales (6) | Formato institucional, APA 7 (≥ 5 fuentes), redacción formal | Informe completo | cumplido |

## Verificación final antes de entregar
- [x] Ninguna celda o documento conserva el marcador "Por desarrollar".
- [x] `python scripts/run_all.py` termina sin errores (8 de 8 pasos) y su log queda en `docs/evidencias/`.
- [ ] La ejecución en GitHub Actions está en verde en `main`.
- [x] Cada integrante tiene commits propios identificables.
- [ ] El informe cita los mismos archivos, notebooks y commits que este documento.
