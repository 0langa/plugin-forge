---
name: release-plugin
description: One-shot autonomous release of a plugin managed by plugin-forge. Bumps version, regenerates provider manifests, updates marketplace jsons, writes a CHANGELOG stub, commits, tags, and pushes. Use when the user says "release this", "ship v1.2", "cut a release", "publish this plugin", or otherwise asks to release the plugin in the current repo. Do not use for skills — this is plugin-scoped.
---

# Release plugin

Autonomous release chain for a plugin-forge–managed plugin. Runs to completion without asking the user to confirm intermediate steps unless something is blocked or ambiguous.

## Preconditions (check first, in order)

1. Current cwd is a plugin repo (call `forge.status`; `is_plugin_repo=true`, `has_forge_yaml=true`).
2. `git_dirty=false`, or the user explicitly said to commit dirty state.
3. `drift=[]` — if not, call `forge.sync_check(fix=True)` first.

If any precondition fails and the user did not opt in, stop and report exactly what's blocking.

## Steps

1. **Decide level.** If the user named an explicit version ("v1.2.0"), pass `explicit`. Otherwise infer level from their words: "patch/hotfix" → patch, "minor/feature" → minor, "major/breaking" → major. Default to `patch` when unclear.
2. **Bump.** Call `forge.bump_version(level=..., explicit=...)`. Read back the `files_changed` list.
3. **Compile.** Call `forge.compile` to make sure every provider manifest is fresh.
4. **Register marketplace.** Call `forge.register_marketplace`. Include `marketplace_repo` if `forge.status` shows marketplace_notes about missing repo.
5. **Commit.** Stage the changed files (use `git add` for exactly the files returned by `bump_version` + any regenerated manifests). Commit message:
   ```
   release: v<new>

   - <one-line summary of what changed>
   ```
   No `--amend`. No `--no-verify` (git hooks are forge's own guards).
6. **Tag.** `git tag v<new>`.
7. **Push.** `git push && git push --tags`.
8. **GitHub release.** `gh release create v<new> --generate-notes` if `gh` is available; otherwise skip and note it.
9. **Marketplace push.** If the marketplace repo is a separate git repo (typical), commit + push those jsons too.

## After release

Emit a short summary: version bumped, files changed, tag pushed, release URL if any. Nothing else.

## Failure modes

- Bump fails → surface stderr, do nothing else.
- Compile drift after bump → re-run `sync_check(fix=True)`; if still drifting, stop.
- Push rejected (behind remote) → stop, tell user to pull, do not force.
- gh missing → skip step 8, tell user to publish notes manually.
