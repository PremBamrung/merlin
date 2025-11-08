# 🧙‍♂️ Merlin

Merlin is a versatile chatbot application built with Streamlit that combines conversational AI with powerful integrations for YouTube video processing, web search, and knowledge management. Engage in dynamic conversations or harness integrated functionalities like YouTube subtitle extraction and summarization to build a comprehensive knowledge database effortlessly.

## ✨ Features

### 🤖 Conversational AI
- **Interactive Chat Interface**: Engage in natural conversations with an AI assistant
- **Multiple LLM Providers**: Support for OpenRouter and Azure OpenAI
- **Streaming Responses**: Real-time streaming of AI responses for better user experience
- **Conversation History**: Maintain context across multiple interactions

### 📺 YouTube Integration
- **Video Summarization**: Automatically extract and summarize YouTube video content
- **Subtitle Extraction**: Extract subtitles in multiple languages (English, French, German)
- **Smart Caching**: Cache video summaries to avoid reprocessing
- **Flexible Summary Lengths**: Choose from short, medium, or long summaries
- **Video Metadata**: Extract and display video information including:
  - Title, channel, views, duration
  - Publication date
  - Subscriber count
  - Video thumbnail
- **Tag Organization**: Organize summaries with custom tags
- **Search & Filter**: Search through your video database by title, channel, content, or tags
- **Topic Extraction**: Automatically extract key topics and timestamps

### 🔍 Web Search
- **LangChain Integration**: Powered by LangChain agents for intelligent web searches
- **DuckDuckGo Search**: Real-time web search capabilities

### 💾 Knowledge Database
- **SQLite Database**: Store all video summaries and metadata locally
- **Persistent Storage**: Your knowledge base persists across sessions
- **Easy Retrieval**: Quick access to all summarized content

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd merlin
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Create a `.env` file in the `merlin/` directory with the following variables:

   **For OpenRouter:**
   ```env
   OPENROUTER_API_KEY=your_openrouter_api_key
   OPENROUTER_MODEL_DEPLOYMENT=your_model_name
   OPENROUTER_ENDPOINT=https://openrouter.ai/api/v1
   ```

   **For Azure OpenAI (alternative):**
   ```env
   AZURE_OPENAI_ENDPOINT=your_azure_endpoint
   AZURE_OPENAI_KEY=your_azure_key
   AZURE_OPENAI_API_VERSION=your_api_version
   AZURE_MODEL_DEPLOYMENT=your_deployment_name
   ```

4. **Run the application**
   ```bash
   streamlit run Home.py
   ```

   The application will open in your default web browser at `http://localhost:8501`

## 📖 Usage

### Main Chat Interface
- Start a conversation by typing in the chat input
- Paste a YouTube URL directly in the chat to automatically summarize the video
- Use the sidebar button to clear conversation history

### YouTube Video Summarizer
Navigate to the **YouTube** page from the sidebar to:
- **Summarize a Video**:
  - Enter a YouTube video URL
  - Select your preferred language (English, French, German)
  - Choose summary length (short, medium, long)
  - Add optional tags for organization
  - Click "Summarize" to process the video

- **View Summarized Videos**:
  - Browse all previously summarized videos
  - Search by title, channel, or content
  - Filter by tags
  - View cached summaries instantly

### QA & Search
Access the **QA** page for web-enabled search capabilities using LangChain agents.

## 📁 Project Structure

```
merlin/
├── Home.py                 # Main Streamlit application entry point
├── pages/                  # Streamlit multi-page application pages
│   ├── 01_Youtube.py      # YouTube video summarization page
│   ├── 02_QA.py           # QA and search page
│   └── 03_Blogs.py        # Blog-related features
├── merlin/                 # Core application package
│   ├── llm/               # LLM provider integrations
│   │   ├── openrouter.py  # OpenRouter LLM implementation
│   │   └── azureopenai.py # Azure OpenAI LLM implementation
│   ├── integration/       # External service integrations
│   │   ├── youtube/       # YouTube integration module
│   │   └── reddit.py      # Reddit integration
│   ├── database/          # Database models and repositories
│   │   ├── models.py      # SQLAlchemy models
│   │   └── repositories.py # Data access layer
│   └── utils.py           # Utility functions
├── merlin.db              # SQLite database file
├── requirements.txt       # Python dependencies
├── LICENSE                # Apache License 2.0
└── README.md              # This file
```

## 🛠️ Dependencies

- **streamlit**: Web application framework
- **langchain**: LLM framework and agent tools
- **langchain_openai**: OpenAI integration for LangChain
- **pytube**: YouTube video metadata extraction
- **youtube_transcript_api**: YouTube subtitle extraction
- **sqlalchemy**: Database ORM
- **python-dotenv**: Environment variable management
- **Pillow**: Image processing

See `requirements.txt` for complete dependency list with versions.

## 🔧 Configuration

### LLM Provider Selection
The application uses OpenRouter by default. To switch to Azure OpenAI, modify the import in `Home.py`:

```python
# Change from:
from merlin.llm.openrouter import llm

# To:
from merlin.llm.azureopenai import llm
```

### Database
The application uses SQLite by default (`merlin.db`). The database is automatically initialized on first run. To reset the database, simply delete the `merlin.db` file.

## 📝 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Support

For issues, questions, or contributions, please open an issue on the repository.

---

**Note**: Make sure to keep your API keys secure and never commit them to version control. The `.env` file should be added to `.gitignore`.
