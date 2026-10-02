# LLM Runtime State

`.llm/` is lightweight filesystem memory for Codex and other LLM agents working in this repository. It stores compact runtime state from actual work so agents can resume after context compaction, handle pivots, and track notebook or MIP analysis work without turning chat history into the source of truth.

Core principle:

```text
Chat is not memory.
Filesystem is memory.
Always rehydrate before continuing.
```

`.llm/` augments the existing repository instructions. It does not replace `AGENTS.md` or `docs/llm/`.

## What Belongs Here

- `.llm/project.md` - compact project-level runtime memory.
- `.llm/templates/` - reusable templates for chat runtime state.
- `.llm/chats/<chat_id>/` - per-chat runtime state created only when useful for resumable work.

Runtime chat folders should use this shape:

```text
.llm/chats/<chat_id>/
  state.md
  handoff.md
  journal.md
  decisions.md
  artifacts.md
  objectives/
    objective-001.md
  archive/
```

Do not create a chat folder for a tiny one-shot edit unless the user asks or the work is likely to resume later.

## What Must Never Be Stored

Never write secrets, tokens, credentials, private connection strings, raw private data, or full sensitive notebook outputs into `.llm/`.

Summarize sensitive outputs instead of copying them.

Do not commit `.llm/chats/` runtime state unless explicitly requested.

## Precedence

Use this order when instructions or state disagree:

```text
system/developer instructions
> repo AGENTS.md
> docs/llm static playbook
> active user request
> active objective file
> state.md
> handoff.md
> decisions.md
> journal.md
> archived / old objectives
```

The active user request controls the current task within the higher-priority safety and repository rules. Old `.llm/` state must not override a newer user instruction.

## BOOT

Follow the existing MIP Jupyter startup flow first, then use runtime state only when continuing work:

1. Obey system/developer instructions.
2. Read `AGENTS.md`.
3. Read `docs/llm/INDEX.md`.
4. Read one relevant `docs/llm/wiki/` page.
5. Read `.llm/project.md` if present.
6. Read `.llm/chats/<chat_id>/state.md` if present.
7. Read `.llm/chats/<chat_id>/handoff.md` if present.
8. Read the active objective file listed in `state.md` if present.
9. Classify the current request.
10. Continue, simple-edit, pivot, fork, or reset.

Do not read everything by default. Read these only on demand:

- `journal.md`
- `decisions.md`
- `artifacts.md`
- old objectives
- `archive/`

## Request classification

### Simple edit

Small localized change to an existing artifact. No new objective. Minimal state update.

### Continuation

Extends the current active objective. Keep current objective active.

### Pivot with carry-over

New goal, but some previous context remains useful. Pause previous objective and create a new active objective.

### Fork

New side path without abandoning the old one. Create a new objective branch.

### Hard reset

User explicitly asks for clean slate, reset, ignore previous work, or start over. Archive old objective and create a clean active objective.

Default behavior:

- Minor changes = continuation.
- Major goal changes = pivot with carry-over.
- Hard reset only when explicit.
- Never delete old state automatically.

For ambiguous pivots, ask exactly one clarification question:

```text
Do you want this as a pivot that keeps useful context, or a hard reset where I archive the previous objective and start clean?
```

## Pivot, Fork, And Reset Behavior

- Pivot with carry-over: mark the previous objective `paused`, summarize useful carry-over in `state.md`, and create a new active objective.
- Fork: keep the existing objective active or paused as appropriate, then create a clearly named side objective.
- Hard reset: move old objective context to `archive/` or mark it archived/superseded. Create a clean active objective. Do not delete old state automatically.

## Lightweight Edit Behavior

For simple notebook edits:

1. Read minimal state.
2. Locate the notebook.
3. Inspect notebook outline or relevant cells.
4. Edit only requested cells.
5. Run only affected cells if code changed.
6. Do not run the whole notebook unless needed.
7. Append short journal entry if a runtime chat exists.
8. Update state only if status, plan, verification, or next actions changed.

Examples:

- Fix typo.
- Change title.
- Rename plot label.
- Add one markdown explanation.
- Edit one code cell.
- Delete one cell.

## State Update Rules

Avoid bureaucracy.

Append to `journal.md` after meaningful discoveries, edits, errors, or results.

Update `state.md` only when:

- objective changes
- mode changes
- status changes
- plan changes
- risk changes
- next actions change
- verification status changes
- switching phase
- pivoting/forking/resetting
- before final reply for a substantial resumable task

Before continuing to a new phase, switching objective, pivoting, or ending a substantial turn, `state.md` must reflect the latest meaningful state.

Do not append endlessly to `state.md`. Rewrite it as a compact current summary. `state.md` is a router and working summary, not an exhaustive transcript. `journal.md` is append-only history and is not read by default at boot.

## Notebook-Specific Tracking

Notebook state should track:

- notebook path
- stable cell marker, such as a heading, first line, or explicit marker
- cell index if known
- execution status
- whether affected cells were run
- summarized outputs/errors

Do not rely only on cell indexes because indexes drift.

Do not store large raw outputs or sensitive result tables. Summarize them.

## Analysis-Long Behavior

For long MIP/Jupyter/statistical work, use `analysis-long` mode and keep stricter objective state. The active objective must track:

- data model
- dataset IDs
- variable IDs
- filters
- cohort definition
- pipeline
- experiment ID
- polling/waiting status
- notebook path
- affected cells
- execution status
- results summary

This is especially important for MIP runs and notebook execution because live kernel memory is fragile.

## Git Policy

Commit these files if useful:

```text
.llm/README.md
.llm/project.md
.llm/templates/
.llm/chats/.gitkeep
```

Do not commit actual per-chat runtime state unless the project explicitly decides to version agent sessions.

`.gitignore` should include:

```text
.llm/chats/*
!.llm/chats/.gitkeep
```
