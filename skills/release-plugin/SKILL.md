---
name: release-plugin
description: Use this skill when releasing a Forge-managed plugin, when bumping version, when tagging a release, when publishing marketplace metadata, or when the user asks to ship a Claude/Codex/Kimi plugin. Use proactively for release requests; automatically trigger on ship/publish/tag requests.
---

# Release Plugin

## Purpose

Release a plugin-forge managed plugin without hand-editing provider manifests.
The expected result is a version bump, regenerated Claude/Codex/Kimi manifests,
updated marketplace entries, a commit, a tag, and pushed release state.

## Preconditions

Check these before mutation:

```text
forge.status -> is_plugin_repo=true, has_forge_yaml=true
git status   -> clean unless user explicitly wants dirty state included
forge.sync_check -> no drift, or drift repaired before release
```

If the repo is not Forge-managed, switch to `import-existing`.
If the user is releasing only a single skill, use the skill-center workflow instead.

## Version Decision

Use the user's explicit version when present:

```text
"release v1.2.0" -> explicit 1.2.0
```

Infer semantic level when no explicit version exists:

```text
hotfix, patch, typo, safety fix -> patch
feature, new provider support   -> minor
breaking, schema change         -> major
unclear release request         -> patch
```

## Release Steps

1. Run `forge.status`.
2. Run `forge.sync_check(fix=true)` if drift exists.
3. Run `forge.bump_version(level=...)` or explicit version equivalent.
4. Run `forge.compile`.
5. Run the repository test suite.
6. Run a focused hook/MCP smoke test when the plugin has hooks or MCP servers.
7. Run `forge.register_marketplace`.
8. Stage only release-related files.
9. Commit with:

```text
release: v<version>

- <short release summary>
```

10. Tag with `v<version>`.
11. Push branch and tag.
12. Create a GitHub release with generated notes when `gh` is available.

## Output Format

Return a compact release report:

```text
Released v<version>.
Changed: <files or surfaces>.
Verified: <tests/eval/smoke checks>.
Pushed: <branch>, tag v<version>.
Release: <url or skipped reason>.
```

If blocked:

```text
Blocked before release: <specific reason>. No tag or push created.
```

## Safety

Do not use `--no-verify` unless the user explicitly instructs it.
Do not force-push release tags unless the user explicitly asks to move an existing tag.
Do not publish marketplace changes when tests fail.
Do not invent provider manifest fields; check official docs when provider shape matters.
Do not directly edit Claude internal install cache, Kimi global hooks, or Codex global MCP blocks.

## Examples

User: "cut a patch release"

Action:

```text
forge.status
forge.sync_check(fix=true)
forge.bump_version(level="patch")
forge.compile
pytest
forge.register_marketplace
git add <release files>
git commit -m "release: v<version>"
git tag v<version>
git push && git push --tags
```

User: "publish this plugin once Kimi eval is over 90"

Action: run PluginEval, improve skills if needed, verify score, then run release steps.

## Decision Table

| User phrase | Release level | Extra gate |
| --- | --- | --- |
| "hotfix this plugin" | patch | focused regression test |
| "ship the safety fix" | patch | provider config smoke |
| "release the new MCP tool" | minor | MCP server smoke |
| "publish Kimi support" | minor | Kimi doctor and plugin reload |
| "breaking schema change" | major | migration note |
| "release v1.4.0" | explicit | exact version check |
| "publish after eval over 90" | inferred | PluginEval gate |

## Verification Matrix

| Surface changed | Required check |
| --- | --- |
| `forge.yaml` | compile and sync-check |
| Skill docs | PluginEval quick or standard |
| Hook code | synthetic hook test |
| MCP server | direct MCP server startup |
| Provider install state | install in link mode |
| Marketplace metadata | marketplace validation |

## Commit Scope

Stage only release-related files. Typical files:

```text
forge.yaml
pyproject.toml
.claude-plugin/plugin.json
.codex-plugin/plugin.json
kimi.plugin.json
CHANGELOG.md
marketplace json files
```

Do not stage unrelated working tree changes.

## Rollback Plan

If release fails before commit, keep changes in the working tree and fix them.

If release fails after commit but before tag, create a new fix commit.

If release fails after local tag but before push, delete the local tag and retry:

```powershell
git tag -d v<version>
```

If release fails after push, do not rewrite history without direct user approval.

## Quality Gate

Before publishing a marketplace-ready plugin, prefer this evidence:

```text
pytest passed
PluginEval score over configured threshold
provider install smoke passed
MCP server starts
hooks fail open
```

## Edge Cases

Handle these cases explicitly:

| Case | Action |
| --- | --- |
| Dirty tree with unrelated files | stop and list unrelated files |
| Dirty tree with release files only | continue if user asked to include them |
| Existing local tag | stop unless user asked to replace it |
| Existing remote tag | stop; no force push without direct approval |
| Marketplace repo dirty | stop and report marketplace repo path |
| PluginEval below threshold | improve skill docs or report blocked |
| Kimi plugin load error | fix install state before release |
| Claude marketplace validation error | fix marketplace json before release |
| Codex plugin validation error | fix `.codex-plugin/plugin.json` before release |

## Provider Release Checks

Claude release readiness:

```text
.claude-plugin/plugin.json exists
hooks/hooks.json valid when hooks are bundled
.mcp.json valid when MCP is bundled
marketplace entry points at correct plugin source
```

Codex release readiness:

```text
.codex-plugin/plugin.json exists
hook path stays inside plugin root
MCP config stays inside plugin root
plugin enabled state is not a global MCP duplicate
```

Kimi release readiness:

```text
kimi.plugin.json exists
mcpServers use ./ paths or PATH commands
hooks use plugin-root-relative commands
installed.json entry uses id/root/source/enabled shape
```

## Final Sanity Pass

Before final response, check:

```text
git status --short
git log -1 --oneline
git tag --list v<version>
```

If anything is still dirty after release, report it as follow-up work rather
than hiding it.

## Troubleshooting

If `forge.sync_check` still reports drift after fixing, stop and inspect the adapter.

If tests fail after version bump, keep the bump in the working tree and fix the test failure
before committing.

If push is rejected because the branch is behind remote, stop; do not rebase or force without
user direction.

If GitHub release creation fails because `gh` is unavailable or unauthenticated, finish the
git release and report the skipped GitHub release.

## Related

- `using-forge`: normal work inside a Forge-managed plugin repo.
- `import-existing`: retrofit before release when `forge.yaml` is missing.
