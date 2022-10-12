try:
    from ..rman_ui import rfb_qt
except:
    raise

import sys
import bpy

from ..rfb_logger import rfb_log
from . import core as bl_pb_core

__PRESET_BROWSER_WINDOW__ = None 

class PresetBrowserQtAppTimed(rfb_qt.RfbBaseQtAppTimed):
    bl_idname = "wm.rpb_qt_app_timed"
    bl_label = "RenderManPreset Browser"

    def __init__(self):
        super(PresetBrowserQtAppTimed, self).__init__()

    def execute(self, context):
        global __PRESET_BROWSER_WINDOW__
        __PRESET_BROWSER_WINDOW__ = PresetBrowserWrapper()
        self._window = __PRESET_BROWSER_WINDOW__
        return super(PresetBrowserQtAppTimed, self).execute(context)

class PresetBrowserWrapper(rfb_qt.RmanQtWrapper):

    def __init__(self):
        super(PresetBrowserWrapper, self).__init__()
        # import here because we will crash Blender
        # when we try to import it globally
        import rman_utils.rman_assets.ui as rui    

        self.resize(1024, 1024)
        self.setWindowTitle('RenderMan Preset Browser')

        if sys.platform != "darwin":
            bg_role = self.backgroundRole()
            plt = self.palette()
            bg_color = plt.color(bg_role)  
            bg_color.setRgb(70, 70, 70)
            plt.setColor(bg_role, bg_color)      
            self.setPalette(plt)              
        
        self.hostPrefs = bl_pb_core.get_host_prefs()
        self.ui = rui.Ui(self.hostPrefs, parent=self)
        self.setLayout(self.ui.topLayout)
        self.show() # Show window        

    def closeEvent(self, event):
        self.hostPrefs.saveAllPrefs()
        event.accept()

class PRMAN_OT_Renderman_Presets_Editor(bpy.types.Operator):
    bl_idname = "renderman.rman_open_presets_editor"
    bl_label = "PresetBrowser"

    def execute(self, context):

        global __PRESET_BROWSER_WINDOW__
        if __PRESET_BROWSER_WINDOW__ and __PRESET_BROWSER_WINDOW__.isVisible():
            return {'FINISHED'}

        if sys.platform == "darwin":
            __PRESET_BROWSER_WINDOW__ = rfb_qt.run_with_timer(__PRESET_BROWSER_WINDOW__, PresetBrowserWrapper)   
        else:
            bpy.ops.wm.rpb_qt_app_timed()
         
        return {'RUNNING_MODAL'}

classes = [         
    PRMAN_OT_Renderman_Presets_Editor,
    PresetBrowserQtAppTimed
]           

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)
    
def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)