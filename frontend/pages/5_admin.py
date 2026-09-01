import streamlit as st

from shared import page_title, post

page_title("Admin panel", "Review documents and manage field configuration")
st.warning("OCR results are staged for review and are never committed automatically.")
ocr_text = st.text_area("Paste Pahani / RTC text for review")
if st.button("Extract staged fields"):
    st.json(post("/api/v1/ocr/pahani", {"text": ocr_text}, {"status": "API unavailable"}))
st.subheader("Role")
st.write("Admin access is expected to be enforced by Supabase JWT metadata in production.")
