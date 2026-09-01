import streamlit as st

from shared import get, page_title

page_title("Fields", "Field inventory, crop stages, and location context")
fields = get("/api/v1/fields", [])
for field in fields:
    with st.container(border=True):
        st.subheader(field["name"])
        st.write(f"Crop: {field['crop_type']} · Stage: {field['growth_stage']} · ID: `{field['id']}`")
        st.json(field.get("gps_coordinates") or {})
