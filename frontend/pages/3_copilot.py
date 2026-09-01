import streamlit as st

from shared import page_title, post

page_title("AI co-pilot", "Grounded guidance with a clear explanation of what is known")
language = st.selectbox("Language", ["en", "hi", "kn", "ta", "te", "mr", "bn", "gu", "pa", "ml", "or"])
question = st.chat_input("Ask about irrigation, soil, or crop planning")
if question:
    result = post("/api/v1/copilot/query", {"query_text": question, "language": language, "context": ["FAO knowledge base"]}, {})
    with st.chat_message("assistant"):
        st.write(result.get("answer_text", "Data Not Available"))
        if result.get("citations"):
            st.caption("Sources: " + ", ".join(str(item["source"]) for item in result["citations"]))
st.divider()
st.subheader("Irrigation co-pilot")
st.write("Rain probability is checked before recommending irrigation. Connect a field weather source to activate live advice.")
