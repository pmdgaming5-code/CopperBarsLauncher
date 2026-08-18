from __future__ import annotations

from typing import Any

from . import core


def rule_allows(rules: list[dict[str, Any]] | None) -> bool:
    """Evaluate Mojang-style allow/disallow rules.

    The launcher defaults to allowed and changes state only for rules that match
    this machine. This correctly handles exception-only rules such as
    'disallow on macOS'. Unknown feature-gated rules are treated as unmatched.
    """
    if not rules:
        return True
    allowed = True
    os_name = core.current_os()
    arch = core.current_arch()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        os_rule = rule.get("os") or {}
        matches = True
        if isinstance(os_rule, dict):
            name = os_rule.get("name")
            if name and name != os_name:
                matches = False
            wanted_arch = os_rule.get("arch")
            if wanted_arch and wanted_arch not in {arch, "x86_64" if arch == "x86_64" else "x86"}:
                matches = False
        if rule.get("features"):
            matches = False
        if matches:
            allowed = rule.get("action", "allow") == "allow"
    return allowed


# Make every core helper use the corrected evaluator.
core.rule_allows = rule_allows
