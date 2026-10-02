"""MIP-branded Jupyter AI persona backed by Codex ACP."""

from __future__ import annotations

from acp.exceptions import RequestError
from jupyter_ai_acp_client.acp_personas.codex import CodexAcpPersona
from jupyter_ai_acp_client.base_acp_persona import BaseAcpPersona
from jupyter_ai_persona_manager import PersonaDefaults
from jupyterlab_chat.models import Message

MIP_PERSONA_NAME = "Cohort Scout"
MIP_PERSONA_ID = "jupyter-ai-personas::dev::CohortScoutPersona"
MIP_PERSONA_DESCRIPTION = (
    "MIP notebook assistant for cohort discovery and federated analysis, not general chat."
)
VLLM_UNAVAILABLE_MESSAGE = (
    "Cohort Scout cannot reach the vLLM model service right now."
    "\n\nYour notebook and MIP platform connection are unaffected, but AI chat replies "
    "are unavailable until the model service is back."
    "\n\nTry again later, or ask your platform administrator to check the Jupyter AI "
    "model service. For local development, verify `CODEX_VLLM_BASE_URL` points to a "
    "reachable `/v1` endpoint."
)

TOOL_CALL_PARSE_ERROR_MESSAGE = (
    "Cohort Scout hit a tool-call formatting error from the local model."
    "\n\nThis usually happens when a long code payload is sent in one tool call and "
    "the model returns invalid JSON. Your notebook and MIP connection are fine."
    "\n\nStart a **new chat** and resume from existing `scratch/*.py` artifacts with "
    "smaller steps (`scratch-list`, then `scratch-write-file` or "
    "`scratch-replace-snippet`). Continue the newest complete script in scratch/. "
    "Do not retry write commands without `scratch-list` or "
    "`notebook-outline` first. Do not retry heredocs or large shell writes."
)

_VLLM_UNAVAILABLE_MARKERS = (
    "connection refused",
    "connection reset",
    "connect error",
    "connection error",
    "connection closed",
    "failed to connect",
    "failed sending request",
    "error sending request",
    "tcp connect error",
    "network is unreachable",
    "no route to host",
    "temporarily unavailable",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "timed out",
    "timeout",
    "503",
    "502",
    "504",
    "vllm",
)


_TOOL_CALL_PARSE_MARKERS = (
    "expecting ',' delimiter",
    "failed to parse function arguments",
    "invalid number at line",
    "badrequesterror",
    "json decode",
)


def _error_text(error: BaseException) -> str:
    parts = [str(error)]
    data = getattr(error, "data", None)
    if data is not None:
        parts.append(str(data))
    cause = getattr(error, "__cause__", None)
    if cause is not None:
        parts.append(str(cause))
    context = getattr(error, "__context__", None)
    if context is not None:
        parts.append(str(context))

    return " ".join(parts)


def is_tool_call_parse_error(error: BaseException) -> bool:
    """Return whether an ACP/Codex error likely means the model returned bad tool JSON."""

    text = _error_text(error).lower()
    return any(marker in text for marker in _TOOL_CALL_PARSE_MARKERS)


def is_vllm_unavailable_error(error: BaseException) -> bool:
    """Return whether an ACP/Codex error likely means the vLLM service is down."""

    if is_tool_call_parse_error(error):
        return False

    text = _error_text(error).lower()
    return any(marker in text for marker in _VLLM_UNAVAILABLE_MARKERS)


class CohortScoutPersona(CodexAcpPersona):
    @property
    def defaults(self) -> PersonaDefaults:
        base = super().defaults
        return PersonaDefaults(
            name=MIP_PERSONA_NAME,
            description=MIP_PERSONA_DESCRIPTION,
            avatar_path=base.avatar_path,
            system_prompt=base.system_prompt,
        )

    async def process_message(self, message: Message) -> None:
        try:
            await BaseAcpPersona.process_message(self, message)
        except RequestError as error:
            if is_tool_call_parse_error(error):
                await self.handle_tool_call_parse_error(error)
                return
            if is_vllm_unavailable_error(error):
                await self.handle_vllm_unavailable(error)
                return
            if error.code == -32000:
                self.log.info("[%s] Authentication required: %s", MIP_PERSONA_NAME, error)
                await self.handle_no_auth(message)
                return
            raise
        except Exception as error:
            if is_tool_call_parse_error(error):
                await self.handle_tool_call_parse_error(error)
                return
            if is_vllm_unavailable_error(error):
                await self.handle_vllm_unavailable(error)
                return
            raise

    async def handle_uncaught_exception(self, exc: Exception) -> None:
        if is_tool_call_parse_error(exc):
            await self.handle_tool_call_parse_error(exc)
            return
        if is_vllm_unavailable_error(exc):
            await self.handle_vllm_unavailable(exc)
            return
        await super().handle_uncaught_exception(exc)

    async def handle_tool_call_parse_error(self, error: BaseException) -> None:
        self.log.warning("[%s] tool-call JSON parse error: %s", MIP_PERSONA_NAME, error)
        self.send_message(TOOL_CALL_PARSE_ERROR_MESSAGE)

    async def handle_vllm_unavailable(self, error: BaseException) -> None:
        self.log.warning("[%s] vLLM unavailable: %s", MIP_PERSONA_NAME, error)
        self.send_message(VLLM_UNAVAILABLE_MESSAGE)
