---
name: roy-skill
description: Routes requests to the most appropriate skill in Roy's skill index and executes that skill's workflow. Use when the user asks for roy_skill, wants the right skill chosen from the index, or needs a single entry point for Roy's reusable workflows.
disable-model-invocation: true
---

# roy-skill

Use this as the entry point for Roy's skill library.

## Workflow

1. Open this skill's `reference.md`.
2. Pick the most specific matching skill.
3. Read that skill's `SKILL.md` first.
4. Read its `reference.md` or scripts only if needed.
5. Execute the selected skill's workflow.
6. If no skill matches, ask for the smallest missing detail.

## Selection rules

- Prefer the most specific skill over a generic one.
- If two skills fit, choose the one whose description matches the user's wording best.
- If the request is a repo-maintenance task, prefer `mynote-wiki-maintenance`.
- If the request is about Mac external display HiDPI, prefer `one-key-hidpi`.

## Notes

- This skill is a router, not a separate workflow.
- Keep the index current whenever a new skill is added at `$ROY_NOTE_PWD/docs/wiki/LLM/skills/index.md`.
