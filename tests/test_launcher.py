import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import launcher
from copperbars_launcher import core


def test_rule_allows_default_and_disallow_exception():
    assert launcher.rule_allows(None)
    assert launcher.rule_allows([{"action": "allow"}])
    assert launcher.rule_allows([{"action": "disallow", "os": {"name": "linux"}}])


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
    monkeypatch.setattr(core, "find_java", lambda version, explicit="", log=None: "java")
    monkeypatch.setattr(core, "extract_natives", lambda *_args, **_kwargs: tmp_path / "natives")
    monkeypatch.setattr(core, "library_artifacts", lambda _: ([], []))
    monkeypatch.setattr(core, "LIBRARIES_DIR", tmp_path / "libraries")
    monkeypatch.setattr(core, "VERSIONS_DIR", tmp_path / "versions")
    version_dir = core.VERSIONS_DIR / "1.21.11"
    version_dir.mkdir(parents=True)
    (version_dir / "1.21.11.jar").write_bytes(b"jar")
    account = launcher.make_offline_account("CopperBars")
    settings = launcher.Settings(game_directory=str(tmp_path / "game"), memory_mb=4096, selected_version="1.21.11")
    command = launcher.build_command(
        "1.21.11",
        {"mainClass": "net.minecraft.client.main.Main", "libraries": [], "arguments": {"jvm": [], "game": []}},
        account,
        settings,
    )
    assert "-Xmx4096M" in command


def test_required_java_major():
    assert launcher.required_java_major({"javaVersion": {"majorVersion": 21}}) == 21
    assert launcher.required_java_major({"compatibleJavaMajors": [17, 21]}) == 21


def test_recommended_ram_is_sane(monkeypatch):
    monkeypatch.setattr(core, "total_system_ram_mb", lambda: 16384)
    assert launcher.recommended_ram_mb() == 8192


def test_profile_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    monkeypatch.setattr(core, "PROFILES_FILE", path)
    profiles = [launcher.Profile(id="x", name="Test", version="1.21.11", memory_mb=4096, game_directory=str(tmp_path / "game"))]
    launcher.save_profiles(profiles)
    loaded = launcher.load_profiles()
    assert loaded[0].name == "Test"


def test_modpack_rejects_path_traversal(tmp_path):
    import zipfile
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../../outside.txt", "bad")
    profile = launcher.Profile(id="x", name="Test", game_directory=str(tmp_path / "game"))
    try:
        launcher.import_modpack(str(zip_path), profile)
    except launcher.AppError:
        return
    raise AssertionError("Unsafe modpack path was accepted")


def test_managed_java_component_fallback():
    assert core._java_component(25, {}) == "java-runtime-epsilon"
    assert core._java_component(21, {}) == "java-runtime-delta"
