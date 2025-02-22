import os
import time

from dotenv import load_dotenv
from langchain_openai.chat_models import AzureChatOpenAI
from openai import OpenAI

from merlin.utils import logger

load_dotenv()

# Log model initialization
model_name = os.getenv("AZURE_MODEL_DEPLOYMENT")
logger.info(f"Initializing Azure OpenAI LLM with model: {model_name}")


class LoggedAzureChatOpenAI(AzureChatOpenAI):
    def __call__(self, *args, **kwargs):
        start_time = time.time()
        try:
            logger.debug(f"Starting Azure OpenAI API call with args: {args}")
            result = super().__call__(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"Azure OpenAI API call completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Azure OpenAI API call failed after {duration:.2f}s: {str(e)}"
            )
            raise


llm = LoggedAzureChatOpenAI(
    deployment_name=model_name,
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    api_key=os.getenv("AZURE_KEY"),
    openai_api_version=os.getenv("AZURE_API_VERSION"),
    temperature=0.01,
    max_tokens=None,
    streaming=True,
)
