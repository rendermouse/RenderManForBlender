try: 
    from PySide2 import QtCore, QtWidgets 
    import functools
except ModuleNotFoundError:
    raise    
except ImportError:
    raise

import bpy
import sys

"""
-------------------------------------------------
Code from:
https://gitlab.com/-/snippets/1881226

Code modified by ihsieh@pixar.com (Jan 5, 2021)
Original comments below.
-------------------------------------------------
Test for running a Qt app in Blender.

Warning:
    Do not use `app.exec_()`, this will block the Blender UI! And possibly also
    cause threading issues.

In this example there are 4 approaches:
    - Using a timed modal operator (this should also work in Blender 2.79). On
      Windows the `bpy.context` is almost empty and on macOS Blender and the UI
      of the app are blocked. So far this only seems to work on Linux.
    - Using a timed modal operator to keep the Qt GUI alive and communicate via
      `queue.Queue`. So far this seems to work fine on Linux and Windows (macOS
      is untested at the moment).
    - Using a 'normal' modal operator (this should also work in Blender 2.79).
      This doesn't seem to work very well. Because the modal operator is only
      triggered once, the `processEvents()` is also only called once. This
      means after showing, the UI will never be updated again without manually
      calling `processEvents()` again. For me the UI doens't even show up
      properly, because it needs more 'loops' to do this (on Linux).
    - Using `bpy.app.timers` wich was introduced in Blender 2.80. This also
      doesn't work reliably. If you try to get `bpy.context` from within the Qt
      App, it's almost empty. Seems like we run into the 'Blender threading
      issue' again.

TLDR: Use `run_timed_modal_operator_queue`. :)

isort:skip_file

"""

class RfbBaseQtAppTimed(bpy.types.Operator):
    """Run a Qt app inside of Blender, without blocking Blender."""

    _app = None
    _window = None
    _timer = None

    def __init__(self):
        self._app = (QtWidgets.QApplication.instance()
                     or QtWidgets.QApplication(sys.argv))

    def modal(self, context, event):
        """Run modal."""
        if event.type == 'TIMER':
            if self._window and not self._window.isVisible():
                self.cancel(context)
                return {'FINISHED'}

            self._app.processEvents()
        return {'PASS_THROUGH'}

    def execute(self, context):
        """Process the event loop of the Qt app."""
        self._window.show()
        wm = context.window_manager
        # Run every 0.01 seconds
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """Remove event timer when stopping the operator."""
        self._window.close()
        wm = context.window_manager
        wm.event_timer_remove(self._timer)

class RmanQtWrapper(QtWidgets.QDialog):

    def __init__(self):
        super().__init__()        
        if sys.platform == "darwin":
            self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        else:
            self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)         

    def closeEvent(self, event):
        event.accept()

def process_qt_events(app, window):
    """Run `processEvents()` on the Qt app."""
    if window and not window.isVisible():
        return None
    app.processEvents()
    window.update()
    return 0.01  # Run again after 0.001 seconds
        
def run_with_timer(window, cls):
    """Run the app with the new `bpy.app.timers` in Blender 2.80."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    if not window:
        window = cls()
    window.show()
    bpy.app.timers.register(functools.partial(process_qt_events, app, window))
    return window