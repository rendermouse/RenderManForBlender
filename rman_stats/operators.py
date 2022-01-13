try: 
    from PySide2 import QtCore, QtWidgets 
    import functools
except ModuleNotFoundError:
    raise    
except ImportError:
    raise

import bpy
import sys
from ..rfb_logger import rfb_log
import rman_utils.stats_config.core as rs
from .. import rman_render

__STATS_WINDOW__ = None  # Keep a reference so the window is not garbage collected
COUNTER = 0


class LiveStatsQtAppTimed(bpy.types.Operator):
    """Run a Qt app inside of Blender, without blocking Blender."""
    bl_idname = "wm.run_qt_app_timed"
    bl_label = "Run Qt app"

    _app = None
    _window = None
    _timer = None
    _counter = 0

    def __init__(self):
        print("Init LiveStatsQtAppTimed")
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
        self._window = RmanStatsWrapper()
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

class RmanStatsWrapper(QtWidgets.QDialog):

    def __init__(self):
        # import here because we will crash Blender
        # when we try to import it globally
        import rman_utils.stats_config.ui as rui  
        super().__init__()
        
        self.resize(512, 512)
        self.setWindowTitle('RenderMan Preset Browser')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        
        rr = rman_render.RmanRender.get_rman_render()
        mgr = rr.stats_mgr.mgr
        self.ui = rui.StatsManagerUI(self, manager=mgr, show_connect=True, show_config=False)
        self.setLayout(self.ui.topLayout) # Pass the layout to the window
        self.show() # Show window        

    def closeEvent(self, event):
        event.accept()

def process_qt_events(app):
    """Run `processEvents()` on the Qt app."""
    global COUNTER
    if __STATS_WINDOW__ and not __STATS_WINDOW__.isVisible():
        return None
    app.processEvents()
    COUNTER += 1
    # print(f"Times iteration: {COUNTER}")
    return 0.01  # Run again after 0.001 seconds



def run_timed_modal_operator():
    """Run the app with help of a timed modal operator."""
    #bpy.utils.register_class(LiveStatsQtAppTimed)

    # Launch immediately. You can also launch it manually by running this
    # command the Blender Python console.
    bpy.ops.wm.run_qt_app_timed()
        
def run_with_timer():
    """Run the app with the new `bpy.app.timers` in Blender 2.80."""
    global __STATS_WINDOW__
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    __STATS_WINDOW__ = RmanStatsWrapper()
    __STATS_WINDOW__.show()
    bpy.app.timers.register(functools.partial(process_qt_events, app))


class PRMAN_OT_Open_Stats(bpy.types.Operator):
    bl_idname = "renderman.rman_open_stats"
    bl_label = "Live Stats"

    def execute(self, context):

        # Choose the method you would like to test.
        if sys.platform == "darwin":
            run_with_timer()   
        else:
            run_timed_modal_operator()  # This seems to work best
         
        return {'RUNNING_MODAL'}

classes = [         
    PRMAN_OT_Open_Stats,
    LiveStatsQtAppTimed
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