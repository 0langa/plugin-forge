"""Command-line entry point (`forge ...`).

Thin wrapper over the MCP tool functions so anything an agent can do via MCP
you can also do from a terminal. Not the primary UX — the primary UX is hooks
and MCP tool calls made by the agent. Use the CLI for scripting, cron, or
manual escape hatch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from plugin_forge import audit, bump, git_hooks, importer, initializer, installer, sync
from plugin_forge.adapters import render_all
from plugin_forge.installer import Mode
from plugin_forge.spec import ForgeSpec, Provider


def _load(path: str | None) -> tuple[ForgeSpec, Path]:
    repo = Path(path).resolve() if path else Path.cwd().resolve()
    forge_yaml = repo / "forge.yaml"
    if not forge_yaml.exists():
        raise click.ClickException(f"no forge.yaml at {forge_yaml}")
    return ForgeSpec.load(forge_yaml), repo


@click.group()
def cli() -> None:
    """plugin-forge — multi-provider plugin lifecycle."""


@cli.command("init")
@click.option("--path", default=None, help="Plugin repo path (defaults to cwd).")
@click.option("--name", required=True, help="Stable plugin id, usually kebab-case.")
@click.option("--providers", default="all", help="Comma list: all, claude,codex,kimi.")
@click.option("--description", default=None, help="Short plugin description.")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing forge.yaml.")
def init_cmd(
    path: str | None, name: str, providers: str, description: str | None, force: bool
) -> None:
    """Create forge.yaml and standard plugin source directories."""
    repo = Path(path).resolve() if path else Path.cwd().resolve()
    try:
        provider_list = initializer.parse_providers(providers)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        result = initializer.create(
            repo,
            name,
            provider_list,
            description=description,
            force=force,
        )
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"wrote {result.forge_yaml}")
    for directory in result.created_dirs:
        click.echo(f"dir {directory}")


@cli.command()
@click.option("--path", default=None, help="Plugin repo path (defaults to cwd).")
def status(path: str | None) -> None:
    """Print combined plugin-repo status as JSON."""
    from plugin_forge import status as st

    repo = Path(path).resolve() if path else Path.cwd().resolve()
    click.echo(json.dumps(st.probe(repo).to_dict(), indent=2, default=str))


@cli.command()
@click.option("--path", default=None)
def compile(path: str | None) -> None:
    """Regenerate provider manifests from forge.yaml before sync/install."""
    spec, repo = _load(path)
    written = render_all(spec, repo)
    for prov, p in written.items():
        click.echo(f"{prov.value}: {p}")


@cli.command("sync")
@click.option("--path", default=None)
@click.option("--fix", is_flag=True, default=False)
def sync_cmd(path: str | None, fix: bool) -> None:
    """Check (or fix) drift between forge.yaml and provider manifests."""
    spec, repo = _load(path)
    report = sync.fix(spec, repo) if fix else sync.check(spec, repo)
    click.echo(
        json.dumps(
            {
                "clean": report.is_clean,
                "drift": [
                    {"provider": d.provider.value, "kind": d.kind, "message": d.message}
                    for d in report.drift
                ],
                "fixed": report.fixed,
            },
            indent=2,
        )
    )
    if not report.is_clean and not fix:
        sys.exit(1)


@cli.command("import")
@click.option("--path", default=None)
@click.option("--write/--no-write", default=True)
def import_(path: str | None, write: bool) -> None:
    """Retrofit an existing plugin repo into a forge.yaml."""
    repo = Path(path).resolve() if path else Path.cwd().resolve()
    spec = importer.sniff(repo)
    if write:
        spec.dump(repo / "forge.yaml")
        click.echo(f"wrote {repo / 'forge.yaml'}")
    else:
        click.echo(json.dumps(spec.model_dump(mode="json", exclude_none=True), indent=2))


@cli.command()
@click.option("--path", default=None)
@click.option("--provider", default="all", type=click.Choice(["all", "claude", "codex", "kimi"]))
@click.option("--mode", default="link", type=click.Choice(["link", "copy"]))
@click.option("--dry-run", is_flag=True, default=False)
def install(path: str | None, provider: str, mode: str, dry_run: bool) -> None:
    """Install compiled provider manifests; run compile and sync first."""
    spec, repo = _load(path)
    providers = list(spec.providers) if provider == "all" else [Provider(provider)]
    for prov in providers:
        r = installer.install(spec, repo, prov, mode=Mode(mode), dry_run=dry_run)
        click.echo(
            f"{r.provider.value} -> {r.target} "
            f"({r.mode.value}, settings_patched={r.settings_patched})"
        )


@cli.command()
@click.option("--path", default=None)
@click.option("--provider", default="all", type=click.Choice(["all", "claude", "codex", "kimi"]))
def uninstall(path: str | None, provider: str) -> None:
    """Uninstall from provider directories."""
    spec, repo = _load(path)
    providers = list(spec.providers) if provider == "all" else [Provider(provider)]
    for prov in providers:
        ok = installer.uninstall(spec, prov)
        click.echo(f"{prov.value}: {'removed' if ok else 'nothing to remove'}")


@cli.command("bump")
@click.option("--path", default=None)
@click.option("--level", default="patch", type=click.Choice(["major", "minor", "patch"]))
@click.option("--explicit", default=None)
def bump_cmd(path: str | None, level: str, explicit: str | None) -> None:
    """Bump the plugin version across every file."""
    _, repo = _load(path)
    result = bump.apply_bump(repo / "forge.yaml", level=level, explicit=explicit)
    click.echo(f"{result.old} -> {result.new}")
    for f in result.files_changed:
        click.echo(f"  {f}")


@cli.command("audit")
def audit_cmd() -> None:
    """Cross-provider inventory of installed plugins."""
    r = audit.run()
    click.echo(
        json.dumps(
            {
                "installed": [
                    {
                        "provider": p.provider.value,
                        "name": p.name,
                        "version": p.version,
                        "path": str(p.path),
                        "is_link": p.is_link,
                        "mcp_registered": p.mcp_registered,
                        "hooks_registered": p.hooks_registered,
                    }
                    for p in r.installed
                ],
                "orphans": [str(o) for o in r.orphans],
                "missing_across": {
                    n: sorted(p.value for p in v) for n, v in r.missing_across.items()
                },
            },
            indent=2,
        )
    )


@cli.command("install-git-hooks")
@click.option("--repo", default=None)
def install_git_hooks(repo: str | None) -> None:
    """Install forge's pre-commit / pre-push into a target plugin repo."""
    target = Path(repo).resolve() if repo else Path.cwd().resolve()
    for p in git_hooks.install_hooks(target):
        click.echo(f"installed {p}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
