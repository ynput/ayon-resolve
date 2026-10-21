from typing import Any

from semver import VersionInfo


def _convert_ayon_menu_0_4_1(overrides):
    if "launch_openpype_menu_on_start" not in overrides:
        return

    overrides["launch_ayon_menu_on_start"] = overrides.pop("launch_openpype_menu_on_start")


def _convert_ExtractProductResources_0_6_3(
    version: VersionInfo,
    overrides: dict[str, Any],
):
    if (version.major, version.minor, version.patch) > (0, 6, 3):
        return

    extract_product_profiles = (
        overrides
        .get("publish", {})
        .get("ExtractProductResources", {})
        .get("profiles")
    )
    if not extract_product_profiles:
        return

    for profile in extract_product_profiles:
        product_base_type = profile.get("product_base_type")

        shared = {}
        for key in ("tags", "custom_tags", "colorspace"):
            override_value = profile.pop(key, None)
            if override_value is not None:
                shared[key] = override_value

        for base_type in ("editorial_pkg", "plate"):
            old_output_defs = profile.get(base_type)
            if not isinstance(old_output_defs, dict):
                continue

            profile_entry = {}
            if old_output_defs:
                profile_entry["output_defs"] = old_output_defs

            if base_type == product_base_type and shared:
                profile_entry["shared"] = shared

            profile[base_type] = [profile_entry] if profile_entry else []


def _convert_ExtractProductResources_0_6_6(overrides: dict[str, Any]):
    """Rename profile `integrate_clip_source` to `keep_original_representation`.

    0.6.6 is the latest version using the old name. The conversion is keyed on
    the old name being present, so it is safe to run on any version.
    """
    extract_product_profiles = (
        overrides
        .get("publish", {})
        .get("ExtractProductResources", {})
        .get("profiles")
    )
    if not extract_product_profiles:
        return

    for profile in extract_product_profiles:
        if "integrate_clip_source" in profile:
            profile["keep_original_representation"] = profile.pop(
                "integrate_clip_source")


def convert_settings_overrides(
    source_version: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    version = VersionInfo.parse(source_version)

    _convert_ayon_menu_0_4_1(overrides)
    _convert_ExtractProductResources_0_6_3(version, overrides)
    _convert_ExtractProductResources_0_6_6(overrides)
    return overrides
