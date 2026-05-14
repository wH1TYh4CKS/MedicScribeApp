# MedicScribe — Claude Code Project Instructions

Medical transcription + note-generation tool for Malaysian clinics. Android tablet records doctor–patient consultations, streams audio over LAN to a local GPU server (Whisper-large-v3 + Qwen2.5-14B), returns a structured note for doctor review/edit/export. Code-switched Manglish (EN/ZH/MS/TA) is the primary use case.

## ALWAYS read first (every session)

Before doing anything in this project, read the persistent project memory:

- `~/.claude/projects/-home-whity-MedicScribeApp/memory/MEMORY.md` — index of memories
- `~/.claude/projects/-home-whity-MedicScribeApp/memory/project_medicscribe.md` — full project context (goals, constraints, stack, phases, open decisions)

These contain context that is NOT derivable from the repo (the repo is mostly empty / under construction). Treat the memory as the source of truth for *intent*; verify any specific file/function reference against the actual filesystem before acting on it.

## Reference docs in repo

- `PLAN.md` — approved implementation plan (mirrors `~/.claude/plans/witty-chasing-sparkle.md`).
- `docs/ARCHITECTURE.md` (will exist after Phase 0).
- `docs/PRIVACY_PDPA.md` (will exist after Phase 0).
- `docs/PROMPT_TEMPLATES.md` (will exist after Phase 3).

## Hard constraints (never violate without asking)

- Note generation latency budget: ≤ 30 s after Stop.
- All persistence is server-side. Phone is a thin client.
- LAN-only — no cloud egress, no third-party APIs that send audio/text off-site.
- Multilingual code-switched ASR is the core feature, not a nice-to-have.
- Doctor-customisable note templates (Jinja prompt templates server-side).

## Conventions

- **Python**: 3.11+, ruff + black, pydantic v2, type hints required, `pyproject.toml` driven.
- **Kotlin**: AGP 8+, Compose Material 3, kotlinx.serialization for protocol, Hilt optional.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`). Subject ≤ 50 chars.
- **Tests**: `pytest` for server, `./gradlew test` for Android. Don't mock the ASR or LLM in integration tests — use small real model + tiny audio fixture.
- **Secrets / PHI**: never commit audio, transcripts, or notes from real consultations. `data/` is gitignored.

## Workflow rules

- Update the project memory file when project-level facts change (phase advanced, model swapped, deadline added).
- Update `PLAN.md` when scope changes — do not let it drift from `~/.claude/plans/witty-chasing-sparkle.md`.
- Memory format is documented in the global `~/.claude/CLAUDE.md` system prompt.
