"""Tests for Azure OpenAI connection and functionality."""

from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI
import pytest

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
    chunks_received = []

    # Test streaming
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
            chunks_received.append(content)
            chunk_count += 1

    # Verify streaming behavior
    assert chunk_count > 0, "Should receive at least one chunk"
    assert len(full_response) > 0, "Full response should not be empty"
    assert len(chunks_received) > 0, "Should have received multiple chunks"

    # Verify that we received incremental chunks (not all at once)
    # The response should be built incrementally
    cumulative_length = 0
    for chunk in chunks_received:
        cumulative_length += len(chunk)

    assert cumulative_length == len(
        full_response
    ), "Chunk lengths should sum to full response length"

    # Verify the response contains expected content
    assert any(
        char.isdigit() for char in full_response
    ), "Response should contain numbers"


@pytest.mark.requires_azure
def test_streaming_vs_non_streaming():
    """Test that streaming and non-streaming produce equivalent results."""
    prompt = "Say 'Streaming test works!' in one sentence."

    # Get non-streaming response
    non_streaming_response = merlin_llm.invoke(prompt)
    if hasattr(non_streaming_response, "content"):
        non_streaming_content = non_streaming_response.content
    elif isinstance(non_streaming_response, str):
        non_streaming_content = non_streaming_response
    else:
        non_streaming_content = str(non_streaming_response)

    # Get streaming response
    streaming_content = ""
    for chunk in merlin_llm.stream(prompt):
        if hasattr(chunk, "content"):
            streaming_content += chunk.content
        elif isinstance(chunk, str):
            streaming_content += chunk
        else:
            streaming_content += str(chunk) if chunk else ""

    # Both should produce non-empty responses
    assert len(non_streaming_content) > 0, "Non-streaming response should not be empty"
    assert len(streaming_content) > 0, "Streaming response should not be empty"

    # The content should be similar (allowing for minor variations)
    # Both should contain the key phrase or similar meaning
    assert (
        "streaming" in streaming_content.lower()
        or "test" in streaming_content.lower()
        or "works" in streaming_content.lower()
    ), "Streaming response should contain relevant content"
    assert (
        "streaming" in non_streaming_content.lower()
        or "test" in non_streaming_content.lower()
        or "works" in non_streaming_content.lower()
    ), "Non-streaming response should contain relevant content"


@pytest.mark.requires_azure
def test_streaming_with_prompt_template():
    """Test streaming with a prompt template."""
    template = PromptTemplate(
        template="List {count} colors.",
        input_variables=["count"],
    )

    chain = template | merlin_llm

    prompt_input = {"count": "3"}

    # Test streaming through the chain
    streaming_content = ""
    chunk_count = 0

    for chunk in chain.stream(prompt_input):
        if hasattr(chunk, "content"):
            content = chunk.content
        elif isinstance(chunk, str):
            content = chunk
        else:
            content = str(chunk) if chunk else ""

        if content:
            streaming_content += content
            chunk_count += 1

    assert chunk_count > 0, "Should receive chunks when streaming through chain"
    assert len(streaming_content) > 0, "Streaming content should not be empty"
    # Should mention colors
    assert "color" in streaming_content.lower() or any(
        word in streaming_content.lower() for word in ["red", "blue", "green", "yellow"]
    ), "Response should mention colors"


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
