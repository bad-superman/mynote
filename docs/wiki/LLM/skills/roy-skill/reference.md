# Reference

## Current index

- `mynote-wiki-maintenance`: repo setup, note creation, MkDocs install, publish
- `one-key-hidpi`: Mac external display HiDPI setup
- `issue-analysis`: Hermes Kanban issue investigation with CodeGraph and Nex. SKILL.md lives at `$ROY_NOTE_PWD/docs/wiki/LLM/skills/issue-analysis/SKILL.md` — not a system skill. Load via `read_file()` from that path.
- `roy-skill`: router entry point for the skill library

## Future extension

When a new skill is added, update `$ROY_NOTE_PWD/docs/wiki/LLM/skills/index.md` first, then let `roy-skill` route to it by description.
