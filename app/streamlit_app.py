import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from rag_chain import answer  # noqa: E402

st.set_page_config(page_title="ლექციების ცხრილის ჩატბოტი", page_icon="📅")
st.title("📅 ლექციების ცხრილის ჩატბოტი")
st.caption("RAG: multilingual-e5 + ChromaDB + Groq (gpt-oss-120b)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("sources"):
            with st.expander("წყაროები (მოძიებული ჩანაწერები)"):
                st.caption(f"ფილტრები: {m['filters']}")
                for s in m["sources"]:
                    st.write("•", s)

if q := st.chat_input("დასვი კითხვა, მაგ: ჯგუფი 103-ს ორშაბათს რა აქვს?"):
    st.session_state.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.markdown(q)

    with st.chat_message("assistant"):
        with st.spinner("ვეძებ..."):
            try:
                text, filters, docs = answer(q)
                sources = [d["text"] for d in docs]
            except Exception as e:
                text, filters, sources = f"შეცდომა: {e}", {}, []
        st.markdown(text)
        if sources:
            with st.expander("წყაროები (მოძიებული ჩანაწერები)"):
                st.caption(f"ფილტრები: {filters}")
                for s in sources:
                    st.write("•", s)

    st.session_state.messages.append(
        {"role": "assistant", "content": text, "sources": sources, "filters": filters})