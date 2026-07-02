---
name: forge
description: Show plugin-forge status for the current plugin repo (declared providers, installed providers + versions, manifest drift, marketplace sync, git state). Escape hatch — the SessionStart hook already surfaces this automatically.
---

Call `forge.status` on the current working directory. Format the result as a compact multi-line report:

```
<name> v<version>
providers: <declared>
installed: <installed>  (versions: {provider: version, ...})
drift:     <count>       # list each drift item on its own indented line
marketplace: <ok|stale|unknown>   # list marketplace_notes on indented lines
git: <branch> (<clean|dirty>)
```

If `is_plugin_repo=false`, print `not a plugin repo` and stop.

If drift > 0, suggest calling `forge.sync_check(fix=True)` at the end. If marketplace is stale, suggest calling `forge.register_marketplace`. If `has_forge_yaml=false` but manifests exist, suggest running the `import-existing` skill.

Do not run any mutating operation from this command — status only.
