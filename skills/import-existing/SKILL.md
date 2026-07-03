---
name: import-existing
description: Use this skill when importing an existing plugin, when retrofitting Claude/Codex/Kimi manifests, when converting a hand-managed repo, when onboarding to Forge, or when forge.yaml is missing. Use proactively for retrofit requests; automatically trigger on import/convert/onboard requests.
---

# Import Existing Plugin

## Purpose

Convert a hand-managed plugin repo into a plugin-forge managed repo without
changing behavior. The first import should preserve existing manifests, detect
surfaces, create `forge.yaml`, install Forge git hooks, and report anything the
importer could not model.

## Preconditions

Confirm the current repo is a plugin repo:

```text
.claude-plugin/plugin.json
.codex-plugin/plugin.json
kimi.plugin.json
skills/
hooks/
.mcp.json
```

If `forge.yaml` already exists, do not import again. Use `using-forge` and
`forge.sync_check` instead.

## Import Steps

1. Run `forge.status`.
2. Run `forge.import_repo(write=false)`.
3. Inspect the generated spec for plugin name, provider list, skills, hooks,
   MCP servers, command files, install targets, and provider extras.
4. Ask one short clarification only if the detected plugin name or surface set
   is clearly wrong.
5. Run `forge.import_repo(write=true)`.
6. Run `forge.sync_check` without auto-fix.
7. Install Forge git hooks:

```powershell
python -m plugin_forge.git_hooks install <target-repo>
```

8. Add `.forge_state/` to `.gitignore` if missing.
9. Run the repo's existing tests.

## Output Format

Return a compact import report:

```text
Imported <plugin-name> into forge.yaml.
Providers: Claude, Codex, Kimi.
Surfaces: <skills, hooks, MCP, commands>.
Drift: <none or list>.
Next: forge install --provider all --mode link.
```

If blocked:

```text
Blocked: <specific missing or ambiguous input>. No manifests regenerated.
```

## Preservation Rules

Do not regenerate manifests during first import unless the user explicitly asks.
Do not erase provider-specific fields; keep unknown fields in provider extras.
Do not bump version during import.
Do not commit the import automatically.
Do not rewrite installer scripts until Forge install has been tested against them.

## Validation

After writing `forge.yaml`, verify that a fresh render would not remove important
provider-specific behavior:

```text
forge.sync_check
pytest
```

For plugins with hooks, run one synthetic hook test. For plugins with MCP, run
the MCP server directly or use `forge.mcp_dev`.

## Examples

User: "make this hand-built plugin a forge plugin"

Action:

```text
forge.status
forge.import_repo(write=false)
forge.import_repo(write=true)
forge.sync_check
python -m plugin_forge.git_hooks install .
pytest
```

User: "import usage-pulse into forge"

Action: detect Claude/Codex/Kimi manifests, preserve Kimi `mcpServers` and
`hooks`, create `forge.yaml`, then compare generated output in a scratch dir
before allowing Forge to own live manifests.

## Detection Matrix

| File or directory | Meaning |
| --- | --- |
| `.claude-plugin/plugin.json` | Claude plugin manifest |
| `.codex-plugin/plugin.json` | Codex plugin manifest |
| `kimi.plugin.json` | Kimi plugin manifest |
| `.mcp.json` | bundled MCP server config |
| `hooks` directory | bundled hook scripts or configs |
| `skills` directory | plugin skills |
| `commands` directory | slash or command files |
| `agents` directory | subagent definitions |

## Scratch Render Check

When the plugin is risky, render to a scratch directory first:

```powershell
forge import-repo --write
forge compile --out <scratch>
```

Compare scratch output against current manifests. Preserve fields that matter.

## Import Report Fields

Include these fields in the final report:

```text
plugin name
provider manifests found
skills detected
hooks detected
MCP servers detected
provider extras preserved
drift result
next install command
```

## Manual Repair Cases

If a provider manifest contains a field Forge does not model, place it under
provider extras.

If hooks differ by provider, keep provider-specific hook sidecars rather than
sharing one file blindly.

If a local installer mutates global config, keep it until Forge install has an
equivalent safe path and tests prove rollback.

If Kimi install state is involved, check the managed plugin root and
`installed.json` shape before launch.

## Troubleshooting

If the importer misses a surface, add it to `forge.yaml` manually and run
`forge.sync_check` again.

If generated output differs from a hand-tuned manifest, preserve the hand-tuned
fields through `provider_extras`.

If provider docs conflict with current manifests, check the official provider
docs and report the concrete mismatch before changing behavior.

## Related

- `using-forge`: normal work after import.
- `release-plugin`: release flow after import and validation.
