# Provider Safety Notes

Provider-specific install state is fragile. Prefer documented plugin surfaces:

| Provider | Safe surface |
| --- | --- |
| Claude Code | marketplace or skills-directory plugin discovery |
| Codex | plugin marketplace plus enabled plugin state |
| Kimi Code | managed plugin root and installed.json entry |

