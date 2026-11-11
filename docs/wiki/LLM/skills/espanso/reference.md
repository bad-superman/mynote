# Reference

Mac config root:

```text
/Users/roy/Library/Application Support/espanso/
```

| File | Contents |
| --- | --- |
| `config/default.yml` | Shortcuts and injection behavior |
| `match/base.yml` | Triggers and template text |

Official install: <https://espanso.org/docs/install/mac/>

```bash
brew install espanso
```

The app is `/Applications/Espanso.app`. Open it and allow Accessibility. If triggers never fire, also allow Input Monitoring.

```bash
espanso status
espanso restart
espanso stop
espanso env-path register
```

`espanso env-path register` is only needed when the terminal cannot find `espanso`.

Match file:

```yaml
matches:
  - trigger: ":review"
    force_clipboard: true
    replace: |
      模板正文
```

`search_shortcut` defaults to `ALT+SPACE` (Option+Space on Mac). It opens the search bar and pastes the chosen snippet into the focused input.

Built-in check: type `:espanso` and expect `Hi there!`.

Uninstall a Homebrew install with `espanso stop` and `brew uninstall espanso`. The config directory remains until deleted by hand.
