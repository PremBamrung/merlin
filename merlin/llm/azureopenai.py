import os

from dotenv import load_dotenv
from langchain_openai.chat_models import AzureChatOpenAI
from openai import OpenAI

load_dotenv()

llm = AzureChatOpenAI(
    deployment_name=os.getenv("AZURE_MODEL_DEPLOYMENT"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    api_key=os.getenv("AZURE_KEY"),
    openai_api_version=os.getenv("AZURE_API_VERSION"),
    temperature=0.01,
    max_tokens=None,
    streaming=True,
)
