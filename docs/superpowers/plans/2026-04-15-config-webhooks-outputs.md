# Config Webhooks & Outputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `src/config/webhooks.yaml` and `src/config/outputs.yaml` to both DDD service templates (`ddd-service-native-db` and `ddd-service-orm-db`).

**Architecture:** Pure YAML data files — no Python code, no loaders, no tests. Both template directories receive identical file content. Files sit at `src/config/` so they travel with the source tree when scaffolded into a new project.

**Tech Stack:** YAML only.

---

## File Map

| Action | Path |
|--------|------|
| Create | `templates/ddd-service-native-db/src/config/webhooks.yaml` |
| Create | `templates/ddd-service-native-db/src/config/outputs.yaml` |
| Create | `templates/ddd-service-orm-db/src/config/webhooks.yaml` |
| Create | `templates/ddd-service-orm-db/src/config/outputs.yaml` |

---

### Task 1: Add config files to `ddd-service-native-db`

**Files:**
- Create: `templates/ddd-service-native-db/src/config/webhooks.yaml`
- Create: `templates/ddd-service-native-db/src/config/outputs.yaml`

> No tests apply — these are YAML data files with no executable logic.

- [ ] **Step 1: Create `webhooks.yaml`**

Create `templates/ddd-service-native-db/src/config/webhooks.yaml` with this exact content:

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

- [ ] **Step 2: Create `outputs.yaml`**

Create `templates/ddd-service-native-db/src/config/outputs.yaml` with this exact content:

```yaml
# Output path configuration for logs and data exports.
path_log:
path_json:
```

- [ ] **Step 3: Verify files exist**

```bash
ls templates/ddd-service-native-db/src/config/
```

Expected output:
```
outputs.yaml  webhooks.yaml
```

- [ ] **Step 4: Commit**

```bash
git add templates/ddd-service-native-db/src/config/
git commit -m "feat(scaffold): add config/webhooks.yaml and config/outputs.yaml to ddd-service-native-db"
```

---

### Task 2: Add config files to `ddd-service-orm-db`

**Files:**
- Create: `templates/ddd-service-orm-db/src/config/webhooks.yaml`
- Create: `templates/ddd-service-orm-db/src/config/outputs.yaml`

> No tests apply — these are YAML data files with no executable logic.

- [ ] **Step 1: Create `webhooks.yaml`**

Create `templates/ddd-service-orm-db/src/config/webhooks.yaml` with this exact content:

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

- [ ] **Step 2: Create `outputs.yaml`**

Create `templates/ddd-service-orm-db/src/config/outputs.yaml` with this exact content:

```yaml
# Output path configuration for logs and data exports.
path_log:
path_json:
```

- [ ] **Step 3: Verify files exist**

```bash
ls templates/ddd-service-orm-db/src/config/
```

Expected output:
```
outputs.yaml  webhooks.yaml
```

- [ ] **Step 4: Commit**

```bash
git add templates/ddd-service-orm-db/src/config/
git commit -m "feat(scaffold): add config/webhooks.yaml and config/outputs.yaml to ddd-service-orm-db"
```
