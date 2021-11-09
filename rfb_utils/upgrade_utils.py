from .. import rman_constants
from ..rfb_utils import shadergraph_utils
from ..rfb_logger import rfb_log
import bpy

def upgrade_242(scene):
    shadergraph_utils.reload_bl_ramps(scene, check_library=False)

def upgrade_scene(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        version = scene.renderman.renderman_version
        if version == '' or version < '24.2':
            rfb_log().debug('Upgrade scene to 24.2')
            upgrade_242(scene)
        
def update_version(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        scene.renderman.renderman_version = rman_constants.RMAN_SUPPORTED_VERSION_STRING