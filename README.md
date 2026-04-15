# ANKOR Voice Agent Service

Minimal FastAPI skeleton for the future ANKOR voice agent service.

This initial scaffold intentionally keeps the scope narrow:

- FastAPI application entrypoint
- Environment-based settings with `pydantic-settings`
- Basic structured JSON logging
- `/health` endpoint
- One small test

Planned integrations such as Strands, Amazon Bedrock Nova Sonic, AgentCore Memory, and ANKOR backend tool calls are not implemented yet.

## Requirements

- Python 3.12

## Local development

Install the project and test dependencies:

```bash
pip install -e ".[dev]"
```

Run the service:

```bash
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest
```

## Environment variables

All settings use the `ANKOR_VOICE_` prefix.

- `ANKOR_VOICE_APP_NAME`
- `ANKOR_VOICE_ENVIRONMENT`
- `ANKOR_VOICE_LOG_LEVEL`
