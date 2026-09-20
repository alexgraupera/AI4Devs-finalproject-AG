"""Entry point of the Streamlit client. The pages live in `pages/`.

This file only says what the product is and where the API is; each page talks to the API over
HTTP and holds no business logic of its own.
"""

import httpx
import streamlit as st

from app.config import get_settings

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

api_url = get_settings().api_url
try:
    healthy = httpx.get(f"{api_url}/health", timeout=2).status_code == 200
except httpx.HTTPError:
    healthy = False

if healthy:
    st.caption(f"API conectada en {api_url}")
else:
    st.error("API no disponible")
