---
name: mynote-wiki-maintenance
description: Maintains the mynote MkDocs wiki repository. Use when the user asks to install or use MkDocs, initialize the wiki repo, add a note, or publish the wiki site.
disable-model-invocation: true
---

# mynote Wiki Maintenance

Maintain the `mynote` wiki repository end to end.

## Use when

- The user asks how to install or use MkDocs for this wiki.
- The user wants to bootstrap the wiki repository on a new machine.
- The user wants to add or update a note in the wiki.
- The user wants to publish the wiki to GitHub Pages.

## Repo bootstrap

1. Check whether `ROY_NOTE_PWD` is set and points to an existing wiki repository root.
2. If it exists, use that path.
3. If it does not exist, clone:

```bash
git clone git@github.com:bad-superman/mynote.git
```

4. Set `ROY_NOTE_PWD` to the repository root:

```bash
export ROY_NOTE_PWD="/path/to/mynote"
```

5. If the variable should persist for future shells, add the export to the shell profile.

## MkDocs install and use

Install the site toolchain in the active Python environment:

```bash
python3 -m pip install mkdocs mkdocs-material
```

Common commands:

```bash
mkdocs serve
mkdocs build
mkdocs gh-deploy
```

## Add a note

1. Switch to `master` and pull the latest code.
2. Resolve any merge conflicts before editing content.
3. Confirm the working tree is clean before editing.
4. Check whether a related directory and note already exist.
5. If they exist, update them.
6. If they do not exist, create the directory and note.
7. Keep the note focused on dry facts, key steps, and reusable commands.
8. Put images in `docs/images`.

## Publish the wiki

1. Switch to `master` and pull the latest code.
2. Resolve any conflicts before deploying.
3. Run `mkdocs gh-deploy` from the repository root.
4. After deployment, push the latest `master` branch to the remote:

```bash
git push origin master
```

## Guardrails

- Prefer `master` as the content branch for this repo.
- Treat `gh-deploy` as the MkDocs-managed publish branch.
- Do not overwrite unrelated user changes.
- Keep the content note-centric, not marketing-heavy.
- If `master` does not exist, inspect the repo branches and use the repo's default content branch.

## Good defaults

- Use `docs/wiki/<area>/...` for notes.
- Keep note text concise and practical.
- Store reusable screenshots or diagrams under `docs/images`.
- Use this note template for new pages:

```markdown
# Title

## 背景

## 结论

## 核心步骤

## 常见坑

## 验证

## 回退
```
