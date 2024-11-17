import os

import streamlit as st
from dotenv import load_dotenv
from langchain_openai.chat_models import AzureChatOpenAI

st.set_page_config(
    page_title="Merlin",
    page_icon="🧙‍♂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv("merlin/.env")

llm = AzureChatOpenAI(
    deployment_name=os.getenv("AZURE_MODEL_DEPLOYMENT"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    api_key=os.getenv("AZURE_KEY"),
    openai_api_version=os.getenv("AZURE_API_VERSION"),
    temperature=0.01,
    max_tokens=None,
    streaming=True,
)
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
