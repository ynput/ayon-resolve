from __future__ import annotations

import re
from pathlib import Path

from ayon_applications import (
    PreLaunchHook,
    LaunchTypes,
    ApplicationLaunchFailed
)


class PreLaunchResolveCheckVersion(PreLaunchHook):
    """Special hook to ensure installed version is compatible with AYON.
    """
    order = 10
    app_groups = {"resolve"}
    launch_types = {LaunchTypes.local}

    def _find_readme(self, executable: str) -> Path | None:
        """Locate the ReadMe.html shipped with the Resolve install.
        - Windows: <install>/Resolve.exe -> <install>/Documents
        - Linux: /opt/resolve/bin/resolve -> /opt/resolve/Documents
        - macOS: .../Contents/MacOS/Resolve -> .../Contents/Documents
        """
        exe = Path(executable).resolve()
        for base in list(exe.parents)[:4]:
            candidate = base / "Documents" / "ReadMe.html"
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _parse_readme(readme: Path) -> tuple[str | None, bool]:
        """ Return version + is studio from readme file.
        """
        text = readme.read_text(encoding="utf-8", errors="replace")
        version = None
        match = re.search(
            r"<title>\s*DaVinci Resolve\s+(\d+\.\d[\d.]*)",
            text,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r"\bDaVinci Resolve(?:\s+Studio)?\s+(\d+\.\d[\d.]*)", text
            )
        if match:
            version = match.group(1).rstrip(".")

        is_studio = bool(
            re.search(r"About DaVinci Resolve\s+Studio\s+\d", text, re.IGNORECASE)
        )
        return version, is_studio

    @staticmethod
    def _is_supported(version: str | None, is_studio: bool) -> bool:
        """Free Resolve 21+ dropped external python scripting."""
        if is_studio:
            return True
        if not version:
            # Unknown version, do not block the launch.
            return True
        major = int(version.split(".")[0])
        return major < 21

    def _should_run_resolve_check_version(self) -> bool:
        resolve_settings = self.data["project_settings"]["resolve"]
        return resolve_settings["check_compatible_ayon_version_on_start"]

    def execute(self):
        if not self._should_run_resolve_check_version():
            return

        executable = self.launch_context.launch_args[0]

        # Detect Resolve version from the shipped ReadMe
        # Cannot rely on '-v' executable output, as it cannot be reliably captured.
        readme = self._find_readme(executable)
        if readme is None:
            self.log.warning(
                "Could not locate Resolve ReadMe.html "
                "from executable: %s.",
                executable,
            )
            return

        try:
            version, is_studio = self._parse_readme(readme)
        except OSError:
            self.log.warning(
                "Could not gather version from ReadMe.html at %s. "
                "Skipping compatibility check.",
                readme,
                exc_info=True,
            )
            return

        edition = "Studio" if is_studio else "Free"
        self.log.debug("Detected DaVinci Resolve %s %s", edition, version)

        if not self._is_supported(version, is_studio):
            raise ApplicationLaunchFailed(
                f"AYON is not supported in DaVinci Resolve {edition} {version}. "
                "Only the studio version supports python external scripting:\n"
                "https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=239823"
            )
