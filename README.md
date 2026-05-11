# SIAT-DE
Sistema Inteligente de Alerta Temprana para la Deserción Estudiantil.

## Ejecución local
```bash
pip install -r requirements.txt
python app.py
```

Abrir: http://127.0.0.1:5000

## Acceso demo
- Usuario: admin
- Contraseña: admin123

## Contenido funcional
- Flask + Bootstrap 5 + Chart.js + DataTables
- Dataset oficial incluido
- Modelo entrenado incluido
- Dashboard ejecutivo
- Gestión de estudiantes
- Predicción ML con carga CSV
- Nuevo módulo: Analítica Académica
- Alertas tempranas
- Intervenciones y seguimiento
- Reportes y administración

## Nuevo módulo de Analítica Académica
Incluye indicadores de rendimiento, aprobación, reprobación, asistencia, riesgo por carrera, riesgo por semestre, factores académicos críticos, correlaciones académicas y tabla de estudiantes con vulnerabilidad académica prioritaria.

Nota técnica: el modelo fue entrenado con Scikit-learn 1.6.1. Por eso el requirements fija esa versión.

## Actualización V4 - Analítica Académica con selectores
Esta versión incorpora el panel de comparación dinámica en el módulo Analítica Académica:
- Filtro por carrera.
- Filtro por semestre.
- Filtro por nivel de riesgo.
- Selector de Variable X.
- Selector de Variable Y.
- Selector de tipo de gráfico: dispersión, barras, línea y pie/donut.
- Resumen interpretativo automático de la comparación.
- Distribución visual en máximo dos gráficos por fila.

## Versión V6 - Mejoras globales profesionales

Esta versión incorpora mejoras globales para elevar el prototipo a nivel institucional:

- Centro de Inteligencia Institucional con insights automáticos.
- Simulador predictivo tipo “qué pasaría si...”.
- Explicabilidad del riesgo en el perfil individual del estudiante.
- Línea temporal académica por estudiante.
- Reporte institucional imprimible/guardable como PDF desde el navegador.
- Panel de métricas del modelo y variables asociadas al riesgo.

Rutas principales nuevas:

- `/inteligencia`
- `/simulador`
- `/reporte-institucional`

