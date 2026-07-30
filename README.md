# Corrector Automatizado de Pruebas

Implementa el flujo de dos fases del prompt original, corrigiendo sus vacíos para que
sea realmente automatizable:

## Qué se corrigió respecto al prompt original

| Problema original | Corrección aplicada |
|---|---|
| Salida en texto libre | Fase 1 y Fase 2 exigen JSON estricto con esquema fijo (`prompts.py`) |
| Sin mecanismo de "pausa" real entre fases | La pauta queda bloqueada en `st.session_state` recién tras el botón "Validar y bloquear pauta"; Fase 2 no habilita hasta entonces |
| Preguntas sin coincidencia numérica no tenían salida definida | Se marcan `"estado": "REVISAR"` y se listan aparte para corrección manual, sin bloquear el resto de la pauta |
| Múltiples formas (A/B/C) sin mapeo explícito | El JSON de pauta incluye `"forma"` por pregunta y Fase 2 usa solo la pauta de la forma detectada en la hoja |
| Sin definición de qué pasa con marcas dobles/ilegibles | Definido explícitamente como `INCORRECTA` con motivo (`ilegible` / `doble_marca`) |
| "Aislamiento de contexto" solo mencionado, no forzado | Cada foto se envía en una llamada API *independiente* (sin historial de mensajes previos), así el modelo no tiene forma de "recordar" hojas anteriores |
| Tono "directo, sin introducciones" contradecía el volumen de tablas pedido | Se quitó esa instrucción de los prompts; las tablas se muestran en la interfaz, no como texto narrado |

## Uso

```bash
pip install -r requirements.txt
streamlit run app.py
```

1. Ingresa tu API key de Anthropic en la barra lateral.
2. **Fase 1**: sube la prueba (PDF/imagen) o pega el texto → "Analizar prueba y generar pauta".
   Revisa/edita la tabla (puedes corregir clave u OA de cualquier pregunta) y presiona
   "Validar y bloquear pauta".
3. **Fase 2**: sube las fotos de las hojas de respuesta (se pueden subir varias a la vez;
   cada una se procesa como evento independiente) → "Corregir hojas subidas".
4. **Reporte final**: tabla de % de logro por OA con veredicto Logrado/No logrado (umbral 60%,
   editable en `UMBRAL_LOGRO` dentro de `app.py`), resumen por estudiante y descarga en CSV.

## Notas

- Cambia `MODEL` en `app.py` si tu cuenta usa otro alias de modelo con visión.
- El umbral de logro (60%) y el tamaño de bloque de preguntas son ajustables en el código.
- Las imágenes se envían en base64 directamente a la API; no se guardan en disco.
