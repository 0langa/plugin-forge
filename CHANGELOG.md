# Changelog

All notable changes to plugin-forge.

## [0.1.0] - 2026-07-03

Initial alpha.

- Canonical `forge.yaml` spec + Pydantic validator
- Manifest adapters: Claude Code, Codex, Kimi Code
- Transactional settings.json patcher with backup + rollback + install receipts
- MCP server (stdio) with tools: `status`, `compile`, `import`, `sync`, `install`, `uninstall`, `bump`, `audit_installed`, `release`, `register_marketplace`, `mcp_dev`, `hook_test`
- Hooks: SessionStart banner, PostToolUse auto-compile
- Skills: `using-forge`, `release-plugin`, `import-existing`
- Slash command: `/forge`
- Git-hook templates for target plugin repos: pre-commit, pre-push
- Import: reverse-engineer existing plugins into `forge.yaml`
- Install/uninstall scripts for forge itself into all three providers
