import sys
import os
import bpy

from ..rfb_utils import object_utils   
from ..rfb_utils.prefs_utils import get_pref, get_addon_prefs
from ..rfb_logger import rfb_log

import rman_utils.rman_assets.core as ra
import rman_utils.rman_assets.lib as ral
from rman_utils.rman_assets.core import RmanAsset, FilePath
from rman_utils.rman_assets.core import TrMode, TrStorage, TrSpace, TrType
from . import core as bl_pb_core

try: 
    from PySide2 import QtCore, QtWidgets 
    import functools
except ImportError:
    raise
except ModuleNotFoundError:
    raise

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

__PRESET_BROWSER_WINDOW__ = None  # Keep a reference so the window is not garbage collected
COUNTER = 0


class PresetBrowserQtAppTimed(bpy.types.Operator):
    """Run a Qt app inside of Blender, without blocking Blender."""
    bl_idname = "wm.rpb_qt_app_timed"
    bl_label = "Run Qt app"

    _app = None
    _window = None
    _timer = None
    _counter = 0

    def __init__(self):
        print("Init PresetBrowserQtAppTimed")
        self._app = (QtWidgets.QApplication.instance()
                     or QtWidgets.QApplication(sys.argv))

    def modal(self, context, event):
        """Run modal."""
        if event.type == 'TIMER':
            if self._window and not self._window.isVisible():
                self.cancel(context)
                return {'FINISHED'}

            # Just for testing: print something so we know it's running
            # print(f"Modal iteration: {self._counter}")
            self._app.processEvents()
            self._counter += 1

        return {'PASS_THROUGH'}

    def execute(self, context):
        """Process the event loop of the Qt app."""
        self._window = PresetBrowserWrapper()
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

class PresetBrowserWrapper(QtWidgets.QDialog):

    def __init__(self):
        # import here because we will crash Blender
        # when we try to import it globally
        import rman_utils.rman_assets.ui as rui  
        super().__init__()
        
        self.resize(1024, 1024)
        self.setWindowTitle('RenderMan Preset Browser')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        
        self.hostPrefs = bl_pb_core.get_host_prefs()
        self.ui = rui.Ui(self.hostPrefs, parent=self)
        self.setLayout(self.ui.topLayout) # Pass the layout to the window
        self.show() # Show window        

    def closeEvent(self, event):
        self.hostPrefs.saveAllPrefs()
        event.accept()

def process_qt_events(app):
    """Run `processEvents()` on the Qt app."""
    global COUNTER
    if __PRESET_BROWSER_WINDOW__ and not __PRESET_BROWSER_WINDOW__.isVisible():
        return None
    app.processEvents()
    COUNTER += 1
    # print(f"Times iteration: {COUNTER}")
    return 0.01  # Run again after 0.001 seconds



def run_timed_modal_operator():
    """Run the app with help of a timed modal operator."""
    #bpy.utils.register_class(PresetBrowserQtAppTimed)

    # Launch immediately. You can also launch it manually by running this
    # command the Blender Python console.
    bpy.ops.wm.rpb_qt_app_timed()
        
def run_with_timer():
    """Run the app with the new `bpy.app.timers` in Blender 2.80."""
    global __PRESET_BROWSER_WINDOW__
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    __PRESET_BROWSER_WINDOW__ = PresetBrowserWrapper()
    __PRESET_BROWSER_WINDOW__.show()
    bpy.app.timers.register(functools.partial(process_qt_events, app))


class PRMAN_OT_Renderman_Presets_Editor(bpy.types.Operator):
    bl_idname = "renderman.rman_open_presets_editor"
    bl_label = "PresetBrowser"

    def execute(self, context):

        # Choose the method you would like to test.
        if sys.platform == "darwin":
            run_with_timer()   
        else:
            run_timed_modal_operator()  # This seems to work best
         
        return {'RUNNING_MODAL'}

classes = [         
    PRMAN_OT_Renderman_Presets_Editor,
    PresetBrowserQtAppTimed
]           

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
def unregister():
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            rfb_log().debug('Could not unregister class: %s' % str(cls))
            pass