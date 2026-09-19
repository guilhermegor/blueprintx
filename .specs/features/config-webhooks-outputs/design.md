# Design: `src/config/` — Webhooks & Outputs Config Files

**Date:** 2026-04-15
**Scope:** `templates/ddd-service-native-db/src/` and `templates/ddd-service-orm-db/src/`

---

## Summary

Add a `config/` directory inside `src/` in both DDD service templates, containing two YAML configuration files:

- `webhooks.yaml` — Slack-compatible webhook definitions with per-channel settings and a Python `str.format()` message template.
- `outputs.yaml` — Output path configuration for logs and JSON exports.

---

## Files to Create (identical in both templates)

### `src/config/webhooks.yaml`

```yaml
# Slack-compatible webhook configurations.
# Add as many named entries as needed.
<name_webhook>:
  url:
  id_channel:
  username:
  icon_emoji:
  title: TITLE
  message: >
    ROUTINE: {}
    \n \n \t - Executed at: {}.
    \n \n \t - Operator machine: {}
    \n \n \t - Operator ID: {}
    \n \n \t - Evidence available at: {}
    \n \n \t - Logs available at: {}
    \n \n \t Regards,
  bool_debug_mode: false
```

**Field notes:**
- `{}` placeholders are consumed by Python `str.format()` at runtime.
- `\n` and `\t` are literal escape sequences interpreted at runtime, not by YAML.
- `bool_debug_mode: false` suppresses webhook dispatch during development when set to `true`.
- Multiple webhook entries are supported by adding sibling keys at the same indent level.

### `src/config/outputs.yaml`

```yaml
# Output path configuration for logs and data exports.
path_log:
path_json:
```

**Field notes:**
- `path_log` — destination path for log files produced by the service.
- `path_json` — destination path for exported JSON files.
- Values are left blank as template defaults; filled in per-project at scaffold time.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config location | `src/config/` | Keeps all runtime artefacts under `src/`; no `__init__.py` needed since files are data, not modules |
| Scalar style | `>` folded | Keeps message on one logical YAML line; `\n`/`\t` processed by Python at runtime |
| Exportation file name | `outputs.yaml` | Clear, concise — directly describes stored content (output paths) |
| No `__init__.py` | Omitted | `config/` holds YAML data files, not Python source |

---

## Out of Scope

- Python loader code for these YAML files (separate concern, added per project need).
- Validation schema for webhook entries.
