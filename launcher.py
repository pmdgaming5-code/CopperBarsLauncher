from __future__ import annotations

from copperbars_launcher import compat as _compat
from copperbars_launcher.core import (
    Account, AppError, Profile, Settings, apply_argument_rules, build_command,
    ensure_managed_java, ensure_version, find_java, import_modpack, java_major_version,
    load_accounts, load_json, load_profiles, load_settings, make_offline_account,
    maven_path, preflight, recommended_ram_mb, required_java_major,
    save_accounts, save_json, save_profiles, save_settings, total_system_ram_mb,
)
from copperbars_launcher.ui_v2 import LauncherApp

rule_allows = _compat.rule_allows

__all__ = [
    "Account", "AppError", "Profile", "Settings", "LauncherApp",
    "apply_argument_rules", "build_command", "ensure_managed_java", "ensure_version",
    "find_java", "import_modpack", "java_major_version", "load_accounts", "load_profiles",
    "load_settings", "load_json", "make_offline_account", "maven_path", "preflight",
    "recommended_ram_mb", "required_java_major", "rule_allows", "save_accounts", "save_json",
    "save_profiles", "save_settings", "total_system_ram_mb",
]


def main() -> None:
    import sys
    if sys.version_info < (3, 11):
        raise SystemExit("CopperBars Launcher Python 3.11 veya daha yeni bir sürüm gerektirir.")
    LauncherApp().mainloop()


if __name__ == "__main__":
    main()
