"""This module is a copy from ayon-resolve"""

import os
import sys

from qtpy import QtCore


class PulseThread(QtCore.QThread):
    """A Timer that checks whether host app is still alive.

    This checks whether the Resolve process is still active at a certain
    interval. This is useful due to how Resolve runs its scripts. Each script
    runs in its own environment and process (a `fusionscript` process each).
    If Resolve would go down and we have a UI process running at the same time
    then it can happen that the `fusionscript.exe` will remain running in the
    background in limbo due to e.g. a Qt interface's QApplication that keeps
    running infinitely.

    Warning:
        When the host is not detected this will automatically exit
        the current process.
    """
    no_host_response = QtCore.Signal()

    def __init__(self, parent=None):
        super(PulseThread, self).__init__(parent=parent)

    def run(self):
        app = getattr(sys.modules["__main__"], "app", None)

        # Interval in milliseconds
        interval = int(os.environ.get("AYON_RESOLVE_PULSE_INTERVAL", 1000))

        while True:
            if self.isInterruptionRequested():
                return

            # We don't need to call Test because PyRemoteObject of the app
            # will actually fail to even resolve the Test function if it has
            # gone down. So we can actually already just check by confirming
            # the method is still getting resolved. (Optimization)
            if app.Test is None:
                self.no_host_response.emit()

            self.msleep(interval)
