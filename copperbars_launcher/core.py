from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

APP_NAME = "CopperBars Launcher"
APP_VERSION = "2.0.0"
DEFAULT_VERSION = "1.21.11"
VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
JAVA_MANIFEST_BASE = "https://piston-meta.mojang.com/v1/products/java-runtime/"
MS_CLIENT_ID = "00000000402b5328"
MS_SCOPE = "XboxLive.signin offline_access"
MS_DEVICE_ENDPOINT = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
MS_TOKEN_ENDPOINT = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBL_AUTH_ENDPOINT = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_ENDPOINT = "https://xsts.auth.xboxlive.com/xsts/authorize"
MINECRAFT_LOGIN_ENDPOINT = "https://api.minecraftservices.com/authentication/login_with_xbox"
MINECRAFT_PROFILE_ENDPOINT = "https://api.minecraftservices.com/minecraft/profile"
USER_AGENT = f"CopperBarsLauncher/{APP_VERSION} (https://github.com/pmdgaming5-code/CopperBarsLauncher)"


def app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    result = base / "CopperBarsLauncher"
    result.mkdir(parents=True, exist_ok=True)
    return result


ROOT = app_data_dir()
CONFIG_FILE = ROOT / "config.json"
ACCOUNTS_FILE = ROOT / "accounts.json"
PROFILES_FILE = ROOT / "profiles.json"
MANIFEST_FILE = ROOT / "version_manifest.json"
VERSIONS_DIR = ROOT / "versions"
LIBRARIES_DIR = ROOT / "libraries"
ASSETS_DIR = ROOT / "assets"
JAVA_DIR = ROOT / "runtime"

