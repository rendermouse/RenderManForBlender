__QT_LOADED__ = False

try:
    from ..rman_ui import rfb_qt
except:
    raise

import sys
import bpy
import hashlib

from ..rfb_logger import rfb_log

__QT_LOADED__ = True
__TXMANAGER_WINDOW__ = None 

class TxManagerQtAppTimed(rfb_qt.RfbBaseQtAppTimed):
    bl_idname = "wm.txm_qt_app_timed"
    bl_label = "Texture Manager"

    def __init__(self):
        super(TxManagerQtAppTimed, self).__init__()

    def execute(self, context):
        self._window = create_widget()
        return super(TxManagerQtAppTimed, self).execute(context)

def parse_scene():
    from ..rfb_utils import texture_utils
    bl_scene = bpy.context.scene
    mgr = texture_utils.get_txmanager().txmanager
    mgr.reset()
    texture_utils.parse_for_textures(bl_scene)

def _append_to_tx_list(file_path_list):
    """Called by the txmanager when extra files are added to the scene list.
    """
    from ..rfb_utils import texture_utils
    bl_scene = bpy.context.scene
    txmgr = texture_utils.get_txmanager().txmanager
    texture_utils.parse_for_textures(bl_scene)    
    for fpath in file_path_list:
        # Pass None as the nodeID and a hash will be generated.
        texid = hashlib.sha1(fpath.encode('utf-8')).hexdigest()
        txmgr.add_texture(texid, fpath)
    txmgr.update_ui_list()
    # make sure to restart the queue.
    txmgr.txmake_all(start_queue=True, blocking=False)    

def create_widget():
    global __TXMANAGER_WINDOW__
    if not __TXMANAGER_WINDOW__:
        import rman_utils.txmanager.ui as rui    
        from ..rfb_utils import texture_utils    
        mgr = texture_utils.get_txmanager().txmanager
        __TXMANAGER_WINDOW__ = rui.TxManagerUI(None, txmanager=mgr, 
                                                parse_scene_func=parse_scene,
                                                append_tx_func=_append_to_tx_list,
                                                help_func=None)
        mgr.ui = __TXMANAGER_WINDOW__
    return __TXMANAGER_WINDOW__

class PRMAN_OT_TxManager_Qt(bpy.types.Operator):
    bl_idname = "rman_txmgr_list.open_txmanager"
    bl_label = "Texture Manager"

    nodeID: bpy.props.StringProperty(default='')    

    def execute(self, context):
        from ..rfb_utils import texture_utils
        global __TXMANAGER_WINDOW__
        if sys.platform == "darwin":
            rfb_qt.run_with_timer(__TXMANAGER_WINDOW__, create_widget)   
        else:
            bpy.ops.wm.txm_qt_app_timed()
        mgr = texture_utils.get_txmanager().txmanager
        mgr.update_ui_list()
        if self.nodeID:
            txfile = mgr.get_txfile_from_id(self.nodeID)
            mgr.ui.select_txfile(txfile)        
         
        return {'RUNNING_MODAL'}

classes = [         
    PRMAN_OT_TxManager_Qt,
    TxManagerQtAppTimed
]           

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 
    
def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes) 