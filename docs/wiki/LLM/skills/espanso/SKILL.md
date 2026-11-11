---
name: espanso
description: Installs and uses Espanso on Mac to expand short triggers into saved templates in any input box, including Cursor, Codex, and Claude. Use when the user wants reusable text snippets, text expansion, or to fill a saved template into the current input.
disable-model-invocation: true
---

# espanso

Fill a saved template into the focused input box on macOS. Cursor, Codex, and Claude share the same Espanso matches.

## Use when

- The user wants a prompt or command template reused across Cursor, Codex, and Claude.
- The user asks to install Espanso, add a trigger, or change how expansion works.
- The user points at `config/default.yml` or `match/base.yml`.

## Workflow

1. Read this skill's `reference.md` for paths, commands, and the match format.
2. Keep snippets out of the current code repository.
3. Install or start Espanso only when the user asks to set it up or a trigger does not run.
4. Put behavior in `config/default.yml`. Put triggers and template text in `match/base.yml`.
5. Add `force_clipboard: true` on multiline templates.
6. Restart Espanso only if a saved match does not expand.
7. Verify with the built-in `:espanso` trigger, then with the new trigger.

## Notes

- Do not use `espanso service register` on macOS. That command is for Linux systemd.
- Do not store template text in `config/default.yml`.
- The note lives at `docs/wiki/LLM/espanso/Espanso 安装与使用.md`.
