# =========================================================
# 1. IMPORTAR LAS LIBRERÍAS #
# =========================================================
import base64 # Sirve para convertir la imagen del logo en texto HTML
import os # Lee la clave API KEY secreta desde el sistema
import time # Para controlara el tiempo por si la API esta saturada
from pathlib import Path # Maneja las rutas de carpetas de forma segura

import streamlit as st
from google import genai

# =========================================================
# 2. CONFIGURACIÓN DE LA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Choussy-bot | Colegio Fernando Llort Choussy",
    page_icon="🏫",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Guarda la ruta de la carpeta actual donde está este archivo app.py
BASE_DIR = Path(__file__).resolve().parent 
MODELO = "gemini-3.7-flash"

# =========================================================
# 3. MANDAR A LLAMAR AL CSS 
# =========================================================
def cargar_css():
    for nombre in ("style.css", "style(3).css"):
        css_path = BASE_DIR / nombre
        if css_path.exists():
            # Lee el código CSS y lo activa dentro de la página
            st.markdown(
                f"<style>{css_path.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True,
            )
            return


cargar_css()


# =========================================================
# 4. CARGAR Y MOSTRAR EL ENCABEZADO CON LOGO
# =========================================================
def logo_data_uri():
    for nombre in ("logo_choussy-2.png", "logo.png"):
        logo_path = BASE_DIR / nombre
        if logo_path.exists():
            # Convierte la imagen a formato de texto base64 para poder ponerla en HTML
            data = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
            return f"data:image/png;base64,{data}"
    return ""


logo_uri = logo_data_uri()

# ESTRUCTURA DONDE SE MUESTRA EL LOGO Y EL NOMBRE DEL COLEGIO #
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
        <div class="school-name">COLEGIO FERNANDO LLORT CHOUSSY</div>
        <div class="bot-name">CHOUSSY-BOT</div>
        <div class="bot-subtitle">Asistente virtual institucional</div>
    </div>
</div>
"""
# Dibuja la tarjeta del logo y títulos en la pantalla
st.markdown(header_html, unsafe_allow_html=True)


# =========================================================
# 5. API DE GEMINI
# =========================================================
def obtener_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    return os.environ.get("GEMINI_API_KEY", "")


API_KEY = obtener_api_key()

# Si no hay clave detiene el chatbot #
if not API_KEY:
    st.error(
        "⚠️ Falta configurar GEMINI_API_KEY. "
        "Crea .streamlit/secrets.toml con tu clave de Gemini."
    )
    st.stop()

# Reutiliza la misma conexión con la IA para que el chatbot responda más rápido
@st.cache_resource
def obtener_cliente(api_key):
    return genai.Client(api_key=api_key)


client = obtener_cliente(API_KEY)


# =========================================================
# 6. MANUAL DE CONVIVENCIA
# =========================================================
manual_path = BASE_DIR / "manual_de_convivencia.pdf"

if not manual_path.exists():
    st.error(
        "❌ No se encontró 'manual_de_convivencia.pdf'. "
        "Coloca el PDF en la misma carpeta que app.py."
    )
    st.stop()

# Envía el PDF a los servidores de Gemini solo una vez (lo guarda en su memoria caché)
@st.cache_resource
def subir_manual_a_gemini(ruta_pdf, modificacion):
    return client.files.upload(file=Path(ruta_pdf))


try:
    manual_gemini = subir_manual_a_gemini(
        str(manual_path),
        manual_path.stat().st_mtime,
    )
except Exception as e:
    st.error("❌ No se pudo subir el manual a Gemini.")
    st.code(str(e))
    st.stop()


# =========================================================
# 7. LIMITACIONES Y PERSONALIDAD DEL CHATBOT
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
# 8. HISTORIAL DE LA CONVERSACIÓN
# =========================================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Muestra en la pantalla todas las preguntas y respuestas que ya se han hecho
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =========================================================
# 9. ENTRADA DE PREGUNTAS Y GENERACIÓN DE RESPUESTA
# =========================================================
prompt = st.chat_input(
    "Escribe tu pregunta sobre el manual de convivencia..."
)


if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)

# Guarda la pregunta en el historial
    st.session_state.chat_history.append(
        {"role": "user", "content": prompt}
    )

# Prepara la respuesta de la Inteligencia Artificial
    with st.chat_message("assistant"):
        with st.spinner("Analizando pregunta..."):
            respuesta_texto = None
            ultimo_error = None

            # Obtiene los mensajes anteriores de la conversación
            previous = st.session_state.chat_history[:-1]

            # Toma hasta los últimos 10 mensajes para que el chatbot recuerde el tema
            history_text = ""
            if previous:
                history_text = "\n\n".join(
                    f"{m['role'].upper()}: {m['content']}"
                    for m in previous[-10:]
                )

            # Une el historial con la pregunta actual
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

            # Intenta comunicarse con la API de Gemini (hasta 5 veces si hay problemas de red)
            for intento in range(5):
                try:
                    response = client.models.generate_content(
                        model=MODELO,
                        contents=[
                            prompt_completo,
                            manual_gemini,
                        ],
                        config={
                            "system_instruction": instrucciones_escolares,
                        },
                    )

                    respuesta_texto = (response.text or "").strip()

                    # Si Gemini respondió detiene los reintentos
                    if respuesta_texto:
                        break

                    ultimo_error = "Gemini devolvió una respuesta vacía."

                except Exception as e:
                    ultimo_error = str(e)
                    error_lower = ultimo_error.lower()
                    
                    # Si el servidor está muy saturado (errores 429 o 503), espera unos segundos
                    if (
                        any(key in ultimo_error for key in ["429", "503"])
                        and intento < 4
                    ):
                        time.sleep((intento + 1) * 4)
                        continue

                    break
            # Si logró obtener respuesta, la muestra en la pantalla y la guarda
            if respuesta_texto:
                st.markdown(respuesta_texto)

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": respuesta_texto,
                    }
                )
            else:
                # Si ocurrió un error después de los 5 intentos, muestra la alerta
                st.error("⚠️ Choussy-bot no pudo responder.")
                if ultimo_error:
                    st.code(ultimo_error)
