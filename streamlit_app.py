import httpx
import streamlit as st

from app.config import get_settings


def is_api_available(api_url: str) -> bool:
    try:
        response = httpx.get(f"{api_url}/health", timeout=2)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


st.set_page_config(page_title="Revisión de anuncios de alquiler", page_icon="🏠")
st.title("Revisión de anuncios de alquiler")

if is_api_available(get_settings().api_url):
    st.success("API conectada")
else:
    st.error("API no disponible")
