from typing import Any


def _convert_ayon_menu_0_4_1(overrides):
    
    # Already new settings
    if "launch_ayon_menu_on_start" in overrides:
        return

    overrides["launch_ayon_menu_on_start"] = overrides.pop("launch_openpype_menu_on_start")


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    _convert_ayon_menu_0_4_1(overrides)
    return overrides