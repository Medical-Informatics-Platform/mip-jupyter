"""Write Jupyter AI MCP configuration for mip-jupyter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .jupyter_mcp_tools import SAFE_JUPYTER_MCP_TOOLS
from .mip_acp_persona import MIP_PERSONA_ID
from .mip_persona_manager import build_persona_manager_config


def build_config(*, mcp_port: int | None = None) -> dict:
    extension_config: dict = {
        "use_tool_discovery": False,
        "mcp_tools": SAFE_JUPYTER_MCP_TOOLS,
    }
    if mcp_port is not None:
        extension_config["mcp_port"] = mcp_port
    config = {
        "MCPExtensionApp": extension_config,
        # RTC sync can leave cells stuck on [*] behind Hub/nginx proxies.
        "YDocExtension": {"disable_rtc": True},
        # Keep kernel websocket pings within nginx/proxy limits (see ServerApp warning).
        "ServerApp": {
            "websocket_ping_interval": 30000,
            "websocket_ping_timeout": 30000,
        },
    }
    config.update(
        build_persona_manager_config(
            default_persona_id=MIP_PERSONA_ID,
            builtin_mcp_servers=[],
        )
    )
    return config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write mip-jupyter Jupyter AI MCP config.")
    parser.add_argument("path", help="Output JSON config path")
    parser.add_argument("--mcp-port", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    path = Path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_config(mcp_port=args.mcp_port), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
