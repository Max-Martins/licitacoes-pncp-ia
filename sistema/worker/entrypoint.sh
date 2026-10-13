#!/bin/bash
# API (n8n) na 8765 e servidor MCP na 8766; se um cair, o container reinicia.
uvicorn app.main:app --host 0.0.0.0 --port 8765 --workers 2 &
python -m app.mcp_server &
wait -n
exit $?
