from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "CopperBars Launcher"
APP_VERSION = "1.0.1"
DEFAULT_VERSION = "1.21.11"
VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
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
    path = base / "CopperBarsLauncher"
    path.mkdir(parents=True, exist_ok=True)
    return path


ROOT = app_data_dir()
CONFIG_FILE = ROOT / "config.json"
ACCOUNTS_FILE = ROOT / "accounts.json"
MANIFEST_FILE = ROOT / "version_manifest.json"
VERSIONS_DIR = ROOT / "versions"
LIBRARIES_DIR = ROOT / "libraries"
ASSETS_DIR = ROOT / "assets"
JAVA_DIR = ROOT / "runtime"

for directory in (VERSIONS_DIR, LIBRARIES_DIR, ASSETS_DIR):
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
    pass


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


def request_json(
    url: str,
    *,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    body = None
    final_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        final_headers.update(headers)
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        final_headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=body, headers=final_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise AppError(f"HTTP {exc.code}: {details[:500]}") from exc
    except urllib.error.URLError as exc:
        raise AppError(f"Ağ hatası: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AppError("Ağ isteği zaman aşımına uğradı.") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AppError("Sunucu geçerli JSON döndürmedi.") from exc


def request_json_body(
    url: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    final_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        final_headers.update(headers)
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=final_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise AppError(f"HTTP {exc.code}: {details[:500]}") from exc
    except urllib.error.URLError as exc:
        raise AppError(f"Ağ hatası: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AppError("Ağ isteği zaman aşımına uğradı.") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AppError("Sunucu geçerli JSON döndürmedi.") from exc


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file_name(value: str) -> str:
    return (re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "file")


def download_file(
    url: str,
    destination: Path,
    *,
    expected_sha1: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> None:
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
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as handle:
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
        temporary.unlink(missing_ok=True)
        raise AppError(f"İndirme başarısız: {url}\n{exc}") from exc
    temporary.replace(destination)
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


def current_arch() -> str:
    arch = platform.machine().lower()
    return "x86_64" if arch in {"amd64", "x86_64", "x64", "aarch64"} else "x86"


def rule_allows(rules: list[dict[str, Any]] | None) -> bool:
    if not rules:
        return True
    allowed = False
    os_name = current_os()
    arch = current_arch()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        features = rule.get("features", {})
        os_rule = rule.get("os", {})
        matches = True
        if isinstance(os_rule, dict):
            if os_rule.get("name") and os_rule["name"] != os_name:
                matches = False
            if os_rule.get("arch") and os_rule["arch"] not in {arch, "x86_64" if arch == "x86_64" else "x86"}:
                matches = False
        # Feature-gated libraries are only used when we explicitly know the feature.
        # Unknown launcher features must not be treated as enabled.
        if features and any(features.values()):
            matches = False
        if not matches:
            continue
        action = rule.get("action", "allow")
        if action == "allow":
            allowed = True
        elif action == "disallow":
            allowed = False
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
        natives_map = library.get("natives", {})
        native_key = None
        if isinstance(natives_map, dict) and current_os() in natives_map:
            native_key = str(natives_map[current_os()]).replace("${arch}", "64" if current_arch() == "x86_64" else "32")
        native = classifiers.get(native_key) if native_key else None
        if native and native.get("url") and native.get("path"):
            path = LIBRARIES_DIR / native["path"]
            download_file(native["url"], path, expected_sha1=native.get("sha1"))
            natives.append(path)
    return classpath, natives


def _merge_version(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = dict(parent)
    merged.update(child)
    if "libraries" in parent or "libraries" in child:
        merged["libraries"] = list(parent.get("libraries", [])) + list(child.get("libraries", []))
    for key in ("arguments", "downloads"):
        if key in child:
            merged[key] = child[key]
    return merged


def ensure_version(version_id: str, progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    manifest = load_json(MANIFEST_FILE, None)
    if not isinstance(manifest, dict):
        if progress:
            progress("Sürüm listesi indiriliyor…")
        manifest = request_json(VERSION_MANIFEST)
        save_json(MANIFEST_FILE, manifest)
    entry = next((item for item in manifest.get("versions", []) if item.get("id") == version_id), None)
    if not entry:
        raise AppError(f"Minecraft {version_id} sürümü bulunamadı.")

    version_dir = VERSIONS_DIR / version_id
    local_version = version_dir / f"{version_id}.json"
    version_dir.mkdir(parents=True, exist_ok=True)
    if not local_version.exists():
        if progress:
            progress(f"{version_id} manifesti indiriliyor…")
        download_file(entry["url"], local_version, expected_sha1=entry.get("sha1"))
    version_json = load_json(local_version, None)
    if not isinstance(version_json, dict):
        raise AppError("Sürüm manifesti okunamadı.")
    if version_json.get("inheritsFrom"):
        parent = ensure_version(str(version_json["inheritsFrom"]), progress)
        version_json = _merge_version(parent, version_json)

    client = version_json.get("downloads", {}).get("client", {})
    client_path = version_dir / f"{version_id}.jar"
    if client.get("url") and progress:
        progress(f"{version_id} istemci dosyası hazırlanıyor…")
    if client.get("url"):
        download_file(client["url"], client_path, expected_sha1=client.get("sha1"))
    if version_json.get("assetIndex", {}).get("url"):
        asset_index = version_json["assetIndex"]
        index_path = ASSETS_DIR / "indexes" / f"{asset_index['id']}.json"
        if not index_path.exists():
            download_file(asset_index["url"], index_path, expected_sha1=asset_index.get("sha1"))
        asset_json = load_json(index_path, {})
        for obj in asset_json.get("objects", {}).values():
            digest = obj.get("hash")
            if not digest:
                continue
            asset_path = ASSETS_DIR / "objects" / digest[:2] / digest
            if not asset_path.exists():
                download_file(
                    f"https://resources.download.minecraft.net/{digest[:2]}/{digest}",
                    asset_path,
                    expected_sha1=digest,
                )
    library_artifacts(version_json)
    return version_json


def find_java(explicit: str) -> str:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    java_on_path = shutil.which("java")
    if java_on_path:
        candidates.append(Path(java_on_path))
    java_home = os.getenv("JAVA_HOME")
    if java_home:
        candidates.append(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java"))
    candidates.append(JAVA_DIR / "bin" / ("java.exe" if os.name == "nt" else "java"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise AppError("Java bulunamadı. Ayarlar bölümünden Java yolunu seçin.")


def java_major_version(java_path: str) -> int | None:
    try:
        result = subprocess.run([java_path, "-version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stderr or result.stdout or "").strip()
    match = re.search(r'version\s+"(\d+)', text)
    return int(match.group(1)) if match else None


def required_java_major(version_json: dict[str, Any]) -> int | None:
    value = version_json.get("javaVersion", {}).get("majorVersion")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def apply_argument_rules(arg_list: list[dict[str, Any]] | list[str], *, replacements: dict[str, str]) -> list[str]:
    result: list[str] = []
    for item in arg_list:
        if isinstance(item, str):
            result.append(item)
            continue
        if not isinstance(item, dict) or not rule_allows(item.get("rules")):
            continue
        value = item.get("value", [])
        values = [value] if isinstance(value, str) else list(value)
        result.extend(str(x) for x in values)
    expanded: list[str] = []
    for value in result:
        for key, replacement in replacements.items():
            value = value.replace(key, replacement)
        expanded.append(value)
    return expanded


def extract_natives(version_id: str, version_json: dict[str, Any]) -> Path:
    natives_dir = VERSIONS_DIR / version_id / "natives"
    natives_dir.mkdir(parents=True, exist_ok=True)
    for library in version_json.get("libraries", []):
        if not isinstance(library, dict) or not rule_allows(library.get("rules")):
            continue
        natives_map = library.get("natives", {})
        if current_os() not in natives_map:
            continue
        key = str(natives_map[current_os()]).replace("${arch}", "64" if current_arch() == "x86_64" else "32")
        native = library.get("downloads", {}).get("classifiers", {}).get(key)
        if not native:
            continue
        archive = LIBRARIES_DIR / native["path"]
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                if member.is_dir() or member.filename.startswith("META-INF/"):
                    continue
                filename = Path(member.filename).name
                if not filename:
                    continue
                target = natives_dir / filename
                with zf.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    return natives_dir


def build_command(version_id: str, version_json: dict[str, Any], account: Account, settings: Settings) -> list[str]:
    java = find_java(settings.java_path)
    version_dir = VERSIONS_DIR / version_id
    client_jar = version_dir / f"{version_id}.jar"
    if not client_jar.exists():
        raise AppError(f"Minecraft istemci dosyası eksik: {client_jar}")
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
        raw = str(version_json.get("minecraftArguments", ""))
        game_args = apply_argument_rules(raw.split(), replacements=replacements)
        jvm_args = ["-Djava.library.path=${natives_directory}".replace("${natives_directory}", str(natives_dir))]
    if not any(value in {"-cp", "-classpath"} for value in jvm_args):
        jvm_args.extend(["-cp", classpath])
    max_ram = max(1024, min(65536, int(settings.memory_mb)))
    min_ram = max(512, min(max_ram, max(512, max_ram // 4)))
    jvm_args = [f"-Xms{min_ram}M", f"-Xmx{max_ram}M"] + jvm_args
    main_class = version_json.get("mainClass")
    if not main_class:
        raise AppError("Sürüm manifestinde mainClass bulunamadı.")
    return [java] + jvm_args + [main_class] + game_args


def launch_game(version_id: str, settings: Settings, account: Account, log: Callable[[str], None]) -> subprocess.Popen[str]:
    version_json = ensure_version(version_id, progress=log)
    command = build_command(version_id, version_json, account, settings)
    required = required_java_major(version_json)
    java_path = command[0]
    detected = java_major_version(java_path)
    if required and detected and detected < required:
        raise AppError(f"Bu Minecraft sürümü Java {required} istiyor; seçili Java {detected}.")
    log("Minecraft başlatılıyor…")
    process = subprocess.Popen(
        command,
        cwd=settings.game_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    threading.Thread(target=stream_process, args=(process, log), daemon=True).start()
    return process


def stream_process(process: subprocess.Popen[str], log: Callable[[str], None]) -> None:
    if process.stdout:
        for line in process.stdout:
            text = line.rstrip()
            if text:
                log(text)
    code = process.wait()
    log(f"Minecraft kapandı. Çıkış kodu: {code}")


def microsoft_login(client_id: str, progress: Callable[[str], None]) -> Account:
    client_id = client_id.strip() or MS_CLIENT_ID
    device = request_json(MS_DEVICE_ENDPOINT, data={"client_id": client_id, "scope": MS_SCOPE})
    verification_uri = device.get("verification_uri") or device.get("verification_uri_complete")
    user_code = device.get("user_code")
    device_code = device.get("device_code")
    if not verification_uri or not user_code or not device_code:
        raise AppError("Microsoft cihaz kodu yanıtı eksik.")
    progress(f"Tarayıcıda {verification_uri} adresini açın ve kodu girin: {user_code}")
    if hasattr(os, "startfile"):
        try:
            os.startfile(verification_uri)
        except OSError:
            pass
    deadline = time.time() + int(device.get("expires_in", 900))
    interval = max(5, int(device.get("interval", 5)))
    token: dict[str, Any] | None = None
    while time.time() < deadline:
        time.sleep(interval)
        try:
            token = request_json(
                MS_TOKEN_ENDPOINT,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": client_id,
                    "device_code": device_code,
                },
            )
            break
        except AppError as exc:
            if "authorization_pending" in str(exc):
                continue
            raise
    if not token or "access_token" not in token:
        raise AppError("Microsoft oturum süresi doldu veya giriş tamamlanmadı.")
    ms_access = token["access_token"]
    xbl = request_json_body(
        XBL_AUTH_ENDPOINT,
        {
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={ms_access}"},
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
        },
    )
    user_hash = xbl["DisplayClaims"]["xui"][0]["uhs"]
    xsts = request_json_body(
        XSTS_ENDPOINT,
        {
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl["Token"]]},
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT",
        },
    )
    mc = request_json_body(
        MINECRAFT_LOGIN_ENDPOINT,
        {"identityToken": f"XBL3.0 x={user_hash};{xsts['Token']}"},
    )
    profile = request_json_body(
        MINECRAFT_PROFILE_ENDPOINT,
        headers={"Authorization": f"Bearer {mc['access_token']}"},
    )
    if not profile.get("id") or not profile.get("name"):
        raise AppError("Bu Microsoft hesabında kullanılabilir bir Minecraft profili bulunamadı.")
    return Account(
        id=str(uuid.uuid4()),
        username=profile["name"],
        uuid=profile["id"],
        type="microsoft",
        access_token=mc["access_token"],
        refresh_token=token.get("refresh_token", ""),
        expires_at=time.time() + int(mc.get("expires_in", 86400)),
    )


def make_offline_account(username: str) -> Account:
    clean = re.sub(r"[^A-Za-z0-9_]+", "", username).strip()[:16]
    if not 3 <= len(clean) <= 16:
        raise AppError("Kullanıcı adı 3–16 karakter olmalı ve yalnızca harf, sayı veya _ içermeli.")
    digest = hashlib.md5(("OfflinePlayer:" + clean).encode("utf-8")).hexdigest()
    offline_uuid = f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"
    return Account(id=str(uuid.uuid4()), username=clean, uuid=offline_uuid, type="offline")


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.settings = load_settings()
        self.accounts = load_accounts()
        self.versions: list[str] = []
        self.busy = False
        self._configure_style()
        self._build_ui()
        self._refresh_accounts()
        self._load_versions_async()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista" if os.name == "nt" else "clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10))
        style.configure("Launch.TButton", font=("Segoe UI", 13, "bold"), padding=12)
        style.configure("Card.TLabelframe", padding=12)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="CopperBars Launcher", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"v{APP_VERSION} • Minecraft Java", style="Sub.TLabel").pack(side="right", pady=(8, 0))

        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True, pady=(18, 0))
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(content, text="Oyun", style="Card.TLabelframe")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ttk.LabelFrame(content, text="Hesap", style="Card.TLabelframe")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ttk.Label(left, text="Minecraft sürümü").pack(anchor="w")
        self.version_var = tk.StringVar(value=self.settings.selected_version)
        self.version_combo = ttk.Combobox(left, textvariable=self.version_var, state="readonly")
        self.version_combo.pack(fill="x", pady=(6, 16))
        self.version_combo.bind("<<ComboboxSelected>>", lambda _event: self._save_selection())

        ttk.Label(left, text="Oyun klasörü").pack(anchor="w")
        game_row = ttk.Frame(left)
        game_row.pack(fill="x", pady=(6, 16))
        self.game_var = tk.StringVar(value=self.settings.game_directory)
        ttk.Entry(game_row, textvariable=self.game_var).pack(side="left", fill="x", expand=True)
        ttk.Button(game_row, text="Seç", command=self._choose_game_dir).pack(side="right", padx=(8, 0))

        ttk.Label(left, text="RAM (MB)").pack(anchor="w")
        self.ram_var = tk.IntVar(value=int(self.settings.memory_mb))
        ttk.Spinbox(left, from_=1024, to=65536, increment=512, textvariable=self.ram_var, width=12).pack(anchor="w", pady=(6, 16))

        ttk.Label(left, text="Durum").pack(anchor="w")
        self.status = tk.StringVar(value="Hazır")
        ttk.Label(left, textvariable=self.status, wraplength=620).pack(anchor="w", pady=(6, 12))
        ttk.Button(left, text="OYNA", style="Launch.TButton", command=self._launch).pack(fill="x", pady=(8, 8))
        ttk.Button(left, text="Ayarlar", command=self._open_settings).pack(fill="x")

        ttk.Label(right, text="Profil").pack(anchor="w")
        self.account_var = tk.StringVar()
        self.account_combo = ttk.Combobox(right, textvariable=self.account_var, state="readonly")
        self.account_combo.pack(fill="x", pady=(6, 12))
        ttk.Button(right, text="Microsoft hesabı ekle", command=self._login_microsoft).pack(fill="x", pady=4)
        ttk.Button(right, text="Offline profil ekle", command=self._add_offline).pack(fill="x", pady=4)
        ttk.Button(right, text="Seçili hesabı sil", command=self._delete_account).pack(fill="x", pady=4)

        ttk.Label(right, text="Günlük", padding=(0, 18, 0, 6)).pack(anchor="w")
        self.log_text = tk.Text(right, height=20, wrap="word", state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    def _log(self, message: str) -> None:
        def append() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, append)

    def _set_status(self, message: str) -> None:
        self.after(0, lambda: self.status.set(message))

    def _load_versions_async(self) -> None:
        def worker() -> None:
            try:
                manifest = load_json(MANIFEST_FILE, None)
                if not isinstance(manifest, dict):
                    manifest = request_json(VERSION_MANIFEST)
                    save_json(MANIFEST_FILE, manifest)
                versions = [
                    item["id"]
                    for item in manifest.get("versions", [])
                    if item.get("type") in {"release", "snapshot"} and item.get("id")
                ]
                self.versions = versions[:300]
                self.after(0, lambda: self.version_combo.configure(values=self.versions))
                if self.settings.selected_version not in self.versions and self.versions:
                    self.settings.selected_version = versions[0]
                    self.version_var.set(versions[0])
                    save_settings(self.settings)
                self._set_status(f"{len(self.versions)} sürüm hazır.")
            except Exception as exc:
                self._log(f"Sürüm listesi alınamadı: {exc}")
                self._set_status("Sürüm listesi alınamadı; internet bağlantısını kontrol edin.")
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_accounts(self) -> None:
        labels = [f"{a.username} ({'Microsoft' if a.type == 'microsoft' else 'Offline'})" for a in self.accounts]
        self.account_combo.configure(values=labels)
        if self.accounts:
            index = next((i for i, a in enumerate(self.accounts) if a.id == self.settings.selected_account), 0)
            self.account_combo.current(index)
            self.settings.selected_account = self.accounts[index].id
            save_settings(self.settings)
        else:
            self.account_combo.set("Hesap ekleyin")

    def _save_selection(self) -> None:
        self.settings.selected_version = self.version_var.get() or DEFAULT_VERSION
        self.settings.game_directory = self.game_var.get().strip() or str(ROOT / "game")
        try:
            self.settings.memory_mb = int(self.ram_var.get())
        except (TypeError, ValueError):
            self.settings.memory_mb = 4096
        index = self.account_combo.current()
        if 0 <= index < len(self.accounts):
            self.settings.selected_account = self.accounts[index].id
        save_settings(self.settings)

    def _choose_game_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.settings.game_directory)
        if chosen:
            self.game_var.set(chosen)
            self._save_selection()

    def _selected_account(self) -> Account:
        index = self.account_combo.current()
        if not 0 <= index < len(self.accounts):
            raise AppError("Önce bir hesap ekleyin.")
        account = self.accounts[index]
        if account.type == "microsoft" and account.expires_at and account.expires_at < time.time():
            raise AppError("Microsoft oturumunun süresi dolmuş. Yeniden giriş yapın.")
        return account

    def _launch(self) -> None:
        if self.busy:
            return
        try:
            self._save_selection()
            account = self._selected_account()
            version = self.settings.selected_version.strip()
            if not version:
                raise AppError("Bir Minecraft sürümü seçin.")
        except AppError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        self.busy = True
        self._set_status("Hazırlanıyor…")
        settings = Settings(**asdict(self.settings))
        settings.memory_mb = max(1024, min(65536, int(settings.memory_mb)))

        def worker() -> None:
            try:
                process = launch_game(version, settings, account, self._log)
                self._set_status("Minecraft çalışıyor.")
                self.after(0, lambda: self._watch_process(process))
            except Exception as exc:
                self.busy = False
                self._set_status("Başlatma başarısız.")
                self._log(f"HATA: {exc}")
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _watch_process(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            self.after(500, lambda: self._watch_process(process))
        else:
            self.busy = False
            self._set_status("Hazır")

    def _login_microsoft(self) -> None:
        if self.busy:
            return
        self.busy = True
        self._set_status("Microsoft girişi bekleniyor…")

        def worker() -> None:
            try:
                account = microsoft_login(self.settings.client_id, self._log)
                self.accounts.append(account)
                save_accounts(self.accounts)
                self.settings.selected_account = account.id
                save_settings(self.settings)
                self.after(0, self._refresh_accounts)
                self._set_status(f"Giriş başarılı: {account.username}")
                self._log(f"Microsoft hesabı eklendi: {account.username}")
            except Exception as exc:
                self._log(f"Microsoft giriş hatası: {exc}")
                self._set_status("Giriş başarısız.")
                self.after(0, lambda: messagebox.showerror("Microsoft Girişi", str(exc)))
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def _add_offline(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Offline profil")
        dialog.resizable(False, False)
        ttk.Label(dialog, text="Kullanıcı adı (3–16 karakter)").pack(padx=16, pady=(16, 6))
        value = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=value, width=30)
        entry.pack(padx=16)

        def add() -> None:
            try:
                account = make_offline_account(value.get())
            except AppError as exc:
                messagebox.showerror(APP_NAME, str(exc), parent=dialog)
                return
            self.accounts.append(account)
            save_accounts(self.accounts)
            self.settings.selected_account = account.id
            save_settings(self.settings)
            dialog.destroy()
            self._refresh_accounts()

        ttk.Button(dialog, text="Ekle", command=add).pack(pady=16)
        entry.focus_set()
        dialog.transient(self)
        dialog.grab_set()

    def _delete_account(self) -> None:
        index = self.account_combo.current()
        if not 0 <= index < len(self.accounts):
            return
        account = self.accounts[index]
        if not messagebox.askyesno(APP_NAME, f"{account.username} hesabı silinsin mi?"):
            return
        self.accounts.pop(index)
        save_accounts(self.accounts)
        self.settings.selected_account = self.accounts[0].id if self.accounts else ""
        save_settings(self.settings)
        self._refresh_accounts()

    def _open_settings(self) -> None:
        window = tk.Toplevel(self)
        window.title("CopperBars Launcher Ayarları")
        window.geometry("540x390")
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Java yolu").pack(anchor="w")
        java_var = tk.StringVar(value=self.settings.java_path)
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(5, 14))
        ttk.Entry(row, textvariable=java_var).pack(side="left", fill="x", expand=True)

        def choose_java() -> None:
            chosen = filedialog.askopenfilename(filetypes=[("Java", "java.exe"), ("Tüm dosyalar", "*.*")])
            if chosen:
                java_var.set(chosen)

        ttk.Button(row, text="Seç", command=choose_java).pack(side="right", padx=(6, 0))
        ttk.Label(frame, text="Microsoft Client ID").pack(anchor="w")
        client_var = tk.StringVar(value=self.settings.client_id)
        ttk.Entry(frame, textvariable=client_var).pack(fill="x", pady=(5, 14))
        ttk.Label(frame, text="Oyun çözünürlüğü").pack(anchor="w")
        size_row = ttk.Frame(frame)
        size_row.pack(fill="x", pady=(5, 14))
        width_var = tk.IntVar(value=self.settings.width)
        height_var = tk.IntVar(value=self.settings.height)
        ttk.Spinbox(size_row, from_=800, to=3840, textvariable=width_var, width=10).pack(side="left")
        ttk.Label(size_row, text=" x ").pack(side="left")
        ttk.Spinbox(size_row, from_=600, to=2160, textvariable=height_var, width=10).pack(side="left")
        ttk.Label(frame, text="Değişiklikler bir sonraki başlatmada kullanılır.", wraplength=480).pack(anchor="w", pady=(8, 14))

        def save() -> None:
            self.settings.java_path = java_var.get().strip()
            self.settings.client_id = client_var.get().strip() or MS_CLIENT_ID
            self.settings.width = max(800, min(3840, int(width_var.get())))
            self.settings.height = max(600, min(2160, int(height_var.get())))
            save_settings(self.settings)
            window.destroy()

        ttk.Button(frame, text="Kaydet", command=save).pack(fill="x", side="bottom")


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("CopperBars Launcher Python 3.11 veya daha yeni bir sürüm gerektirir.")
    app = LauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
