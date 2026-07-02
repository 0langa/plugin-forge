---
name: import-existing
description: Retrofit an existing plugin repo into a plugin-forge–managed plugin by generating forge.yaml from its current manifests, then installing forge's git hooks. Use when the user says "make this a forge plugin", "retrofit this", "import this plugin into forge", or when working in a repo that clearly is a plugin (has .claude-plugin/, .codex-plugin/, or kimi.plugin.json) but lacks forge.yaml.
---

# Import existing plugin

One-shot retrofit. Turns a hand-crafted plugin repo into a forge-managed one without changing existing behavior.

## Preconditions

1. Current cwd is a plugin repo. Confirm via `forge.status` — `is_plugin_repo=true`.
2. `forge.yaml` does NOT already exist. If it does, use `forge.sync_check` instead.

## Steps

1. **Sniff.** Call `forge.import_repo(write=False)` first. Read the produced spec and sanity-check: does the plugin name match the repo, are all expected surfaces detected, do the MCP entries look sensible?
2. **Report.** Show the user a compact summary of what was detected (providers, surfaces, MCP servers, hooks). Ask ONE clarifying question only if something looks clearly wrong (e.g., wrong plugin name, missing MCP server). Otherwise proceed.
3. **Write.** Call `forge.import_repo(write=True)` to persist `forge.yaml` at the repo root.
4. **Verify parity.** Call `forge.sync_check` to confirm the generated forge.yaml round-trips to the current manifests. If drift is reported, that's a bug in the importer or hand-edited manifests. Report drift; do NOT auto-fix on import (may erase intentional divergence).
5. **Install git hooks.** Run `python -m plugin_forge.git_hooks install <target_repo>` (or `forge install-git-hooks --repo <target_repo>` from the forge CLI). This copies `git_hook_templates/pre-commit` and `pre-push` into the target repo's `.git/hooks/`. If the target already has non-forge hooks, forge chains the new logic rather than replacing them.
6. **Update .gitignore.** Add `.forge_state/` if not already present.
7. **Summary.** One paragraph: what forge.yaml was written, what surfaces it covers, what to do next (usually: `forge.install(mode="link")` to link the plugin into all three providers).

## Do not

- Regenerate manifests during import — that risks erasing hand-tuned fields the sniffer missed.
- Commit anything. Let the user review the diff and commit.
- Bump the version. Import is not a release.
