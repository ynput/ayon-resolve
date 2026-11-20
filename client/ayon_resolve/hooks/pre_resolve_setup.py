import os
from pathlib import Path
import platform
import shutil
import subprocess
from ayon_applications import (
    PreLaunchHook,
    LaunchTypes,
    ApplicationLaunchFailed,
)
from ayon_resolve.utils import setup


class PreLaunchResolveSetup(PreLaunchHook):
    """
    This hook will set up the Resolve scripting environment as described in
    Resolve's documentation found with the installed application at
    {resolve}/Support/Developer/Scripting/README.txt

    Prepares the following environment variables:
    - `RESOLVE_SCRIPT_API`
    - `RESOLVE_SCRIPT_LIB`

    It adds $RESOLVE_SCRIPT_API/Modules to PYTHONPATH.

    Additionally it sets up the Python home for Python 3 based on the
    RESOLVE_PYTHON3_HOME in the environment (usually defined in Ayon's
    Application environment for Resolve by the admin). For this it sets
    PYTHONHOME, PYTHON3HOME and PATH variables.

    It also defines:
    - `RESOLVE_UTILITY_SCRIPTS_DIR`: Destination directory for Ayon
        Fusion scripts to be copied to for Resolve to pick them up.
    - `AYON_LOG_NO_COLORS` to True to ensure OP doesn't try to
        use logging with terminal colors as it fails in Resolve.

    """

    app_groups = {"resolve"}
    launch_types = {LaunchTypes.local}

    @staticmethod
    def _is_python3_install(folder):
        """Folder holds `bin/python3` and its standard library (macOS, Linux).

        The standard library check rules out shared prefixes like
        `/opt/homebrew`, which have `bin/python3` but no `lib/python3.x`.
        `lib*` covers `lib64` (Fedora), `python3*` a zipped library.
        """
        if not (folder / "bin" / "python3").exists():
            return False
        return any(
            (path / "os.py").is_file() or path.suffix == ".zip"
            for path in folder.glob("lib*/python3*")
        )

    def _get_python3_home(self, current_platform):
        """Return the Python 3 install folder from `RESOLVE_PYTHON3_HOME`.

        On macOS and Linux Resolve runs `<PYTHON3HOME>/bin/python3`. When it
        is missing, Resolve 21+ silently falls back to its bundled Python,
        which ignores PYTHONPATH, so AYON never loads. A `bin` folder is
        the usual mistake, so step up from it.

        Raises:
            ApplicationLaunchFailed: The folder is not set, does not exist
                or does not hold a Python 3 interpreter.
        """
        expected = (
            "`RESOLVE_PYTHON3_HOME` must point at the Python 3 install "
            "folder: the one that holds `python.exe` on Windows, or `bin` "
            "and `lib` on macOS and Linux (not `bin` itself)."
        )
        value = self.launch_context.env.get("RESOLVE_PYTHON3_HOME", "")
        if not value.strip():
            raise ApplicationLaunchFailed(
                "`RESOLVE_PYTHON3_HOME` is not set in the Resolve "
                f"application environment.\n\n{expected}"
            )

        python3_home = Path(value.strip()).expanduser()
        if not python3_home.is_dir():
            raise ApplicationLaunchFailed(
                f"Python 3 folder does not exist: `{python3_home}`\n\n"
                f"{expected}"
            )

        if current_platform == "windows":
            return python3_home

        if self._is_python3_install(python3_home):
            return python3_home

        # The value is the `bin` folder of a Python install: the folder is
        # named `bin` and its parent passes the install check (which needs
        # `<parent>/bin/python3`, so this very folder holds `python3`)
        parent = python3_home.parent
        if python3_home.name == "bin" and self._is_python3_install(parent):
            self.log.warning(
                f"`RESOLVE_PYTHON3_HOME` points at a `bin` folder "
                f"(`{python3_home}`), using its parent folder instead. "
                "Please set it to the Python install folder."
            )
            return parent

        raise ApplicationLaunchFailed(
            f"No Python 3 install found in `{python3_home}` "
            "(`bin/python3` and its standard library in `lib`). "
            "Resolve would fall back to its own Python, which cannot "
            f"load AYON.\n\n{expected}"
        )

    def _resolve_python_has_pyside6(self, python3_home_str):
        """Check if Resolve's Python can find PySide6.

        Never raises: any failure is logged and treated as "not found".
        """
        python_search_path = os.pathsep.join(
            [python3_home_str, os.path.join(python3_home_str, "bin")]
        )
        python_exe = (
            shutil.which("python3", path=python_search_path)
            or shutil.which("python", path=python_search_path)
        )
        if not python_exe:
            self.log.info(
                f"No Python executable found in `{python3_home_str}`, "
                "skipping PySide6 detection."
            )
            return False

        script = (
            "import importlib.util, sys;"
            "sys.exit(0 if importlib.util.find_spec('PySide6') else 1)"
        )
        try:
            subprocess.run(
                [python_exe, "-c", script],
                env=self.launch_context.env,
                capture_output=True,
                timeout=30,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.info(
                f"PySide6 not detected in Resolve Python ({python_exe}): {exc}"
            )
            return False
        return True

    def execute(self):
        current_platform = platform.system().lower()

        programdata = self.launch_context.env.get("PROGRAMDATA", "")
        resolve_script_api_locations = {
            "windows": (
                f"{programdata}/Blackmagic Design/"
                "DaVinci Resolve/Support/Developer/Scripting"
            ),
            "darwin": (
                "/Library/Application Support/Blackmagic Design"
                "/DaVinci Resolve/Developer/Scripting"
            ),
            "linux": "/opt/resolve/Developer/Scripting",
        }
        resolve_script_api = Path(
            resolve_script_api_locations[current_platform]
        )
        self.log.info(
            f"setting RESOLVE_SCRIPT_API variable to {resolve_script_api}"
        )
        self.launch_context.env[
            "RESOLVE_SCRIPT_API"
        ] = resolve_script_api.as_posix()

        resolve_script_lib_dirs = {
            "windows": (
                "C:/Program Files/Blackmagic Design"
                "/DaVinci Resolve/fusionscript.dll"
            ),
            "darwin": (
                "/Applications/DaVinci Resolve/DaVinci Resolve.app"
                "/Contents/Libraries/Fusion/fusionscript.so"
            ),
            "linux": "/opt/resolve/libs/Fusion/fusionscript.so",
        }
        resolve_script_lib = Path(resolve_script_lib_dirs[current_platform])
        self.launch_context.env[
            "RESOLVE_SCRIPT_LIB"
        ] = resolve_script_lib.as_posix()
        self.log.info(
            f"setting RESOLVE_SCRIPT_LIB variable to {resolve_script_lib}"
        )

        # TODO: add OTIO installation from `openpype/requirements.py`
        # making sure python <3.9.* is installed at provided path
        python3_home = self._get_python3_home(current_platform)
        python3_home_str = python3_home.as_posix()
        self.launch_context.env["PYTHONHOME"] = python3_home_str
        # Resolve reads PYTHON3HOME before PYTHONHOME, keep them in sync
        self.launch_context.env["PYTHON3HOME"] = python3_home_str
        self.log.info(f"Path to Resolve Python folder: `{python3_home_str}`")

        # add to the PYTHONPATH
        env_pythonpath = self.launch_context.env["PYTHONPATH"]
        modules_path = Path(resolve_script_api, "Modules").as_posix()
        self.launch_context.env[
            "PYTHONPATH"
        ] = f"{modules_path}{os.pathsep}{env_pythonpath}"

        self.log.debug(f"PYTHONPATH: {self.launch_context.env['PYTHONPATH']}")

        # add the pythonhome folder to PATH because on Windows
        # this is needed for Py3 to be correctly detected within Resolve
        env_path = self.launch_context.env["PATH"]
        self.log.info(f"Adding `{python3_home_str}` to the PATH variable")
        self.launch_context.env[
            "PATH"
        ] = f"{python3_home_str}{os.pathsep}{env_path}"

        self.log.debug(f"PATH: {self.launch_context.env['PATH']}")

        # Resolve python env might contain a legacy PySide2 that AYON used to
        # self-require in previous versions. Force QtPy to use PySide6 if
        # Resolve's Python can import it. Set here because `QT_API` is
        # dropped from the environment before the hooks run.
        if self._resolve_python_has_pyside6(python3_home_str):
            self.log.info("PySide6 found in Resolve Python, setting QT_API.")
            self.launch_context.env["QT_API"] = "pyside6"

        resolve_utility_scripts_dirs = {
            "windows": (
                f"{programdata}/Blackmagic Design"
                "/DaVinci Resolve/Fusion/Scripts/Comp"
            ),
            "darwin": (
                "/Library/Application Support/Blackmagic Design"
                "/DaVinci Resolve/Fusion/Scripts/Comp"
            ),
            "linux": "/opt/resolve/Fusion/Scripts/Comp",
        }
        resolve_utility_scripts_dir = Path(
            resolve_utility_scripts_dirs[current_platform]
        )
        # setting utility scripts dir for scripts syncing
        self.launch_context.env[
            "RESOLVE_UTILITY_SCRIPTS_DIR"
        ] = resolve_utility_scripts_dir.as_posix()

        # remove terminal coloring tags
        self.launch_context.env["AYON_LOG_NO_COLORS"] = "1"

        # Resolve Setup integration
        setup(self.launch_context.env)
