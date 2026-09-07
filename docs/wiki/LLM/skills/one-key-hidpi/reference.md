# Reference

This skill is for a Mac external display that needs larger, readable text through HiDPI.

## Practical defaults

- 24-inch 2K Dell display: start with `2048x1152`
- If still too small: use `1920x1080`
- If the display becomes blurry, return to the HiDPI mode instead of a plain scaled mode

## Common checks

- `system_profiler SPDisplaysDataType`
- `displayplacer list`

## Input to preserve

If the user names a specific monitor model, keep that exact model name in the skill output and instructions.
