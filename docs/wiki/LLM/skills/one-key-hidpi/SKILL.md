---
name: one-key-hidpi
description: Enables HiDPI scaling for Mac external monitors with one-key-hidpi and displayplacer. Use when the user asks to make external display text larger, set up HiDPI on a Dell or other external monitor, or recover from a too-small Mac display scaling mode.
disable-model-invocation: true
---

# one-key-hidpi

Enable HiDPI on a Mac external monitor so text and UI become larger and clearer.

## Use when

- The user says the external monitor text is too small.
- The user asks to set up HiDPI for a Dell or similar external display.
- The user wants a reversible display-scaling setup on macOS.

## Workflow

1. Check the current display state with `system_profiler SPDisplaysDataType`.
2. Confirm the target external monitor and its current `UI Looks like` value.
3. Use `one-key-hidpi` to install or update the HiDPI override for that monitor.
4. Use `displayplacer` to switch the monitor to a larger HiDPI mode.
5. Verify the result with `system_profiler` again.

## Recommended mode

For a 24-inch 2560x1440 Dell panel, prefer:

- `2048x1152` first
- `1920x1080` if text still feels too small

## Example outcome

- Current resolution: `2560 x 1440`
- Target HiDPI look: `2048 x 1152`

## Verification

Check that macOS reports a HiDPI-style look such as:

```text
UI Looks like: 2048 x 1152
```

## Rollback

1. Switch the monitor back to the original native mode.
2. Disable or remove the HiDPI override created by one-key-hidpi.

## Notes

- Keep instructions specific to the target monitor.
- Prefer the smallest change that makes text comfortably readable.
