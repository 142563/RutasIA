# Cuadernos de la tesis (compatibles con Google Colab)

| Cuaderno | Qué hace | Archivos que necesita |
|---|---|---|
| `analisis_estadistico.ipynb` | Estadística del experimento: media y desviación por escenario, Shapiro-Wilk, t pareada o Wilcoxon, d de Cohen, α = 0.05, metas de la tesis y genético contra OR-Tools | `matriz_comparativa.csv` y `genetico_vs_ortools.csv` (de `docs/Capitulo V/resultados/`) |
| `refuerzo_exploratorio.ipynb` | Aprendizaje por refuerzo **exploratorio** con TensorFlow/Keras (DQN): elegir la mejor ruta candidata ante un evento de congestión o cierre | `grafo.json` y `logistics/routing/genetic.py` |

Ambos quedan guardados **ya ejecutados** (con sus salidas).

## Cómo regenerar los datos

```bash
python manage.py run_thesis_experiment
```

```bash
python manage.py export_graph_json
```

`grafo.json` no se sube a Git (son datos derivados de Google Routes API); se regenera con el segundo comando.

## Cómo correrlos en local

TensorFlow vive en un entorno aparte (`experiments/colab/.venv-tf`, ignorado por Git) para no pesar en el servidor:

```bash
python -m venv experiments/colab/.venv-tf
```

```bash
experiments/colab/.venv-tf/Scripts/python -m pip install "tensorflow==2.19.*" numpy pandas scipy matplotlib nbconvert ipykernel
```

En Colab basta con subir los archivos de la tabla a la sesión.
