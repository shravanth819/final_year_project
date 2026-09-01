import os

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
st.set_page_config(page_title="Agri-Mitra", page_icon="🌱", layout="wide")
st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: #071b12; color: #e8fff3; }
[data-testid="stSidebar"] { background: #0b281b; }
</style>
""", unsafe_allow_html=True)


def api_get(path, default):
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return default


st.title("🌱 Agri-Mitra")
st.caption("A free, explainable co-pilot for healthier soil and better decisions.")
fields = api_get("/api/v1/fields", [])
alerts = api_get("/api/v1/alerts/active", [])
col1, col2, col3 = st.columns(3)
col1.metric("Fields monitored", len(fields))
col2.metric("Active alerts", len(alerts))
col3.metric("Software cost", "Free")
st.info("Choose a page from the sidebar to monitor telemetry, ask the co-pilot, or review reports.")
