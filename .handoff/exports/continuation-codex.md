# Continuation prompt — plugin-forge (paste into a new Claude Code session)

You are continuing work on `plugin-forge` — a multi-provider (Claude Code / Codex / Kimi Code) plugin lifecycle automation tool. The prior Claude Code session hit its usage limit at v0.1.0 with 84/84 tests passing and pushed everything to [github.com/0langa/plugin-forge](https://github.com/0langa/plugin-forge) (`main @ 0e7aed7`).

Full handoff record: `C:\Users\Julius\source\repos\0langas-plugin-forge\.handoff\active.md` and `.handoff\active.json`. Read `active.md` first — it has priorities, context, and Julius's collaboration style.

Repository: `C:\Users\Julius\source\repos\0langas-plugin-forge`. Working tree is clean. Virtual env at `.venv/`. Tests: `.\.venv\Scripts\python.exe -m pytest` (expect 84 passing).

## Immediate next task (highest priority)

Rewrite `ClaudeRegistrar` in `src/plugin_forge/registrars.py` to use the **documented** marketplace.json install path. Current code writes `~/.claude/plugins/installed_plugins.json` (internal cache, undocumented). Per official docs (`https://code.claude.com/docs/en/plugin-marketplaces`, already cached in the tool-results dir listed in `active.md`), the documented flow is:

1. Emit a `.claude-plugin/marketplace.json` describing a "forge-local" marketplace, listing every forge-managed plugin: `{name, owner: {name}, plugins: [{name, source: <install_dir>, description, version}]}`.
2. Add the marketplace to Claude (either subprocess `claude plugin marketplace add <path>` or note that the user runs it once).
3. Install via subprocess `claude plugin install <name>@forge-local` (or leave that to the user).

Delete the current installed_plugins.json direct-write path. Update `tests/test_registrars.py` accordingly.

## Remaining priorities (in order)

Read `.handoff/active.md` for the full list of 9 next-steps. Highlights:

- Verify Codex + Kimi registrar shapes against real config files on this machine.
- Fix Claude hooks.json nesting (currently flat, real shape has matcher grouping).
- Live install one plugin end-to-end (usage-pulse is the intended target).
- release-plugin skill dry-run.
- Register plugin-forge itself in `0langas-plugin-marketplace`.

## Collaboration notes

- Julius runs a "caveman mode" system prompt — terse, drop articles/filler. Applies to prose only, not code or commits.
- He prefers automation over slash-command menus and rejects PAYG cost estimation and MVP-thinking for personal projects.
- Before any provider-specific claim, invoke `anthropic-skills:official-ai-devdocs`. Docs cached at `C:\Users\Julius\.claude\projects\C--Users-Julius-source-repos-0langas-plugin-marketplace\a59e6f9d-99ba-4c3d-8508-2c445b0fd4a7\tool-results\`.
- Don't touch RECALL unless he explicitly asks.

## Verify before proceeding

```
cd C:\Users\Julius\source\repos\0langas-plugin-forge
git log -1 --oneline           # should show 0e7aed7 or later
.\.venv\Scripts\python.exe -m pytest    # 84 expected
```

If either fails, stop and report — something drifted.

Start with next-step #1 (ClaudeRegistrar rewrite). Silent success is fine; report only what changed and whether tests still pass.
