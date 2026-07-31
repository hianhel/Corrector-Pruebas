"""
Corrector Automatizado de Pruebas — Fase 1 (pauta) + Fase 2 (corrección de hojas)

Ejecutar con:
    pip install -r requirements.txt
    streamlit run app.py

Requiere una API key de Anthropic (https://console.anthropic.com/settings/keys).
"""

import base64
import json
import re

import pandas as pd
import streamlit as st
from anthropic import Anthropic

from prompts import PHASE1_SYSTEM_PROMPT, PHASE2_SYSTEM_PROMPT

MODEL = "claude-sonnet-5"  # cambia aquí si tu cuenta usa otro alias de modelo
UMBRAL_LOGRO = 0.60  # 60% definido en el prompt original para marcar OA "Logrado"

st.set_page_config(page_title="Corrector Automatizado de Pruebas", layout="wide")


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def get_client() -> Anthropic:
    return Anthropic(api_key=st.session_state["api_key"])


def extract_json(raw_text: str) -> dict:
    """El modelo puede envolver el JSON en ```json ... ``` a pesar de la instrucción;
    esto lo tolera igual en vez de fallar en seco."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def file_to_content_block(uploaded_file) -> dict:
    """Convierte un archivo subido (imagen o PDF) a un bloque de contenido de la API."""
    data = uploaded_file.getvalue()
    b64 = base64.standard_b64encode(data).decode("utf-8")
    mime = uploaded_file.type or "application/octet-stream"
    if mime == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": mime, "data": b64}}
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}


def call_claude(system_prompt: str, user_content: list) -> dict:
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=32000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    raw_text = "".join(block.text for block in resp.content if block.type == "text")
    return extract_json(raw_text)


# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------

st.session_state.setdefault("pauta", None)          # JSON de Fase 1, editado por el profesor
st.session_state.setdefault("pauta_bloqueada", False)
st.session_state.setdefault("resultados_estudiantes", [])  # lista de JSON de Fase 2

st.title("Corrector Automatizado de Pruebas")

with st.sidebar:
    st.session_state["api_key"] = st.text_input("Anthropic API key", type="password")
    st.caption(f"Modelo: {MODEL}")
    if st.session_state["pauta_bloqueada"]:
        st.success("Pauta validada y bloqueada ✅")
        if st.button("Desbloquear pauta (editar de nuevo)"):
            st.session_state["pauta_bloqueada"] = False

tab1, tab2, tab3 = st.tabs(["Fase 1 · Pauta", "Fase 2 · Corrección", "Reporte final"])

# ---------------------------------------------------------------------------
# FASE 1
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("1. Sube la prueba (PDF, imagen o texto pegado)")

    prueba_file = st.file_uploader(
        "Documento de la prueba", type=["pdf", "png", "jpg", "jpeg"], key="prueba_file"
    )
    prueba_texto = st.text_area("...o pega el texto de la prueba aquí", height=150)

    if st.button("Analizar prueba y generar pauta", disabled=st.session_state["pauta_bloqueada"]):
        if not st.session_state["api_key"]:
            st.error("Ingresa tu API key en la barra lateral.")
        elif not prueba_file and not prueba_texto.strip():
            st.error("Sube un archivo o pega el texto de la prueba.")
        else:
            with st.spinner("Extrayendo, calculando y emparejando cada pregunta..."):
                content = []
                if prueba_file:
                    content.append(file_to_content_block(prueba_file))
                if prueba_texto.strip():
                    content.append({"type": "text", "text": prueba_texto})
                else:
                    content.append({"type": "text", "text": "Analiza el documento adjunto."})
                try:
                    st.session_state["pauta"] = call_claude(PHASE1_SYSTEM_PROMPT, content)
                except (json.JSONDecodeError, Exception) as e:
                    st.error(f"No se pudo generar la pauta: {e}")

    pauta = st.session_state["pauta"]
    if pauta:
        preguntas_df = pd.DataFrame(pauta["preguntas"])

        revisar = preguntas_df[preguntas_df["estado"] == "REVISAR"]
        if not revisar.empty:
            st.warning(
                f"{len(revisar)} pregunta(s) marcadas REVISAR: el cálculo no coincidió con "
                f"ninguna alternativa. Corrígelas manualmente antes de validar."
            )
            st.dataframe(revisar[["numero", "resultado_calculado", "alternativas", "observacion"]])

        st.subheader("2. Valida / edita la Pauta de Corrección")
        edited_preguntas = st.data_editor(
            preguntas_df[["numero", "forma", "clave_correcta", "oa_codigo", "estado"]],
            num_rows="fixed",
            key="editor_pauta",
            disabled=st.session_state["pauta_bloqueada"],
        )

        st.subheader("3. Objetivos de Aprendizaje")
        oa_df = pd.DataFrame(pauta["objetivos_aprendizaje"])
        st.dataframe(oa_df, use_container_width=True)

        st.subheader("4. Tabla de Especificaciones")
        st.dataframe(pd.DataFrame(pauta["tabla_especificaciones"]), use_container_width=True)

        if not st.session_state["pauta_bloqueada"]:
            if st.button("✅ Validar y bloquear pauta (pasar a Fase 2)"):
                # aplica las ediciones del profesor de vuelta al JSON fuente
                edited_map = edited_preguntas.set_index("numero").to_dict("index")
                for q in pauta["preguntas"]:
                    if q["numero"] in edited_map:
                        q["clave_correcta"] = edited_map[q["numero"]]["clave_correcta"]
                        q["oa_codigo"] = edited_map[q["numero"]]["oa_codigo"]
                        q["estado"] = "OK"
                st.session_state["pauta"] = pauta
                st.session_state["pauta_bloqueada"] = True
                st.rerun()

# ---------------------------------------------------------------------------
# FASE 2
# ---------------------------------------------------------------------------
with tab2:
    if not st.session_state["pauta_bloqueada"]:
        st.info("Valida y bloquea la pauta en la pestaña Fase 1 antes de continuar.")
    else:
        st.subheader("Sube las fotos de las hojas de respuesta (una o varias, se procesan por separado)")
        fotos = st.file_uploader(
            "Fotos de hojas de respuesta", type=["png", "jpg", "jpeg"],
            accept_multiple_files=True, key="fotos_hojas",
        )

        if st.button("Corregir hojas subidas"):
            if not fotos:
                st.error("Sube al menos una foto.")
            else:
                pauta_json_str = json.dumps(
                    {
                        "formas": st.session_state["pauta"]["formas"],
                        "tabla_especificaciones": st.session_state["pauta"]["tabla_especificaciones"],
                    },
                    ensure_ascii=False,
                )
                progress = st.progress(0.0)
                for i, foto in enumerate(fotos):
                    with st.spinner(f"Corrigiendo hoja {i + 1}/{len(fotos)} (evento independiente)..."):
                        content = [
                            file_to_content_block(foto),
                            {
                                "type": "text",
                                "text": f"Pauta de corrección validada (JSON):\n{pauta_json_str}\n\n"
                                        f"Corrige esta hoja de respuesta según las reglas del sistema.",
                            },
                        ]
                        try:
                            resultado = call_claude(PHASE2_SYSTEM_PROMPT, content)
                            resultado["_archivo"] = foto.name
                            st.session_state["resultados_estudiantes"].append(resultado)
                        except (json.JSONDecodeError, Exception) as e:
                            st.error(f"Error procesando {foto.name}: {e}")
                    progress.progress((i + 1) / len(fotos))
                st.success(f"{len(fotos)} hoja(s) procesadas.")

        if st.session_state["resultados_estudiantes"]:
            st.subheader("Resultados por estudiante")
            for r in st.session_state["resultados_estudiantes"]:
                with st.expander(
                    f"{r['nombre_estudiante']} — Forma {r['forma_prueba']} — "
                    f"{r['total_correctas']} correctas / {r['total_incorrectas']} incorrectas"
                ):
                    if r["estado_identificacion"] == "REVISAR":
                        st.warning("Nombre o forma no se identificaron con claridad.")
                    df_resp = pd.DataFrame(r["respuestas"])
                    df_resp["Estado"] = df_resp["estado"].map({"CORRECTA": "✅", "INCORRECTA": "❌"})
                    st.dataframe(
                        df_resp[["numero", "clave_pauta", "marca_detectada", "Estado"]],
                        use_container_width=True,
                    )
                    st.write(f"**Total: {r['total_correctas']} correctas, {r['total_incorrectas']} incorrectas**")

            if st.button("🗑️ Limpiar resultados de esta sesión"):
                st.session_state["resultados_estudiantes"] = []
                st.rerun()

# ---------------------------------------------------------------------------
# REPORTE FINAL (análisis pedagógico por OA, agregado)
# ---------------------------------------------------------------------------
with tab3:
    if not st.session_state["resultados_estudiantes"]:
        st.info("Aún no hay hojas corregidas.")
    else:
        st.subheader("Análisis pedagógico por Objetivo de Aprendizaje")

        oa_por_pregunta = {
            item["numero"]: item["oa_codigo"]
            for item in st.session_state["pauta"]["tabla_especificaciones"]
        }

        filas = []
        for r in st.session_state["resultados_estudiantes"]:
            for resp in r["respuestas"]:
                filas.append(
                    {
                        "estudiante": r["nombre_estudiante"],
                        "numero": resp["numero"],
                        "oa_codigo": oa_por_pregunta.get(resp["numero"], "SIN_OA"),
                        "correcta": resp["estado"] == "CORRECTA",
                    }
                )
        detalle_df = pd.DataFrame(filas)

        resumen_oa = (
            detalle_df.groupby("oa_codigo")["correcta"]
            .mean()
            .reset_index()
            .rename(columns={"correcta": "pct_logro"})
        )
        resumen_oa["pct_logro"] = (resumen_oa["pct_logro"] * 100).round(1)
        resumen_oa["veredicto"] = resumen_oa["pct_logro"].apply(
            lambda p: "Logrado" if p >= UMBRAL_LOGRO * 100 else "No logrado"
        )
        st.dataframe(resumen_oa, use_container_width=True)

        st.subheader("Resumen general por estudiante")
        resumen_estudiantes = pd.DataFrame(
            [
                {
                    "estudiante": r["nombre_estudiante"],
                    "forma": r["forma_prueba"],
                    "correctas": r["total_correctas"],
                    "incorrectas": r["total_incorrectas"],
                }
                for r in st.session_state["resultados_estudiantes"]
            ]
        )
        st.dataframe(resumen_estudiantes, use_container_width=True)

        csv = detalle_df.to_csv(index=False).encode("utf-8")
        st.download_button("Descargar detalle completo (CSV)", csv, "detalle_correccion.csv", "text/csv")
