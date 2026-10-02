"""Restrict Jupyter AI to the MIP Cohort Scout persona only."""

from __future__ import annotations

from jupyter_ai_persona_manager.persona_manager import PersonaManager

MIP_PERSONA_MANAGER_CLASS = "mip_jupyter_dev.mip_persona_manager.MipPersonaManager"
ALLOWED_PERSONA_ENTRY_POINTS = frozenset({"cohort-scout"})


def build_persona_manager_config(
    *,
    default_persona_id: str,
    builtin_mcp_servers: list | None = None,
) -> dict:
    persona_manager_config: dict = {"default_persona_id": default_persona_id}
    if builtin_mcp_servers is not None:
        persona_manager_config["builtin_mcp_servers"] = builtin_mcp_servers
    return {
        "PersonaManagerExtension": {
            "persona_manager_class": MIP_PERSONA_MANAGER_CLASS,
        },
        "PersonaManager": persona_manager_config,
    }


class MipPersonaManager(PersonaManager):
    """Load only the Cohort Scout entry point; hide stock ACP personas such as Codex."""

    def _init_ep_persona_classes(self) -> None:
        super()._init_ep_persona_classes()
        loaded = PersonaManager._ep_persona_classes or []
        filtered = [item for item in loaded if item.get("module") in ALLOWED_PERSONA_ENTRY_POINTS]
        skipped = len(loaded) - len(filtered)
        if skipped:
            self.log.info(
                "Filtered out %d third-party Jupyter AI persona entry points; "
                "only %s are enabled.",
                skipped,
                ", ".join(sorted(ALLOWED_PERSONA_ENTRY_POINTS)),
            )
        PersonaManager._ep_persona_classes = filtered

    def _init_local_persona_classes(self) -> None:
        self.log.info(
            "Skipping local .jupyter/personas loading; MIP exposes Cohort Scout only."
        )
        self._local_persona_classes = []
