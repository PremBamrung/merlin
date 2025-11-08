import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

from merlin.utils import logger

# Get the project root directory (two levels up from this file)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)

# Log environment loading
if env_path.exists():
    logger.info(f"Loading .env from: {env_path}")
else:
    logger.warning(f".env file not found at: {env_path}")

# Log model initialization
model_name = os.getenv("AZURE_MODEL_DEPLOYMENT")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_key = os.getenv("AZURE_OPENAI_KEY")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")

if not all([model_name, azure_endpoint, azure_key, api_version]):
    missing_vars = []
    if not model_name:
        missing_vars.append("AZURE_MODEL_DEPLOYMENT")
    if not azure_endpoint:
        missing_vars.append("AZURE_OPENAI_ENDPOINT")
    if not azure_key:
        missing_vars.append("AZURE_OPENAI_KEY")
    if not api_version:
        missing_vars.append("AZURE_OPENAI_API_VERSION")
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    raise ValueError(
        f"Missing required Azure OpenAI environment variables: {', '.join(missing_vars)}"
    )

logger.info(f"Initializing Azure OpenAI LLM with model: {model_name}")
logger.debug(f"Azure endpoint: {azure_endpoint}")
logger.debug(f"API version: {api_version}")


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
    azure_endpoint=azure_endpoint,
    api_key=azure_key,
    openai_api_version=api_version,
    temperature=0.01,
    max_tokens=None,
    streaming=True,
)
