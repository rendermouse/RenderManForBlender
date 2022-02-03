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
    for cls in classes:
        bpy.utils.register_class(cls)
    
def unregister():
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            rfb_log().debug('Could not unregister class: %s' % str(cls))
            pass