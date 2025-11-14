"""Tests for Azure OpenAI connection and functionality."""

import pytest
from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI

from merlin.llm.azureopenai import llm as merlin_llm
from merlin.utils import logger


@pytest.mark.requires_azure
def test_environment_variables(azure_openai_configured):
    """Test that all required environment variables are present."""
    assert azure_openai_configured["AZURE_OPENAI_ENDPOINT"]
    assert azure_openai_configured["AZURE_OPENAI_KEY"]
    assert azure_openai_configured["AZURE_OPENAI_API_VERSION"]
    assert azure_openai_configured["AZURE_MODEL_DEPLOYMENT"]


@pytest.mark.requires_azure
def test_direct_langchain_connection(azure_openai_configured):
    """Test direct LangChain Azure OpenAI connection (without Merlin's API)."""
    # Create a direct LangChain AzureChatOpenAI instance
    direct_llm = AzureChatOpenAI(
        deployment_name=azure_openai_configured["AZURE_MODEL_DEPLOYMENT"],
        azure_endpoint=azure_openai_configured["AZURE_OPENAI_ENDPOINT"],
        api_key=azure_openai_configured["AZURE_OPENAI_KEY"],
        openai_api_version=azure_openai_configured["AZURE_OPENAI_API_VERSION"],
        temperature=0.01,
        streaming=True,
    )

    assert (
        direct_llm.deployment_name == azure_openai_configured["AZURE_MODEL_DEPLOYMENT"]
    )
    assert direct_llm.azure_endpoint == azure_openai_configured["AZURE_OPENAI_ENDPOINT"]
    assert (
        direct_llm.openai_api_version
        == azure_openai_configured["AZURE_OPENAI_API_VERSION"]
    )
    assert direct_llm.temperature == 0.01
    assert direct_llm.streaming is True

    # Test a simple completion with direct LangChain
    test_prompt = "Say 'Direct LangChain connection works!' in one sentence."
    response = direct_llm.invoke(test_prompt)

    # Extract content
    if hasattr(response, "content"):
        content = response.content
    elif isinstance(response, str):
        content = response
    else:
        content = str(response)

    assert content
    assert len(content) > 0


@pytest.mark.requires_azure
def test_merlin_llm_initialization(azure_openai_configured):
    """Test that Merlin's LLM object is properly initialized."""
    assert merlin_llm is not None
    assert (
        merlin_llm.deployment_name == azure_openai_configured["AZURE_MODEL_DEPLOYMENT"]
    )
    assert merlin_llm.azure_endpoint == azure_openai_configured["AZURE_OPENAI_ENDPOINT"]
    assert (
        merlin_llm.openai_api_version
        == azure_openai_configured["AZURE_OPENAI_API_VERSION"]
    )


@pytest.mark.requires_azure
def test_simple_completion():
    """Test a simple completion request with Merlin's LLM."""
    prompt = "Say 'Hello, Azure OpenAI is working!' in one sentence."

    response = merlin_llm.invoke(prompt)

    # Extract content
    if hasattr(response, "content"):
        content = response.content
    elif isinstance(response, str):
        content = response
    else:
        content = str(response)

    assert content
    assert len(content) > 0
    assert "Azure OpenAI" in content or "working" in content.lower()


@pytest.mark.requires_azure
def test_streaming_completion():
    """Test a streaming completion request with Merlin's LLM."""
    prompt = "Count from 1 to 5, one number per line."

    full_response = ""
    chunk_count = 0

    for chunk in merlin_llm.stream(prompt):
        # Extract content from chunk
        if hasattr(chunk, "content"):
            content = chunk.content
        elif isinstance(chunk, str):
            content = chunk
        else:
            content = str(chunk) if chunk else ""

        if content:
            full_response += content
            chunk_count += 1

    assert chunk_count > 0
    assert len(full_response) > 0


@pytest.mark.requires_azure
def test_prompt_template():
    """Test using a prompt template with Merlin's LLM."""
    template = PromptTemplate(
        template="Write a {length} summary about {topic}.",
        input_variables=["length", "topic"],
    )

    chain = template | merlin_llm

    prompt_input = {"length": "brief", "topic": "artificial intelligence"}

    response = chain.invoke(prompt_input)

    # Extract content
    if hasattr(response, "content"):
        content = response.content
    elif isinstance(response, str):
        content = response
    else:
        content = str(response)

    assert content
    assert len(content) > 0


@pytest.mark.requires_azure
def test_text_summarization_capabilities():
    """Test text summarization capabilities with fake content."""
    # Create fake text content to summarize
    fake_text = """
    Welcome to this educational content about artificial intelligence. Today we'll explore the fundamentals of AI and machine learning.

    First, let's understand what artificial intelligence is. AI refers to computer systems that can perform tasks typically requiring human intelligence. These tasks include learning, reasoning, and problem-solving.

    Machine learning is a subset of AI that enables systems to learn from data without being explicitly programmed. There are three main types: supervised learning, unsupervised learning, and reinforcement learning.

    Supervised learning uses labeled data to train models. For example, we can train a model to recognize cats in images by showing it thousands of labeled cat photos.

    Unsupervised learning finds patterns in data without labels. This is useful for discovering hidden structures or grouping similar data points together.

    Reinforcement learning involves an agent learning through trial and error, receiving rewards for good actions and penalties for bad ones. This approach has been successful in game playing and robotics.

    Deep learning uses neural networks with multiple layers to process complex data. Convolutional neural networks excel at image recognition, while recurrent neural networks are great for sequential data like text.

    Natural language processing allows computers to understand and generate human language. Modern NLP models can translate languages, answer questions, and even write creative content.

    AI applications are everywhere: recommendation systems, autonomous vehicles, medical diagnosis, and virtual assistants. However, we must also consider ethical implications like bias, privacy, and job displacement.

    The future of AI looks promising with advances in areas like quantum computing and general artificial intelligence. But we need to ensure AI development is responsible and beneficial for all of humanity.
    """

    # Create a simple summarization prompt template
    summary_template = PromptTemplate(
        template="""Summarize the following text in a brief, concise manner. Focus on the main points and key concepts.

Text: {text}

Summary:""",
        input_variables=["text"],
    )

    # Create a chain with the template and LLM
    summary_chain = summary_template | merlin_llm

    # Test summarization
    response = summary_chain.invoke({"text": fake_text})

    # Extract content
    if hasattr(response, "content"):
        summary = response.content
    elif isinstance(response, str):
        summary = response
    else:
        summary = str(response)

    # Verify the summary
    assert summary is not None
    assert len(summary) > 0
    assert len(summary) < len(fake_text)  # Summary should be shorter than original
    # Check that key concepts are mentioned
    assert (
        "AI" in summary
        or "artificial intelligence" in summary.lower()
        or "machine learning" in summary.lower()
    )
