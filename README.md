# Reddit Comment Analysis API

A high-performance FastAPI-based web service for analyzing Reddit comments using AI-powered sentiment analysis, theme extraction, and purchase intent detection.

## 🚀 Features

- **FastAPI Framework**: High-performance async API with automatic OpenAPI documentation
- **AI-Powered Analysis**: Advanced comment analysis using Pydantic AI with multiple model support
- **Configurable Analysis**: Customizable keywords, subreddits, timeframes, and AI models
- **Structured Responses**: Clean JSON responses with detailed metadata
- **Production Ready**: Comprehensive logging, error handling, and configuration management
- **Development Tools**: Full testing suite, linting, formatting, and type checking

## 🏗️ Project Structure

```
reddit_sl_api/
├── reddit-build/                 # Main application directory
│   ├── app/                     # Application core
│   │   ├── agents/              # AI analysis agents
│   │   │   ├── __init__.py
│   │   │   └── comment_analyzer.py
│   │   ├── api/                 # API routes
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   ├── core/                # Core configuration
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── models/              # Data models
│   │   │   ├── __init__.py
│   │   │   └── schemas.py
│   │   ├── services/            # Business logic
│   │   │   ├── __init__.py
│   │   │   └── reddit_collector.py
│   │   ├── __init__.py
│   │   └── main.py              # FastAPI application
│   ├── tests/                   # Test suite
│   │   ├── __init__.py
│   │   └── test_main.py
│   └── docs/                    # Documentation
├── requirements.txt             # Dependencies
├── pyproject.toml              # Tool configuration
├── .flake8                     # Linting configuration
├── pytest.ini                 # Test configuration
├── Makefile                    # Development commands
└── README.md                   # This file
```

## 🛠️ Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

## 📦 Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd reddit_sl_api
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
make install
# or manually:
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the `reddit-build/` directory:

```env
# API Keys
RAPID_API_KEY=your_rapid_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Application Settings
LOG_LEVEL=INFO
DEBUG=false
APP_VERSION=v2
MAX_CONCURRENT_AGENTS=5

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

## 🚀 Quick Start

### Development Server

```bash
make dev
# or manually:
cd reddit-build && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Production Server

```bash
make run-prod
# or manually:
cd reddit-build && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 🧪 Development Commands

The project includes a comprehensive Makefile for common development tasks:

```bash
# View all available commands
make help

# Development workflow
make setup          # Complete development setup
make dev             # Start development server with hot reload
make test            # Run test suite
make lint            # Run code linting
make format          # Format code with black
make type-check      # Run type checking with mypy
make build           # Run all checks (format, lint, type-check, test)
make clean           # Clean cache and build files
```

## 📋 API Endpoints

### Health Check

```http
GET /health
```

Returns API status and version information.

### Analyze Reddit Comments

```http
POST /analyze-reddit-comments
Content-Type: application/json

{
  "keywords": ["BMW R 12 GS", "motorcycle"],
  "subreddits": ["motorcycles", "BMW"],
  "timeframe": "week",
  "limit": 10,
  "model": "gemini-2.5-pro",
  "api_key": "your_api_key",
  "system_prompt": "You are an expert social media analyst...",
  "output_format": "json",
  "max_quote_length": 200
}
```

### API Status

```http
GET /status
```

Returns detailed API status, configuration, and capabilities.

## 🔧 Configuration

### Environment Variables

| Variable                | Description                    | Default   |
| ----------------------- | ------------------------------ | --------- |
| `RAPID_API_KEY`         | RapidAPI key for Reddit access | Required  |
| `GEMINI_API_KEY`        | Google Gemini API key          | Required  |
| `OPENAI_API_KEY`        | OpenAI API key                 | Required  |
| `LOG_LEVEL`             | Logging level                  | `INFO`    |
| `DEBUG`                 | Debug mode                     | `false`   |
| `MAX_CONCURRENT_AGENTS` | Max parallel AI agents         | `5`       |
| `HOST`                  | Server host                    | `0.0.0.0` |
| `PORT`                  | Server port                    | `8000`    |

### Supported AI Models

- `gemini-2.5-pro` (default)
- `gpt-4`
- `claude-3-sonnet`

## 🧪 Testing

### Run Tests

```bash
make test
# or manually:
cd reddit-build && python -m pytest tests/ -v
```

### Test Coverage

The test suite includes:

- API endpoint testing
- Request/response validation
- Error handling verification
- Async functionality testing
- Model validation testing

### Writing Tests

Tests are located in `reddit-build/tests/`. Use pytest with async support:

```python
import pytest
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_my_async_function():
    # Your async test here
    pass
```

## 🎨 Code Quality

### Formatting

Code is formatted using [Black](https://github.com/psf/black):

```bash
make format
```

### Linting

Code is linted using [Flake8](https://flake8.pycqa.org/):

```bash
make lint
```

### Type Checking

Type checking is performed using [MyPy](https://mypy.readthedocs.io/):

```bash
make type-check
```

## 📈 Performance

- **Async Architecture**: Built on FastAPI's async foundation
- **Concurrent Processing**: Configurable concurrent AI agents
- **Efficient Data Models**: Pydantic models with optimized serialization
- **Background Tasks**: Support for background processing

## 🔒 Security

- **Environment Variables**: Sensitive data stored in environment variables
- **Input Validation**: Comprehensive request validation using Pydantic
- **Error Handling**: Safe error responses without sensitive information exposure
- **CORS Configuration**: Configurable CORS for cross-origin requests

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're in the correct directory and virtual environment is activated
2. **API Key Issues**: Verify `.env` file exists and contains valid API keys
3. **Port Conflicts**: Change the port in configuration if 8000 is in use
4. **Dependencies**: Run `make install` to ensure all dependencies are installed

### Debug Mode

Enable debug mode in `.env`:

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Run tests and checks: `make build`
4. Commit your changes: `git commit -am 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

### Development Workflow

```bash
# Setup development environment
make setup

# Make your changes
# ...

# Run all checks before committing
make build

# If all checks pass, commit and push
git add .
git commit -m "Your commit message"
git push
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

- Check the troubleshooting section above
- Review API documentation at `/docs` endpoint
- Open an issue in the repository

---

**Happy coding! 🚀**
