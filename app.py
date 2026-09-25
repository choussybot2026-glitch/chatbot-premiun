import base64
import os
import time
from pathlib import Path

import anthropic as ant
import streamlit as st

# CONFIGURACIÓN PARA NOMBRE DE LA PAGINA 
st.set_page_config(
    page_title="Choussy-bot | Colegio Fernando Llort Choussy",
    page_icon="🏫",
    layout="centered",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
MODELO = "claude-sonnet-5"


# =========================================================
# CSS 
# =========================================================
def cargar_css():
    for nombre in ("style.css", "style(3).css"):
        css_path = BASE_DIR / nombre
        if css_path.exists():
            st.markdown(
                f"<style>{css_path.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True,
            )
            return


cargar_css()


# =========================================================
# LOGO
# =========================================================
def logo_data_uri():
    for nombre in ("logo_choussy-2.png", "logo.png"):
        logo_path = BASE_DIR / nombre
        if logo_path.exists():
            data = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
            return f"data:image/png;base64,{data}"
    return ""


logo_uri = logo_data_uri()

header_html = f"""
<div class="school-header">
    <div class="logo-box">
        {
            f'<img src="{logo_uri}" class="school-logo">'
            if logo_uri
            else '<div class="logo-placeholder">🏫</div>'
        }
    </div>
    <div class="school-text">
        <div class="school-name">Colegio Fernando Llort Choussy</div>
        <div class="bot-name">Choussy-bot</div>
        <div class="bot-subtitle">Asistente virtual institucional</div>
    </div>
</div>
"""

st.markdown(header_html, unsafe_allow_html=True)


# =========================================================
# API DE CLAUDE
# =========================================================
def obtener_api_key():
    try:
        key = st.secrets.get("CLAUDE_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    return os.environ.get("CLAUDE_API_KEY", "")


API_KEY = obtener_api_key()

if not API_KEY:
    st.error(
        "⚠️ Falta configurar CLAUDE_API_KEY. "
        "Crea .streamlit/secrets.toml con tu clave de Claude."
    )
    st.stop()


@st.cache_resource
def obtener_cliente(api_key):
    return ant.Anthropic(api_key=api_key)


client = obtener_cliente(API_KEY)


# =========================================================
# MANUAL DE CONVIVENCIA
# =========================================================
manual_path = BASE_DIR / "manual_de_convivencia.pdf"

if not manual_path.exists():
    st.error(
        "❌ No se encontró 'manual_de_convivencia.pdf'. "
        "Coloca el PDF en la misma carpeta que app.py."
    )
    st.stop()


@st.cache_resource
def subir_manual_a_claude(ruta_pdf, modificacion):
    return client.files.upload(file=Path(ruta_pdf))


try:
    manual_claude = subir_manual_a_claude(
        str(manual_path),
        manual_path.stat().st_mtime,
    )
except Exception as e:
    st.error("❌ No se pudo subir el manual a Claude.")
    st.code(str(e))
    st.stop()


# =========================================================
# PERSONALIDAD DEL CHATBOT Y LIMITACIONES 
# =========================================================
instrucciones_escolares = """
Eres el Asistente Virtual Oficial del Colegio Fernando Llort Choussy.

Tu público objetivo son padres de familia y estudiantes de todos los
niveles académicos.

REGLAS ESTRICTAS DE ATENCIÓN:

1. Responde siempre con empatía, amabilidad, respeto y un lenguaje sencillo,
   libre de tecnicismos complejos.

2. Utiliza viñetas o listas numeradas cuando expliques procesos.

3. Basa tus respuestas ÚNICAMENTE en el manual digital de convivencia
   proporcionado. No asumas ni inventes nada que no esté escrito allí.

4. Si la duda del usuario involucra un caso muy específico, una queja formal
   o algo que NO viene en el manual, indícales amablemente que deben acudir
   con el "Coordinador Académico" o a la "Dirección".

5. Si no sabes la respuesta o no está en el reglamento, di de forma cordial:
   "Lamentablemente no encuentro esa norma en el reglamento vigente.
   Le sugerimos consultar directamente con la secretaría de la institución."

6. No inventes artículos, sanciones, horarios, teléfonos, nombres ni
   procedimientos que no aparezcan en el documento.

7. Si existe conversación anterior, úsala solamente para entender referencias
   como "eso", "lo anterior" o "esa norma". La información oficial debe salir
   del manual proporcionado.
"""


# =========================================================
# HISTORIAL
# =========================================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# =========================================================
# MENSAJES
# Streamlit renderiza cada mensaje como su propio componente.
# =========================================================
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =========================================================
# ENTRADA
# =========================================================
prompt = st.chat_input(
    "Escribe tu pregunta sobre el manual de convivencia..."
)


if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)

    st.session_state.chat_history.append(
        {"role": "user", "content": prompt}
    )

    with st.chat_message("assistant"):
        with st.spinner("Analizando pregunta..."):
            respuesta_texto = None
            ultimo_error = None

            previous = st.session_state.chat_history[:-1]

            history_text = ""
            if previous:
                history_text = "\n\n".join(
                    f"{m['role'].upper()}: {m['content']}"
                    for m in previous[-10:]
                )

            if history_text:
                prompt_completo = (
                    "Contexto de la conversación anterior:\n"
                    f"{history_text}\n\n"
                    "Responde la pregunta actual usando ÚNICAMENTE "
                    "el manual de convivencia proporcionado. "
                    "La conversación anterior sirve solo para entender "
                    "referencias; las normas deben salir del PDF.\n\n"
                    f"Pregunta actual: {prompt}"
                )
            else:
                prompt_completo = (
                    "Responde la siguiente pregunta usando ÚNICAMENTE "
                    "el manual de convivencia proporcionado.\n\n"
                    f"Pregunta: {prompt}"
                )

            for intento in range(3):
                try:
                    response = client.models.generate_content(
                        model=MODELO,
                        contents=[
                            prompt_completo,
                            manual_claude,
                        ],
                        config={
                            "system_instruction": instrucciones_escolares,
                        },
                    )

                    respuesta_texto = (response.text or "").strip()

                    if respuesta_texto:
                        break

                    ultimo_error = "Claude devolvió una respuesta vacía."

                except Exception as e:
                    ultimo_error = str(e)

                    if (
                        ("429" in ultimo_error or "503" in ultimo_error)
                        and intento < 2
                    ):
                        time.sleep((intento + 1) * 2)
                        continue

                    break

            if respuesta_texto:
                st.markdown(respuesta_texto)

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": respuesta_texto,
                    }
                )
            else:
                st.error("⚠️ Choussy-bot no pudo responder.")
                if ultimo_error:
                    st.code(ultimo_error)