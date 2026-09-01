import streamlit as st

from shared import API_BASE_URL, get, page_title

page_title("Reports & compliance", "Download field health summaries and inspect anomalies")
fields = get("/api/v1/fields", [])
if fields:
    selected = st.selectbox("Field", fields, format_func=lambda item: item["name"])
    field_id = selected["id"]
    report = get(f"/api/v1/reports/cycle/{field_id}", {})
    st.json(report)
    st.link_button("Download certificate PDF", f"{API_BASE_URL}/api/v1/reports/certificate/{field_id}")
st.subheader("Anomaly log")
st.dataframe(get("/api/v1/anomalies", []), use_container_width=True)
