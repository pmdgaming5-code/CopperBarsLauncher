import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launcher


def test_rule_allows_simple():
    assert launcher.rule_allows(None)
    assert launcher.rule_allows([{"action": "allow"}])


def test_offline_uuid_is_stable():
    a = launcher.make_offline_account("CopperBars")
    b = launcher.make_offline_account("CopperBars")
    assert a.uuid == b.uuid
    assert a.type == "offline"


def test_maven_path():
    path = launcher.maven_path("org.lwjgl:lwjgl:3.3.3")
    assert str(path).endswith("org/lwjgl/lwjgl/3.3.3/lwjgl-3.3.3.jar")


def test_argument_replacements():
    args = launcher.apply_argument_rules(
        ["--username", "${auth_player_name}", {"rules": [{"action": "allow"}], "value": "${version_name}"}],
        replacements={"${auth_player_name}": "CopperBars", "${version_name}": "1.21.11"},
    )
    assert args == ["--username", "CopperBars", "1.21.11"]


def test_json_roundtrip(tmp_path):
    path = tmp_path / "x.json"
    launcher.save_json(path, {"hello": "world"})
    assert launcher.load_json(path, {}) == {"hello": "world"}


def test_build_command_contains_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "find_java", lambda _: "java")
    monkeypatch.setattr(launcher, "VERSIONS_DIR", tmp_path / "versions")
    monkeypatch.setattr(launcher, "LIBRARIES_DIR", tmp_path / "libraries")
    version_dir = launcher.VERSIONS_DIR / "1.21.11"
    version_dir.mkdir(parents=True)
    (version_dir / "1.21.11.jar").write_bytes(b"jar")
    account = launcher.make_offline_account("CopperBars")
    settings = launcher.Settings(game_directory=str(tmp_path / "game"), memory_mb=4096, selected_version="1.21.11")
    command = launcher.build_command("1.21.11", {"mainClass": "net.minecraft.client.main.Main", "libraries": [], "arguments": {"jvm": [], "game": []}}, account, settings)
    assert "-Xmx4096M" in command


def test_legacy_arguments_are_supported(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "find_java", lambda _: "java")
    monkeypatch.setattr(launcher, "VERSIONS_DIR", tmp_path / "versions")
    monkeypatch.setattr(launcher, "LIBRARIES_DIR", tmp_path / "libraries")
    version_dir = launcher.VERSIONS_DIR / "1.12.2"
    version_dir.mkdir(parents=True)
    (version_dir / "1.12.2.jar").write_bytes(b"jar")
    account = launcher.make_offline_account("CopperBars")
    settings = launcher.Settings(game_directory=str(tmp_path / "game"), memory_mb=2048, selected_version="1.12.2")
    command = launcher.build_command("1.12.2", {"mainClass": "net.minecraft.client.main.Main", "libraries": [], "minecraftArguments": "--username ${auth_player_name} --version ${version_name}"}, account, settings)
    assert "CopperBars" in command
    assert "1.12.2" in command


def test_manifest_merge_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "VERSIONS_DIR", tmp_path / "versions")
    monkeypatch.setattr(launcher, "LIBRARIES_DIR", tmp_path / "libraries")
    monkeypatch.setattr(launcher, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(launcher, "MANIFEST_FILE", tmp_path / "manifest.json")
    launcher.VERSIONS_DIR.mkdir(parents=True)
    launcher.LIBRARIES_DIR.mkdir(parents=True)
    launcher.ASSETS_DIR.mkdir(parents=True)
    launcher.save_json(launcher.MANIFEST_FILE, {"versions": [{"id": "child", "url": "http://unused", "sha1": ""}, {"id": "parent", "url": "http://unused", "sha1": ""}]})
    parent = {"id": "parent", "mainClass": "Parent", "libraries": [{"name": "a:b:c"}]}
    child = {"id": "child", "inheritsFrom": "parent", "mainClass": "Child", "libraries": [{"name": "d:e:f"}]}
    def fake_download(url, dest, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = parent if dest.stem == "parent" else child
        dest.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(launcher, "download_file", fake_download)
    monkeypatch.setattr(launcher, "library_artifacts", lambda _: ([], []))
    result = launcher.ensure_version("child")
    assert result["mainClass"] == "Child"
    assert len(result["libraries"]) == 2