for directory in (VERSIONS_DIR, LIBRARIES_DIR, ASSETS_DIR, JAVA_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@dataclass
class Settings:
    game_directory: str = str(ROOT / "game")
    memory_mb: int = 4096
    selected_version: str = DEFAULT_VERSION
    selected_account: str = ""
    java_path: str = ""
    client_id: str = MS_CLIENT_ID
    width: int = 1280
    height: int = 720
    extra_jvm_args: str = ""
    selected_profile: str = "default"


@dataclass
class Profile:
    id: str
    name: str
    version: str = DEFAULT_VERSION
    memory_mb: int = 4096
    game_directory: str = ""
    extra_jvm_args: str = ""
    created_at: float = 0.0


@dataclass
class Account:
    id: str
    username: str
    uuid: str
    type: str
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0


class AppError(RuntimeError):
    """User-facing launcher error."""


def load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_settings() -> Settings:
    raw = load_json(CONFIG_FILE, {})
    settings = Settings()
    if isinstance(raw, dict):
        for key in asdict(settings):
            if key in raw:
                setattr(settings, key, raw[key])
    return settings


def save_settings(settings: Settings) -> None:
    save_json(CONFIG_FILE, asdict(settings))


def load_profiles() -> list[Profile]:
    raw = load_json(PROFILES_FILE, [])
    profiles: list[Profile] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                try:
                    profile = Profile(**item)
                    if not profile.game_directory:
                        profile.game_directory = str(ROOT / "instances" / profile.id)
                    profiles.append(profile)
                except TypeError:
                    continue
    if not profiles:
        profiles = [Profile(id="default", name="Survival", game_directory=str(ROOT / "instances" / "default"), created_at=time.time())]
        save_profiles(profiles)
    return profiles


def save_profiles(profiles: list[Profile]) -> None:
    save_json(PROFILES_FILE, [asdict(profile) for profile in profiles])


def load_accounts() -> list[Account]:
    raw = load_json(ACCOUNTS_FILE, [])
    accounts: list[Account] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id") and item.get("username") and item.get("uuid"):
                try:
                    accounts.append(Account(**item))
                except TypeError:
                    continue
    return accounts


def save_accounts(accounts: list[Account]) -> None:
    save_json(ACCOUNTS_FILE, [asdict(account) for account in accounts])


def request_json(url: str, *, method: str = "GET", data: dict[str, Any] | None = None,
                headers: dict[str, str] | None = None, timeout: int = 30) -> Any:
    payload = None
    final_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        final_headers.update(headers)
    if data is not None:
        payload = urllib.parse.urlencode(data).encode("utf-8")
        final_headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=payload, headers=final_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise AppError(f"HTTP {exc.code}: {details[:500]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AppError(f"Ağ hatası: {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise AppError("Sunucudan geçersiz JSON geldi.") from exc


def request_json_body(url: str, body: dict[str, Any], *, headers: dict[str, str] | None = None,
                      timeout: int = 30) -> Any:
    final_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        final_headers.update(headers)
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=final_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise AppError(f"HTTP {exc.code}: {details[:500]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AppError(f"Ağ hatası: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError("Sunucudan geçersiz JSON geldi.") from exc


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "file"


def download_file(url: str, destination: Path, *, expected_sha1: str | None = None,
                  progress: Callable[[int, int], None] | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if expected_sha1:
            try:
                if sha1_file(destination).lower() == expected_sha1.lower():
                    return
            except OSError:
                pass
        elif destination.stat().st_size > 0:
            return
    part = destination.with_suffix(destination.suffix + ".part")
    part.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as handle:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        part.unlink(missing_ok=True)
        raise AppError(f"İndirme başarısız: {url}\n{exc}") from exc
    part.replace(destination)
    if expected_sha1:
        actual = sha1_file(destination).lower()
        if actual != expected_sha1.lower():
            destination.unlink(missing_ok=True)
            raise AppError(f"SHA-1 doğrulaması başarısız: {destination.name}")


def current_os() -> str:
    name = platform.system().lower()
    if name.startswith("win"):
        return "windows"
    if name == "darwin":
        return "osx"
    return "linux"


def runtime_platform() -> str:
    machine = platform.machine().lower()
    if os.name == "nt":
        if "arm64" in machine or "aarch64" in machine:
            return "windows-arm64"
        if machine in {"x86", "i386", "i686"}:
            return "windows-x86"
        return "windows-x64"
    if platform.system() == "Darwin":
        return "macos-arm64" if "arm" in machine or "aarch64" in machine else "mac-os"
    if "arm" in machine or "aarch64" in machine:
        return "linux-arm64"
    return "linux"


def current_arch() -> str:
    machine = platform.machine().lower()
    return "x86_64" if machine in {"amd64", "x86_64", "x64", "aarch64", "arm64"} else "x86"


def rule_allows(rules: list[dict[str, Any]] | None) -> bool:
    if not rules:
        return True
    allowed = False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        os_rule = rule.get("os", {})
        matches = True
        if isinstance(os_rule, dict):
            name = os_rule.get("name")
            if name and name != current_os():
                matches = False
            arch = os_rule.get("arch")
            if arch and arch not in {current_arch(), "x86_64" if current_arch() == "x86_64" else "x86"}:
                matches = False
        if rule.get("features"):
            matches = False
        if matches:
            allowed = rule.get("action", "allow") == "allow"
    return allowed


def maven_path(name: str) -> Path:
    parts = name.split(":")
    if len(parts) != 3:
        return LIBRARIES_DIR / safe_file_name(name)
    group, artifact, version = parts
    return LIBRARIES_DIR / group.replace(".", "/") / artifact / version / f"{artifact}-{version}.jar"


def library_artifacts(version_json: dict[str, Any]) -> tuple[list[Path], list[Path]]:
    classpath: list[Path] = []
    natives: list[Path] = []
    for library in version_json.get("libraries", []):
        if not isinstance(library, dict) or not rule_allows(library.get("rules")):
            continue
        downloads = library.get("downloads", {})
        artifact = downloads.get("artifact") if isinstance(downloads, dict) else None
        if artifact and artifact.get("url") and artifact.get("path"):
            path = LIBRARIES_DIR / artifact["path"]
            download_file(artifact["url"], path, expected_sha1=artifact.get("sha1"))
            classpath.append(path)
        classifiers = downloads.get("classifiers", {}) if isinstance(downloads, dict) else {}
        native_map = library.get("natives", {})
        if isinstance(native_map, dict) and current_os() in native_map:
            key = str(native_map[current_os()]).replace("${arch}", "64" if current_arch() == "x86_64" else "32")
            native = classifiers.get(key)
            if native and native.get("url") and native.get("path"):
                path = LIBRARIES_DIR / native["path"]
                download_file(native["url"], path, expected_sha1=native.get("sha1"))
                natives.append(path)
    return classpath, natives


def _merge_version(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = dict(parent)
    merged.update(child)
    merged["libraries"] = list(parent.get("libraries", [])) + list(child.get("libraries", []))
    if "arguments" in parent and "arguments" in child:
        merged_args = dict(parent["arguments"])
        merged_args.update(child["arguments"])
        if "jvm" in parent["arguments"] and "jvm" in child["arguments"]:
            merged_args["jvm"] = list(parent["arguments"]["jvm"]) + list(child["arguments"]["jvm"])
        if "game" in parent["arguments"] and "game" in child["arguments"]:
            merged_args["game"] = list(parent["arguments"]["game"]) + list(child["arguments"]["game"])
        merged["arguments"] = merged_args
    return merged


def ensure_version(version_id: str, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    manifest = load_json(MANIFEST_FILE, None)
    if not isinstance(manifest, dict):
        if progress:
            progress("Minecraft sürüm kataloğu indiriliyor…")
        manifest = request_json(VERSION_MANIFEST)
        save_json(MANIFEST_FILE, manifest)
    entry = next((item for item in manifest.get("versions", []) if item.get("id") == version_id), None)
    if not entry:
        raise AppError(f"Minecraft {version_id} sürümü bulunamadı.")
    version_dir = VERSIONS_DIR / version_id
    version_dir.mkdir(parents=True, exist_ok=True)
    version_file = version_dir / f"{version_id}.json"
    if not version_file.exists():
        if progress:
            progress(f"{version_id} manifesti indiriliyor…")
        download_file(entry["url"], version_file, expected_sha1=entry.get("sha1"))
    version_json = load_json(version_file, None)
    if not isinstance(version_json, dict):
        raise AppError("Sürüm manifesti okunamadı.")
    if version_json.get("inheritsFrom"):
        parent = ensure_version(str(version_json["inheritsFrom"]), progress)
        version_json = _merge_version(parent, version_json)
    client = version_json.get("downloads", {}).get("client", {})
    client_path = version_dir / f"{version_id}.jar"
    if client.get("url"):
        if progress:
            progress(f"{version_id} istemcisi doğrulanıyor…")
        download_file(client["url"], client_path, expected_sha1=client.get("sha1"))
    asset_index = version_json.get("assetIndex", {})
    if asset_index.get("url"):
        index_file = ASSETS_DIR / "indexes" / f"{asset_index['id']}.json"
        download_file(asset_index["url"], index_file, expected_sha1=asset_index.get("sha1"))
        objects = load_json(index_file, {}).get("objects", {})
        for obj in objects.values():
            digest = obj.get("hash")
            if not digest:
                continue
            asset_path = ASSETS_DIR / "objects" / digest[:2] / digest
            download_file(f"https://resources.download.minecraft.net/{digest[:2]}/{digest}", asset_path, expected_sha1=digest)
    library_artifacts(version_json)
    return version_json


def required_java_major(version_json: dict[str, Any]) -> int | None:
    value = version_json.get("javaVersion", {}).get("majorVersion")
    if value is None:
        compatible = version_json.get("compatibleJavaMajors")
        if isinstance(compatible, list) and compatible:
            value = compatible[-1]
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def java_major_version(java_path: str) -> int | None:
    try:
        result = subprocess.run([java_path, "-version"], capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stderr or result.stdout or "").strip()
    match = re.search(r'version\s+"(\d+)', text)
    return int(match.group(1)) if match else None


def _candidate_javas() -> list[Path]:
    candidates: list[Path] = []
    which = shutil.which("java")
    if which:
        candidates.append(Path(which))
    java_home = os.getenv("JAVA_HOME")
    if java_home:
        candidates.append(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java"))
    if os.name == "nt":
        patterns = [
            Path(os.getenv("ProgramFiles", "C:/Program Files")) / "Java",
            Path(os.getenv("ProgramFiles", "C:/Program Files")) / "Eclipse Adoptium",
            Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Eclipse Adoptium",
        ]
        for root in patterns:
            if root.exists():
                for java in root.rglob("java.exe"):
                    candidates.append(java)
    else:
        for root in (Path("/usr/lib/jvm"), Path("/usr/java")):
            if root.exists():
                candidates.extend(root.rglob("java"))
    candidates.append(JAVA_DIR / "auto" / "bin" / ("java.exe" if os.name == "nt" else "java"))
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _java_component(major: int, version_json: dict[str, Any]) -> str:
    explicit = version_json.get("compatibleJavaName")
    if isinstance(explicit, str) and explicit:
        return explicit
    return {8: "java-runtime-alpha", 17: "java-runtime-gamma", 21: "java-runtime-delta", 25: "java-runtime-epsilon"}.get(
        major, f"java-runtime-{major}"
    )


def _runtime_entry(component: str) -> tuple[str, dict[str, Any]]:
    manifest = request_json(f"{JAVA_MANIFEST_BASE}{runtime_platform()}.json")
    versions = manifest.get(component)
    if not isinstance(versions, list) or not versions:
        raise AppError(f"Mojang Java runtime bulunamadı: {component}")
    selected = versions[-1]
    manifest_info = selected.get("manifest", {}) if isinstance(selected, dict) else {}
    url = manifest_info.get("url")
    if not url:
        raise AppError("Java runtime manifest adresi bulunamadı.")
    return str(selected.get("version", {}).get("name", "latest")), request_json(url)


def ensure_managed_java(version_json: dict[str, Any], log: Callable[[str], None] | None = None) -> str:
    major = required_java_major(version_json) or 17
    component = _java_component(major, version_json)
    runtime_name, runtime_manifest = _runtime_entry(component)
    install_root = JAVA_DIR / f"{major}-{safe_file_name(runtime_name)}"
    java_name = "java.exe" if os.name == "nt" else "java"
    java_path = install_root / "bin" / java_name
    if java_path.exists() and java_major_version(str(java_path)) == major:
        return str(java_path)
    if log:
        log(f"Java {major} bulunamadı. Resmi Mojang runtime otomatik indiriliyor…")
    files = runtime_manifest.get("files", {})
    if not isinstance(files, dict):
        raise AppError("Java runtime manifesti bozuk.")
    for relative, meta in files.items():
        if not isinstance(meta, dict):
            continue
        file_type = meta.get("type")
        target = install_root / Path(relative)
        if file_type == "directory":
            target.mkdir(parents=True, exist_ok=True)
            continue
        if file_type == "link":
            continue
        downloads = meta.get("downloads", {})
        raw = downloads.get("raw") if isinstance(downloads, dict) else None
        if not raw or not raw.get("url"):
            continue
        download_file(raw["url"], target, expected_sha1=raw.get("sha1"))
    if not java_path.exists():
        raise AppError("Java kurulumu tamamlandı ancak java çalıştırılabilir dosyası bulunamadı.")
    try:
        java_path.chmod(java_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass
    detected = java_major_version(str(java_path))
    if detected != major:
        raise AppError(f"Java kurulumu doğrulanamadı. Beklenen: {major}, bulunan: {detected or 'bilinmiyor'}")
    return str(java_path)


def find_java(version_json: dict[str, Any], explicit: str = "", log: Callable[[str], None] | None = None) -> str:
    required = required_java_major(version_json)
    if explicit and Path(explicit).is_file():
        detected = java_major_version(explicit)
        if not required or detected == required:
            return explicit
    candidates = _candidate_javas()
    ranked: list[tuple[int, Path]] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        major = java_major_version(str(candidate))
        if major is None:
            continue
        score = 0 if required is not None and major == required else 100 + abs((required or major) - major)
        ranked.append((score, candidate))
    ranked.sort(key=lambda item: item[0])
    if ranked and (required is None or java_major_version(str(ranked[0][1])) == required):
        return str(ranked[0][1])
    return ensure_managed_java(version_json, log=log)


def apply_argument_rules(arg_list: list[dict[str, Any]] | list[str], *, replacements: dict[str, str]) -> list[str]:
    result: list[str] = []
    for item in arg_list:
        if isinstance(item, str):
            result.append(item)
            continue
        if not isinstance(item, dict) or not rule_allows(item.get("rules")):
            continue
        value = item.get("value", [])
        result.extend([value] if isinstance(value, str) else [str(x) for x in value])
    output = []
    for value in result:
        for key, replacement in replacements.items():
            value = value.replace(key, replacement)
        output.append(value)
    return output


def extract_natives(version_id: str, version_json: dict[str, Any]) -> Path:
    target_root = VERSIONS_DIR / version_id / "natives"
    target_root.mkdir(parents=True, exist_ok=True)
    for library in version_json.get("libraries", []):
        if not isinstance(library, dict) or not rule_allows(library.get("rules")):
            continue
        native_map = library.get("natives", {})
        if not isinstance(native_map, dict) or current_os() not in native_map:
            continue
        key = str(native_map[current_os()]).replace("${arch}", "64" if current_arch() == "x86_64" else "32")
        native = library.get("downloads", {}).get("classifiers", {}).get(key)
        if not native:
            continue
        archive = LIBRARIES_DIR / native["path"]
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                if member.is_dir() or member.filename.startswith("META-INF/"):
                    continue
                target = target_root / Path(member.filename).name
                with source.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    return target_root


def build_command(version_id: str, version_json: dict[str, Any], account: Account, settings: Settings,
                  java_path: str | None = None) -> list[str]:
    java = java_path or find_java(version_json, settings.java_path)
    version_dir = VERSIONS_DIR / version_id
    client_jar = version_dir / f"{version_id}.jar"
    if not client_jar.exists():
        raise AppError(f"Minecraft istemcisi eksik: {client_jar}")
    libraries, _ = library_artifacts(version_json)
    classpath = os.pathsep.join(str(path) for path in libraries + [client_jar])
    game_dir = Path(settings.game_directory).expanduser()
    game_dir.mkdir(parents=True, exist_ok=True)
    natives_dir = extract_natives(version_id, version_json)
    replacements = {
        "${auth_player_name}": account.username,
        "${auth_uuid}": account.uuid,
        "${auth_access_token}": account.access_token or "0",
        "${clientid}": account.uuid,
        "${user_type}": "msa" if account.type == "microsoft" else "legacy",
        "${version_name}": version_id,
        "${version_type}": version_json.get("type", "release"),
        "${game_directory}": str(game_dir),
        "${game_assets}": str(ASSETS_DIR),
        "${assets_root}": str(ASSETS_DIR),
        "${assets_index_name}": version_json.get("assetIndex", {}).get("id", "legacy"),
        "${auth_xuid}": "",
        "${resolution_width}": str(settings.width),
        "${resolution_height}": str(settings.height),
        "${natives_directory}": str(natives_dir),
        "${library_directory}": str(LIBRARIES_DIR),
        "${classpath}": classpath,
        "${launcher_name}": APP_NAME,
        "${launcher_version}": APP_VERSION,
    }
    arguments = version_json.get("arguments", {})
    if arguments:
        jvm_args = apply_argument_rules(arguments.get("jvm", []), replacements=replacements)
        game_args = apply_argument_rules(arguments.get("game", []), replacements=replacements)
    else:
        jvm_args = ["-Djava.library.path=${natives_directory}".replace("${natives_directory}", str(natives_dir))]
        game_args = apply_argument_rules(str(version_json.get("minecraftArguments", "")).split(), replacements=replacements)
    if "-cp" not in jvm_args and "-classpath" not in jvm_args:
        jvm_args.extend(["-cp", classpath])
    max_ram = max(1024, min(65536, int(settings.memory_mb)))
    min_ram = max(512, min(max_ram, max_ram // 4))
    jvm_args = [f"-Xms{min_ram}M", f"-Xmx{max_ram}M"] + jvm_args
    if settings.extra_jvm_args.strip():
        jvm_args[2:2] = settings.extra_jvm_args.split()
    main_class = version_json.get("mainClass")
    if not main_class:
        raise AppError("Sürüm manifestinde mainClass bulunamadı.")
    return [java] + jvm_args + [main_class] + game_args


def preflight(version_id: str, settings: Settings, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    version_json = ensure_version(version_id, progress=log)
    java = find_java(version_json, settings.java_path, log=log)
    required = required_java_major(version_json)
    detected = java_major_version(java)
    if required and detected != required:
        raise AppError(f"Minecraft {version_id} Java {required} istiyor; seçilen Java {detected}.")
    client = VERSIONS_DIR / version_id / f"{version_id}.jar"
    if not client.exists() or client.stat().st_size == 0:
        raise AppError("Minecraft client jar hazır değil.")
    try:
        free = shutil.disk_usage(ROOT).free
        if free < 1_000_000_000:
            raise AppError("Diskte 1 GB'dan az boş alan var.")
    except OSError:
        pass
    return {"version": version_json, "java": java, "java_major": detected}


def launch_game(version_id: str, settings: Settings, account: Account, log: Callable[[str], None]) -> subprocess.Popen[str]:
    state = preflight(version_id, settings, log)
    command = build_command(version_id, state["version"], account, settings, java_path=state["java"])
    log(f"Java {state['java_major']} hazır • Minecraft başlatılıyor…")
    process = subprocess.Popen(command, cwd=settings.game_directory, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    import threading
    threading.Thread(target=stream_process, args=(process, log), daemon=True).start()
    return process


def stream_process(process: subprocess.Popen[str], log: Callable[[str], None]) -> None:
    if process.stdout:
        for line in process.stdout:
            text = line.rstrip()
            if text:
                log(text)
    log(f"Minecraft kapandı • çıkış kodu {process.wait()}")


def total_system_ram_mb() -> int:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys / 1024 / 1024)
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 / 1024)
    except (AttributeError, ValueError, OSError):
        return 8192


def recommended_ram_mb() -> int:
    total = total_system_ram_mb()
    return max(2048, min(8192, int(total * 0.5) // 512 * 512))


def make_offline_account(username: str) -> Account:
    clean = re.sub(r"[^A-Za-z0-9_]+", "", username).strip()[:16]
    if not 3 <= len(clean) <= 16:
        raise AppError("Kullanıcı adı 3–16 karakter olmalı.")
    digest = hashlib.md5(("OfflinePlayer:" + clean).encode("utf-8")).hexdigest()
    offline_uuid = f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
    return Account(id=str(uuid.uuid4()), username=clean, uuid=offline_uuid, type="offline")


def import_modpack(zip_path: str, profile: Profile) -> int:
    destination = Path(profile.game_directory)
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path) as archive:
        root = destination.resolve()
        for member in archive.infolist():
            if member.is_dir():
                continue
            name = member.filename.replace("\\", "/")
            parts = [part for part in name.split("/") if part not in {"", "."}]
            if ".." in parts or name.startswith("/"):
                raise AppError("Modpack içinde güvenli olmayan bir dosya yolu bulundu.")
            target = (destination / Path(*parts)).resolve()
            if root != target and root not in target.parents:
                raise AppError("Modpack güvenlik kontrolünü geçemedi.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def microsoft_login(client_id: str, progress: Callable[[str], None]) -> Account:
    client_id = client_id.strip() or MS_CLIENT_ID
    device = request_json(MS_DEVICE_ENDPOINT, data={"client_id": client_id, "scope": MS_SCOPE})
    uri = device.get("verification_uri") or device.get("verification_uri_complete")
    code = device.get("user_code")
    device_code = device.get("device_code")
    if not uri or not code or not device_code:
        raise AppError("Microsoft giriş yanıtı eksik.")
    progress(f"Tarayıcı açılıyor • kod: {code}")
    if hasattr(os, "startfile"):
        try:
            os.startfile(uri)
        except OSError:
            pass
    deadline = time.time() + int(device.get("expires_in", 900))
    interval = max(5, int(device.get("interval", 5)))
    token = None
    while time.time() < deadline:
        time.sleep(interval)
        try:
            token = request_json(MS_TOKEN_ENDPOINT, data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device_code,
            })
            break
        except AppError as exc:
            if "authorization_pending" in str(exc):
                continue
            raise
    if not token or "access_token" not in token:
        raise AppError("Microsoft giriş süresi doldu.")
    ms_access = token["access_token"]
    xbl = request_json_body(XBL_AUTH_ENDPOINT, {
        "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={ms_access}"},
        "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT",
    })
    user_hash = xbl["DisplayClaims"]["xui"][0]["uhs"]
    xsts = request_json_body(XSTS_ENDPOINT, {
        "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl["Token"]]},
        "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT",
    })
    mc = request_json_body(MINECRAFT_LOGIN_ENDPOINT, {"identityToken": f"XBL3.0 x={user_hash};{xsts['Token']}"})
    profile = request_json_body(MINECRAFT_PROFILE_ENDPOINT, headers={"Authorization": f"Bearer {mc['access_token']}"})
    if not profile.get("id") or not profile.get("name"):
        raise AppError("Bu Microsoft hesabında Minecraft profili bulunamadı.")
    return Account(id=str(uuid.uuid4()), username=profile["name"], uuid=profile["id"], type="microsoft",
                   access_token=mc["access_token"], refresh_token=token.get("refresh_token", ""),
                   expires_at=time.time() + int(mc.get("expires_in", 86400)))
