import os

from dotenv import load_dotenv
from langchain_openai.chat_models import ChatOpenAI
from openai import OpenAI

load_dotenv()


llm = ChatOpenAI(
    model=os.getenv("OPENROUTER_MODEL_DEPLOYMENT"),
    base_url=os.getenv("OPENROUTER_ENDPOINT"),
    api_key=os.getenv("OPENROUTER_KEY"),
    temperature=0.01,
    max_tokens=None,
    streaming=True,
)
