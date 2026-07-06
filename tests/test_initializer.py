from __future__ import annotations

import pytest

from plugin_forge import initializer, mcp_server
from plugin_forge.spec import ForgeSpec, Provider


def test_initializer_creates_forge_yaml_and_dirs(tmp_path) -> None:
    result = initializer.create(
        tmp_path,
        "new-plugin",
        [Provider.CLAUDE, Provider.CODEX, Provider.KIMI],
        description="New plugin.",
    )

    assert result.forge_yaml.exists()
    loaded = ForgeSpec.load(result.forge_yaml)
    assert loaded.name == "new-plugin"
    assert loaded.providers == [Provider.CLAUDE, Provider.CODEX, Provider.KIMI]
    for dirname in ("skills", "commands", "hooks", "assets", "src"):
        assert (tmp_path / dirname).is_dir()


def test_initializer_refuses_existing_forge_yaml(tmp_path) -> None:
    initializer.create(tmp_path, "new-plugin", [Provider.CODEX])

    with pytest.raises(FileExistsError):
        initializer.create(tmp_path, "new-plugin", [Provider.CODEX])


def test_mcp_init_project_defaults_name_to_repo_dir(tmp_path) -> None:
    result = mcp_server.init_project(path=str(tmp_path), providers="codex")

    assert result["spec"]["name"] == tmp_path.name
    assert result["spec"]["providers"] == ["codex"]
    assert (tmp_path / "forge.yaml").exists()
