import json

from install_cli.codex_plugin_config import (
    MARKETPLACE_NAME,
    PLUGIN_NAME,
    install_codex_plugin,
    uninstall_codex_plugin,
)


def test_install_codex_plugin_writes_real_marketplace_and_config(tmp_path):
    config = tmp_path / "config.toml"
    market = tmp_path / "marketplace"
    config.write_text('[memories]\nuse_memories = true\n', encoding="utf-8")

    install_codex_plugin(
        {
            ".codex-plugin/plugin.json": '{"name":"pathly"}',
            "skills/pathly/SKILL.md": "# pathly",
            "agents/director.md": "# director",
        },
        config_path=config,
        marketplace_root=market,
    )

    assert (market / "plugins" / PLUGIN_NAME / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8") == '{"name":"pathly"}'
    assert (market / "plugins" / PLUGIN_NAME / "skills" / "pathly" / "SKILL.md").read_text(encoding="utf-8") == "# pathly"

    marketplace = json.loads((market / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["name"] == MARKETPLACE_NAME
    assert marketplace["plugins"][0]["name"] == PLUGIN_NAME
    assert marketplace["plugins"][0]["source"]["path"] == "./plugins/pathly"

    content = config.read_text(encoding="utf-8")
    assert f"[marketplaces.{MARKETPLACE_NAME}]" in content
    assert f'[plugins."{PLUGIN_NAME}@{MARKETPLACE_NAME}"]' in content
    assert "enabled = true" in content


def test_install_codex_plugin_is_idempotent(tmp_path):
    config = tmp_path / "config.toml"
    market = tmp_path / "marketplace"

    for content in ("first", "second"):
        install_codex_plugin(
            {"skills/pathly/SKILL.md": content},
            config_path=config,
            marketplace_root=market,
        )

    assert (market / "plugins" / PLUGIN_NAME / "skills" / "pathly" / "SKILL.md").read_text(encoding="utf-8") == "second"
    config_content = config.read_text(encoding="utf-8")
    assert config_content.count(f"[marketplaces.{MARKETPLACE_NAME}]") == 1
    assert config_content.count(f'[plugins."{PLUGIN_NAME}@{MARKETPLACE_NAME}"]') == 1


def test_uninstall_codex_plugin_removes_marketplace_and_config_blocks(tmp_path):
    config = tmp_path / "config.toml"
    market = tmp_path / "marketplace"
    install_codex_plugin({"skills/pathly/SKILL.md": "# pathly"}, config_path=config, marketplace_root=market)

    uninstall_codex_plugin(config_path=config, marketplace_root=market)

    assert not market.exists()
    content = config.read_text(encoding="utf-8")
    assert MARKETPLACE_NAME not in content
    assert f"{PLUGIN_NAME}@{MARKETPLACE_NAME}" not in content
