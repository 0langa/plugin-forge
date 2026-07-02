# plugin-forge handoff · 2026-07-03T21:30Z

**Status:** in_progress · **From:** claude-code · **To:** any (successor picks up in ~2h when Julius's Claude usage refreshes)

Repo: `C:\Users\Julius\source\repos\0langas-plugin-forge` → [github.com/0langa/plugin-forge](https://github.com/0langa/plugin-forge) (private, main @ `0e7aed7`), working tree clean.

## What is plugin-forge

MCP + hooks that automate multi-provider (Claude Code / Codex / Kimi Code) plugin lifecycle from one canonical `forge.yaml` per plugin. Version bumps, manifest generation, cross-provider installs, marketplace registration, parity enforcement. Zero-touch during normal work; slash command is escape hatch, not primary UX.

Design principles (do not violate):

- **Automation-first.** Hooks + MCP tools do work. Skills only where single-call solves it.
- **Single source of truth.** `forge.yaml` per plugin. Adapters emit provider manifests deterministically.
- **Transactional installs.** Every settings.json / registry patch backed up, receipt-based reversal.
- **Fail-open hooks.** Errors go to `~/.plugin-forge/errors.log`; host session must never break.
- **Round-trip fidelity.** `import → compile` must preserve every field. Unknown manifest keys → `provider_extras`.
- **Clean boundary with skill-center.** Skill-body porting is `0langas-skill-center/tri-client-skill-port`. Forge = plugin topology, install, MCP, hooks, versioning, marketplace.

## State snapshot

- 84/84 tests passing, 72% coverage.
- Round-trip verified against real `usage-pulse` repo (built by Codex in parallel).
- README carries real usage-pulse example.
- All architecture in place: spec, adapters, patcher, installer, importer, bump, sync, audit, MCP server, hooks, skills, git-hook installer, CLI, registrars.

## What Julius wants next

He said "keep pushing until fully done or my usage runs out." Usage is running out. Next 2h you own the continuation.

## Top priorities (in order)

1. **Rewrite `ClaudeRegistrar` to use `marketplace.json` (highest)**. Current `src/plugin_forge/registrars.py` writes `~/.claude/plugins/installed_plugins.json` — that's Claude's internal cache. Per official docs (`https://code.claude.com/docs/en/plugin-marketplaces`, cached at `C:\Users\Julius\.claude\projects\C--Users-Julius-source-repos-0langas-plugin-marketplace\a59e6f9d-99ba-4c3d-8508-2c445b0fd4a7\tool-results\toolu_01E3eJ7PmAzCXUGQaVHxTBy1.txt`) the documented flow is: emit a marketplace.json (schema: `{name, owner: {name, email?}, plugins: [{name, source, description, version, ...}]}`), user runs `/plugin marketplace add <path>` once, then `/plugin install <name>@<marketplace>`. Forge should either write a `~/.forge-local/.claude-plugin/marketplace.json` OR add the plugin's entry to the existing user marketplace, then optionally invoke `claude plugin install <name>@forge-local` as subprocess.

2. **Verify Codex + Kimi registrar shapes** (`src/plugin_forge/registrars.py`). Codex should point `source` at the marketplace root (dir containing multiple plugins) not `install_dir.parent`. Kimi docs say `Local installations are copied to $KIMI_CODE_HOME/plugins/managed/<id>/` — check if writing an entry pointing at a repo path outside `managed/` works or if forge needs to copy files there.

3. **Fix Claude hooks.json nesting** in `src/plugin_forge/adapters/_common.py`. Currently emits flat `{event, command, matcher, timeout}`. Real shape (per plugins-reference doc):

   ```json
   {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "..."}]}]}}
   ```

   Kimi inline `hooks` array shape is closer to what forge emits, verify against `usage-pulse` kimi.plugin.json.

4. **Live install one plugin end-to-end**. `usage-pulse` is the target. After (1)–(3), run `forge install --mode link --provider all --path C:/Users/Julius/source/repos/usage-pulse`. Then start a session in each of Claude Code, Codex, Kimi and confirm hooks fire + MCP is registered + `/pulse` works. Test uninstall — settings.json / registry must revert byte-clean.

5. **release-plugin skill dry-run**. Task #25. Exercise on a throwaway plugin.

6. **Register forge itself in `0langas-plugin-marketplace`**. Task #26. Test file `tests/test_marketplace_registration.py::test_real_marketplace_shape_recognized` already dry-runs against the real marketplace — flip off dry-run and register plugin-forge for real.

7. **CI file cannot be pushed by current PAT.** `docs/ci.yml.pending-workflow-scope` is a valid GH Actions workflow (matrix ubuntu+windows py3.11–3.13, ruff + pytest + coverage). PAT lacks `workflow` scope. Fix by upgrading PAT or uploading via github.com UI once.

## Blockers

- **PAT missing `workflow` scope.** Cannot push `.github/workflows/*`. Workaround shipped: file lives at `docs/ci.yml.pending-workflow-scope`.

## How to verify state before touching anything

```
cd C:\Users\Julius\source\repos\0langas-plugin-forge
.\.venv\Scripts\python.exe -m pytest
```

Expected: 84 passed. If fewer, something drifted between commits.

## Julius's collaboration style (from memory)

- Runs three parallel 20€ subs (Claude/Codex/Kimi). Delegates parallel workstreams. `usage-pulse` was Codex's parallel target here.
- Prefers automation-first plugins over slash-command menus (verbatim: "9 slash commands in a row triggered some kind of PTSDesque flashback to like 2022 before MCP was even a thing").
- Rejects PAYG cost estimation (dislikes it, forge marketplace registrar must never suggest it).
- Rejects MVP-thinking for personal projects ("go big or go home").
- **Caveman mode is active in his session (terse prose, drop articles/filler). Code and commits stay normal English.**
- For any provider-specific claim, use `anthropic-skills:official-ai-devdocs` skill first. Docs used this session are cached in `C:\Users\Julius\.claude\projects\C--Users-Julius-source-repos-0langas-plugin-marketplace\a59e6f9d-99ba-4c3d-8508-2c445b0fd4a7\tool-results\`.
- Don't touch RECALL. Forge retrofit of RECALL is off the table unless he explicitly asks.

## Safety

- No secrets read. No `.env`, no credentials, no tokens.
- Backup files under `~/.plugin-forge/receipts/` and `<target>.forge-backup.<ts>` — never commit those.
- Kimi and Codex registrars mutate real config files with a `.forge-backup.<ts>` snapshot. Restore via `patcher.restore_from_backup` or manually copy `.forge-backup.<ts>` back.

## Files that matter most

- `forge.yaml` — spec for forge itself
- `src/plugin_forge/spec.py` — canonical Pydantic schema
- `src/plugin_forge/adapters/{claude,codex,kimi}.py` — manifest emitters
- `src/plugin_forge/registrars.py` — **needs Claude refactor per (1)**
- `src/plugin_forge/importer.py` — retrofit sniffer
- `src/plugin_forge/patcher.py` — transactional settings.json engine
- `src/plugin_forge/mcp_server.py` — the 11 tools model calls
- `src/plugin_forge/hooks/{session_start,post_tool_use,user_prompt_submit}.py` — fail-open host hooks
- `skills/{using-forge,release-plugin,import-existing}/SKILL.md`
- `tests/test_roundtrip_usage_pulse.py` — real-world validation

## Successor start command

```
cd C:\Users\Julius\source\repos\0langas-plugin-forge
git status                 # should be clean, on main @ 0e7aed7 or later
cat .handoff/active.md     # this file
.\.venv\Scripts\python.exe -m pytest  # 84 expected
```

Then start on next-step #1.
