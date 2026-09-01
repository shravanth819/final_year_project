import streamlit as st

from shared import get, page_title, post

page_title("Live dashboard", "Real-time field health, alerts, and risk signals")
fields = get("/api/v1/fields", [])
selected = st.selectbox("Field", fields, format_func=lambda item: f"{item['name']} · {item['crop_type']}" if item else "No field") if fields else None
field_id = selected["id"] if selected else "field_demo"
readings = get(f"/api/v1/fields/{field_id}/readings?limit=1", [])
latest = readings[0] if readings else {}
columns = st.columns(5)
for column, label, value in zip(columns, ["Moisture", "pH", "Nitrogen", "Potassium", "Temperature"], [latest.get("soil_moisture", "—"), latest.get("ph", "—"), latest.get("n", "—"), latest.get("k", "—"), latest.get("temperature", "—")]):
    column.metric(label, value)
alerts = get("/api/v1/alerts/active", [])
if alerts:
    for alert in alerts[:5]:
        st.warning(f"{alert['alert_type']} · field {alert['field_id']} · escalation {alert['escalation_level']}")
else:
    st.success("No active alerts")
if st.button("Simulate stress event"):
    result = post("/api/v1/simulate/stress-event", default={})
    st.toast(result.get("status", "Unable to reach API"))
