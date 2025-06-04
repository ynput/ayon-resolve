import os
import sys

from ayon_core.pipeline import install_host
from ayon_core.lib import Logger

log = Logger.get_logger(__name__)


def main(env):
    from ayon_resolve.api import ResolveHost, launch_ayon_menu

    # Register injected "app" variable at class level for future uses.
    # For free version of DaVinci Resolve, this seems to be
    # the only way to gather the Resolve/Fusion applications.
    #
    # https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=113252
    ResolveHost.set_resolve_modules_from_app(app)

    # activate resolve from openpype
    host = ResolveHost()
    install_host(host)

    launch_ayon_menu()


if __name__ == "__main__":
    result = main(os.environ)
    sys.exit(not bool(result))
