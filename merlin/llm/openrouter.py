import os
import time

from dotenv import load_dotenv
from langchain_openai.chat_models import ChatOpenAI
from openai import OpenAI

from merlin.utils import logger

load_dotenv()

# Log model initialization
model_name = os.getenv("OPENROUTER_MODEL_DEPLOYMENT")
logger.info(f"Initializing OpenRouter LLM with model: {model_name}")


class LoggedChatOpenAI(ChatOpenAI):
    def __call__(self, *args, **kwargs):
        start_time = time.time()
        try:
            logger.debug(f"Starting OpenRouter API call with args: {args}")
            result = super().__call__(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"OpenRouter API call completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"OpenRouter API call failed after {duration:.2f}s: {str(e)}")
            raise


llm = LoggedChatOpenAI(
    model=model_name,
    base_url=os.getenv("OPENROUTER_ENDPOINT"),
    api_key=os.getenv("OPENROUTER_KEY"),
    temperature=0.01,
    max_tokens=None,
    streaming=True,
)
