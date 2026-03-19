# AI Agents Configuration

This document outlines the architecture and configuration of AI agents (Support Assistants) within the RAG Chat Service.

## Overview

The system implements a multi-tenant **Retrieval-Augmented Generation (RAG)** architecture. Each tenant can configure their own AI agent, which serves as a professional support assistant for their users.

## Agent Architecture

### 1. Retrieval Pipeline
- **Vector Database**: PostgreSQL with `pgvector`.
- **Embedding Model**: `text-embedding-3-small` (1536 dimensions).
- **Strategy**: Semantic search retrieves the top `N` relevant context chunks from the tenant's knowledge base. `N` is determined by the tenant's subscription plan.

### 2. LLM Orchestration
- **Providers**: OpenAI.
- **Models**: `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`.
- **Streaming**: Supported via FastAPI `StreamingResponse`.

### 3. Prompt Engineering
The `PromptBuilder` constructs system prompts with the following core instructions:
- **Identity**: Professional and friendly AI assistant.
- **Strict Context Adherence**: Assistants must answer primarily based on the provided context.
- **Hallucination Prevention**: If information is missing from the context, the agent is instructed to state it doesn't know rather than inventing facts.
- **Sanitization**: Built-in protection against prompt injection attacks (e.g., ignoring "ignore all previous instructions" patterns).

## Configuration

### Tenant-Level Customization
Each agent is customizable via the `ChatbotConfig` and `TenantConfig` models:
- **DisplayName**: Custom name (e.g., "HelpBot").
- **Welcome Message**: Initial greeting for the chat widget.
- **Visuals**: Primary/background colors and logo URLs.
- **Limits**: Plan-based constraints on token usage, model access, and context window size.

### System Safeguards
- **Rate Limiting**: Enforced at the API level (e.g., 10 requests/min).
- **Cost Tracking**: Each interaction tracks token usage (prompt/completion) and USD cost.
- **Caching**: 24-hour Redis TTL for identical queries to minimize LLM costs and latency.

## Development & Docker Environment

The application is containerized using Docker for consistent development and deployment environments.

### 1. Docker Services
- **`web`**: The main FastAPI application serving the RAG API and widget.
  - **Port**: Accessible on `8001`.
  - **Runtime**: Uses `gunicorn` with `uvicorn` workers in production/final images.
  - **Hot-Reload**: Local `app/`, `tests/`, and `static/` directories are volume-mounted to allow real-time code changes.
- **`redis`**: Used for 24-hour result caching and as a broker for Celery tasks.
- **`worker`**: A Celery worker instance that handles background tasks like persisting chat responses to the database.

### 2. Running the Application
To start the entire stack:
```bash
docker-compose up --build
```

### 3. Running Tests
Tests are located in the `tests/` directory and should be executed within the `web` container to ensure all environment variables and dependencies are present:
```bash
docker-compose exec web pytest
```

## Key Files
- `app/services/chat_service.py`: Core RAG orchestration logic.
- `app/prompt/builder.py`: System prompt construction and sanitization.
- `app/core/llm.py`: OpenAI API integration.
- `app/db/models.py`: Database schemas for `ChatbotConfig` and `Tenant`.
- `migrations`: Alembic migrations for database schema changes.
