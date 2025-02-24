#!/bin/bash

# Check if .env file exists
if [ -f .env ]; then
    echo ".env file already exists. Do you want to overwrite it? (y/n)"
    read answer
    if [ "$answer" != "y" ]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Copy example env file
cp .env.example .env

echo "Please enter your environment variables:"

# Azure OpenAI
echo -n "Azure OpenAI Key (press enter to skip): "
read azure_key
if [ ! -z "$azure_key" ]; then
    sed -i "s/AZURE_OPENAI_KEY=.*/AZURE_OPENAI_KEY=$azure_key/" .env
fi

echo -n "Azure OpenAI Endpoint (press enter to skip): "
read azure_endpoint
if [ ! -z "$azure_endpoint" ]; then
    sed -i "s|AZURE_OPENAI_ENDPOINT=.*|AZURE_OPENAI_ENDPOINT=$azure_endpoint|" .env
fi

echo -n "Azure OpenAI Deployment Name (press enter to skip): "
read azure_deployment
if [ ! -z "$azure_deployment" ]; then
    sed -i "s/AZURE_OPENAI_DEPLOYMENT=.*/AZURE_OPENAI_DEPLOYMENT=$azure_deployment/" .env
fi

# OpenRouter
echo -n "OpenRouter API Key (press enter to skip): "
read openrouter_key
if [ ! -z "$openrouter_key" ]; then
    sed -i "s/OPENROUTER_API_KEY=.*/OPENROUTER_API_KEY=$openrouter_key/" .env
fi

# Make the script executable
# chmod +x setup_env.sh

echo "Environment setup complete! You can now run 'docker-compose up --build'"
