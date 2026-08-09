# Sentinel

## Autonomous Multi-Agent Engineering Ops Copilot

Sentinel is a production-oriented AI engineering system that autonomously
investigates software engineering incidents, plans fixes, uses controlled
tools to inspect and modify repositories, verifies changes through automated
testing, learns from previous incidents, and reports execution outcomes.

## Vision

Sentinel aims to demonstrate modern AI engineering patterns including:

- Multi-agent orchestration
- Planning and autonomous workflows
- Tool calling
- Model Context Protocol (MCP)
- Agent memory
- Automated verification
- Evaluation
- Observability
- Human-in-the-loop controls
- Production-oriented architecture

## Current Status

🚧 Project initialization — Sprint 0

## Technology

- Python
- LangGraph
- LangChain
- Ollama
- MCP
- FastAPI
- ChromaDB
- SQLite
- Pytest
- Docker

## Architecture

The project follows Clean Architecture principles with explicit separation
between domain logic, application services, infrastructure, agent
orchestration, and external interfaces.

## Development

### Install dependencies

```bash
uv sync
