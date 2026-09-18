# Análisis Perú — Piloto dinámico de inflación

Este piloto prueba la idea central del portal: que una persona pueda escoger
un intervalo de tiempo y obtener, para esa misma muestra:

- gráfico dinámico;
- serie original;
- primera diferencia;
- prueba ADF;
- prueba KPSS;
- diagnóstico orientativo del orden de integración;
- descarga CSV;
- descarga Excel.

## Ejecutarlo localmente

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Fuente utilizada

BCRPData / INEI

Código de serie usado en el piloto:

`PN01273PM`

Inflación IPC — variación porcentual 12 meses.

## Qué NO incluye todavía

Esta es deliberadamente una primera versión. Todavía no añadimos:

- cambio de frecuencia mensual / trimestral / anual;
- logaritmos del IPC en niveles;
- Phillips-Perron;
- ADF con tendencia;
- selección de especificación determinística;
- quiebres estructurales;
- cointegración;
- VAR / VECM;
- integración directa dentro de Blogger.

Primero conviene validar que selector de fechas, gráfico, pruebas y descarga
funcionen correctamente.

## Próxima etapa propuesta

1. Validar el piloto.
2. Incorporar IPC en niveles.
3. Añadir `ln(IPC)` y `Δln(IPC)`.
4. Añadir selector de frecuencia y reglas de agregación.
5. Publicar la app.
6. Incrustarla en la entrada de Blogger.
