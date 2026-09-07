# Reference

## Suggested note workflow

1. Find the closest existing wiki category.
2. Reuse an existing note if the topic already exists.
3. Otherwise create a new note under the right folder.
4. Add only the useful parts:
   - what to do
   - what to run
   - what to avoid
   - how to verify
5. Keep screenshots in `docs/images` and reference them with relative Markdown links.

## Suggested deployment checks

- `git status --short`
- `mkdocs build`
- `mkdocs gh-deploy`

## Repo-specific note

This repository currently uses `site_name: Roy's Docs` with the Material theme and a minimal `mkdocs.yml`, so the skill should preserve that lightweight structure.
