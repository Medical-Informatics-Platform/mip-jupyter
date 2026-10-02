# Project Memory

## Purpose
Runtime memory support for LLM/Codex work in this repository.

## Static instruction sources
- `AGENTS.md`
- `docs/llm/INDEX.md`
- `docs/llm/wiki/*.md`

## Runtime state
- `.llm/chats/<chat_id>/`

## Important rule
`.llm` runtime state augments static instructions. It does not override them.

## Secret policy
Do not store secrets or raw sensitive outputs.

## Notebook policy
Track notebook path, stable cell marker, execution status, and summarized outputs/errors.
