#!/usr/bin/env python3
"""
Test script for Azure OpenAI connection.
Tests the connection and basic functionality of the Azure OpenAI LLM.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from project root
project_root = Path(__file__).parent
env_path = project_root / ".env"
load_dotenv(env_path)

# Check environment variables before importing LLM
required_vars = {
    "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
    "AZURE_OPENAI_KEY": os.getenv("AZURE_OPENAI_KEY"),
    "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
    "AZURE_MODEL_DEPLOYMENT": os.getenv("AZURE_MODEL_DEPLOYMENT"),
}

missing_vars = [var for var, value in required_vars.items() if not value]
if missing_vars:
    print("=" * 80)
    print("❌ Missing required environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\nPlease ensure your .env file contains all required variables:")
    print("   - AZURE_OPENAI_ENDPOINT")
    print("   - AZURE_OPENAI_KEY")
    print("   - AZURE_OPENAI_API_VERSION")
    print("   - AZURE_MODEL_DEPLOYMENT")
    print("=" * 80)
    sys.exit(1)

# Now import LLM and other modules
from langchain_core.prompts import PromptTemplate

from merlin.llm.azureopenai import llm
from merlin.utils import logger


def test_environment_variables():
    """Test that all required environment variables are present."""
    print("=" * 80)
    print("Azure OpenAI Connection Test")
    print("=" * 80)
    print("\n1. Checking environment variables...")
    print("-" * 80)

    required_vars = {
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_KEY": os.getenv("AZURE_OPENAI_KEY"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
        "AZURE_MODEL_DEPLOYMENT": os.getenv("AZURE_MODEL_DEPLOYMENT"),
    }

    all_present = True
    for var_name, var_value in required_vars.items():
        if var_value:
            # Mask the key for security
            if "KEY" in var_name:
                masked_value = (
                    var_value[:8] + "..." + var_value[-4:]
                    if len(var_value) > 12
                    else "***"
                )
                print(f"  ✅ {var_name}: {masked_value}")
            else:
                print(f"  ✅ {var_name}: {var_value}")
        else:
            print(f"  ❌ {var_name}: NOT SET")
            all_present = False

    if not all_present:
        print("\n❌ Missing required environment variables!")
        return False

    print("\n✅ All environment variables are present")
    return True


def test_llm_initialization():
    """Test that the LLM object is properly initialized."""
    print("\n2. Testing LLM initialization...")
    print("-" * 80)

    try:
        # Check LLM attributes
        print(f"  ✅ LLM object created: {type(llm).__name__}")
        print(f"  ✅ Deployment name: {llm.deployment_name}")
        print(f"  ✅ Azure endpoint: {llm.azure_endpoint}")
        print(f"  ✅ API version: {llm.openai_api_version}")
        print(f"  ✅ Temperature: {llm.temperature}")
        print(f"  ✅ Streaming: {llm.streaming}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to initialize LLM: {str(e)}")
        return False


def test_simple_completion():
    """Test a simple completion request."""
    print("\n3. Testing simple completion...")
    print("-" * 80)

    try:
        # Create a simple prompt
        prompt = "Say 'Hello, Azure OpenAI is working!' in one sentence."

        print(f"  Prompt: {prompt}")
        print("  Sending request...")

        # Make a simple call
        response = llm.invoke(prompt)

        # Extract content
        if hasattr(response, "content"):
            content = response.content
        elif isinstance(response, str):
            content = response
        else:
            content = str(response)

        print(f"  ✅ Response received:")
        print(f"  {content}")
        return True, content

    except Exception as e:
        print(f"  ❌ Failed to get completion: {str(e)}")
        logger.exception("Completion test failed")
        return False, None


def test_streaming_completion():
    """Test a streaming completion request."""
    print("\n4. Testing streaming completion...")
    print("-" * 80)

    try:
        prompt = "Count from 1 to 5, one number per line."

        print(f"  Prompt: {prompt}")
        print("  Streaming response:")
        print("-" * 80)

        full_response = ""
        chunk_count = 0

        for chunk in llm.stream(prompt):
            # Extract content from chunk
            if hasattr(chunk, "content"):
                content = chunk.content
            elif isinstance(chunk, str):
                content = chunk
            else:
                content = str(chunk) if chunk else ""

            if content:
                print(content, end="", flush=True)
                full_response += content
                chunk_count += 1

        print("\n" + "-" * 80)
        print(f"  ✅ Streaming completed: {chunk_count} chunks received")
        print(f"  ✅ Total response length: {len(full_response)} characters")
        return True, full_response

    except Exception as e:
        print(f"\n  ❌ Failed to stream completion: {str(e)}")
        logger.exception("Streaming test failed")
        return False, None


def test_prompt_template():
    """Test using a prompt template with the LLM."""
    print("\n5. Testing prompt template...")
    print("-" * 80)

    try:
        template = PromptTemplate(
            template="Write a {length} summary about {topic}.",
            input_variables=["length", "topic"],
        )

        chain = template | llm

        prompt_input = {"length": "brief", "topic": "artificial intelligence"}

        print(f"  Template: {template.template}")
        print(f"  Input: {prompt_input}")
        print("  Sending request...")

        response = chain.invoke(prompt_input)

        # Extract content
        if hasattr(response, "content"):
            content = response.content
        elif isinstance(response, str):
            content = response
        else:
            content = str(response)

        print(f"  ✅ Response received:")
        print(f"  {content}")
        return True, content

    except Exception as e:
        print(f"  ❌ Failed to use prompt template: {str(e)}")
        logger.exception("Prompt template test failed")
        return False, None


def main():
    """Run all tests."""
    try:
        # Test 1: Environment variables
        if not test_environment_variables():
            print("\n" + "=" * 80)
            print("❌ Test failed: Environment variables not configured")
            print("=" * 80)
            return False

        # Test 2: LLM initialization
        if not test_llm_initialization():
            print("\n" + "=" * 80)
            print("❌ Test failed: LLM initialization error")
            print("=" * 80)
            return False

        # Test 3: Simple completion
        success, _ = test_simple_completion()
        if not success:
            print("\n" + "=" * 80)
            print("❌ Test failed: Simple completion error")
            print("=" * 80)
            return False

        # Test 4: Streaming completion
        success, _ = test_streaming_completion()
        if not success:
            print("\n" + "=" * 80)
            print("❌ Test failed: Streaming completion error")
            print("=" * 80)
            return False

        # Test 5: Prompt template
        success, _ = test_prompt_template()
        if not success:
            print("\n" + "=" * 80)
            print("❌ Test failed: Prompt template error")
            print("=" * 80)
            return False

        print("\n" + "=" * 80)
        print("✅ All tests completed successfully!")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n❌ Unexpected error during test: {str(e)}")
        logger.exception("Test suite failed with exception")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
