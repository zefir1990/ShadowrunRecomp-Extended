from __future__ import annotations

import sys
from pathlib import Path

MCP_SERVER_DIRECTORY = Path(__file__).resolve().parents[2] / "genesis-mcp"
if str(MCP_SERVER_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIRECTORY))
