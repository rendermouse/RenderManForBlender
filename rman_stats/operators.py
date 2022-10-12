try:
    from ..rman_ui import rfb_qt
except:
    raise

import bpy
import sys
from ..rfb_logger import rfb_log
from .. import rman_render

__STATS_WINDOW__ = None 

class LiveStatsQtAppTimed(rfb_qt.RfbBaseQtAppTimed):
    bl_idname = "wm.live_stats_qt_app_timed"
    bl_label = "Live Stats"

    def __init__(self):
        super(LiveStatsQtAppTimed, self).__init__()

    def execute(self, context):
        self._window = RmanStatsWrapper()
        return super(LiveStatsQtAppTimed, self).execute(context)
    
class RmanStatsWrapper(rfb_qt.RmanQtWrapper):

    def __init__(self):
        super(RmanStatsWrapper, self).__init__()

        # import here because we will crash Blender
        # when we try to import it globally
        import rman_utils.stats_config.ui as rui  

        self.resize(512, 512)
        self.setWindowTitle('RenderMan Live Stats')
        
        rr = rman_render.RmanRender.get_rman_render()
        mgr = rr.stats_mgr.mgr
        self.ui = rui.StatsManagerUI(self, manager=mgr, show_connect=True, show_config=False)
        self.setLayout(self.ui.topLayout)
        self.show() # Show window   

    def show(self):
        if not self.ui.manager.clientConnected():
            self.ui.attachCB()                    
        else:
            # This is a bit weird. If the stats manager is already
            # connected, the UI doesn't seem to update the connection status when
            # first showing the window.
            # For now, just kick the UI's connectedTimer
            self.ui.connectedTimer.start(1000)
            self.ui.attachBtn.setText("Connecting...")
        
        super(RmanStatsWrapper, self).show()

    def closeEvent(self, event):
        event.accept()

class PRMAN_OT_Open_Stats(bpy.types.Operator):
    bl_idname = "renderman.rman_open_stats"
    bl_label = "Live Stats"

    def execute(self, context):

        global __STATS_WINDOW__
        if sys.platform == "darwin":
            rfb_qt.run_with_timer(__STATS_WINDOW__, RmanStatsWrapper)
        else:
            bpy.ops.wm.live_stats_qt_app_timed()
         
        return {'RUNNING_MODAL'}

classes = [         
    PRMAN_OT_Open_Stats,
    LiveStatsQtAppTimed
]           

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 
    
def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes) 