"""Entry point of the Streamlit client. The pages live in `pages/`.

This file only says what the product is and where the API is; each page talks to the API over
HTTP and holds no business logic of its own.
"""

import streamlit as st

from ui_api import WAKING_UP, api_url, is_api_available

st.set_page_config(page_title="Asistente de alquiler", page_icon="🏠")
st.title("Asistente de alquiler")

st.markdown(
    """
    Dos herramientas para publicar anuncios de alquiler sin sustos:

    - **Revisión de anuncios**: pega tu anuncio y recibe las incidencias que habría que corregir
      antes de publicarlo, con su gravedad y la norma que las respalda.
    - **Consulta de normativa**: pregunta sobre la normativa de alquiler y recibe la respuesta
      **con el artículo del BOE del que sale**, o un "no lo sé" cuando la normativa indexada no
      lo cubre.

    Elige una página en el menú de la izquierda.
    """
)

with st.spinner(WAKING_UP):
    available = is_api_available()
if available:
    st.caption(f"API conectada en {api_url()}")
else:
    st.error("API no disponible")
