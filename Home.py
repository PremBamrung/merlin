import streamlit as st
from dotenv import load_dotenv

from merlin.llm.openrouter import llm
from merlin.utils import set_layout

set_layout()


load_dotenv("merlin/.env")


st.title("🧙‍♂️ Merlin")
st.caption("🚀 A Streamlit chatbot powered by OpenAI")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "How can I help you?"}
    ]

# Add a button in the sidebar to clear the conversation
if st.sidebar.button("Clear Conversation"):
    st.session_state["messages"] = [
        {"role": "assistant", "content": "How can I help you?"}
    ]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        response = st.write_stream(llm.stream(st.session_state.messages))

    st.session_state.messages.append({"role": "assistant", "content": response})
