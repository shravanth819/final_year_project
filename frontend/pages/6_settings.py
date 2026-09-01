import streamlit as st

from shared import page_title, post

page_title("Settings", "Language, display units, voice, and notification preferences")
language = st.selectbox("Preferred language", ["en", "hi", "kn", "ta", "te", "mr", "bn", "gu", "pa", "ml", "or"])
area_unit = st.selectbox("Area unit", ["hectare", "acre", "guntha", "bigha", "cent"])
voice = st.toggle("Voice playback", value=True)
if st.button("Save preferences"):
    result = post("/api/v1/preferences", {"preferred_language": language, "preferred_area_unit": area_unit, "voice_playback_enabled": voice}, {})
    st.success(result.get("id", "Preferences saved"))
