import os

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def get(path, default):
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return default


def post(path, payload=None, default=None):
    try:
        response = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return default


def page_title(title, subtitle):
    st.title(title)
    st.caption(subtitle)
