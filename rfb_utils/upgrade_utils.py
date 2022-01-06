from .. import rman_constants
from ..rfb_utils import shadergraph_utils
from ..rfb_logger import rfb_log
from collections import OrderedDict
import bpy

def upgrade_242(scene):
    shadergraph_utils.reload_bl_ramps(scene, check_library=False)

def upgrade_243(scene):
    for node in shadergraph_utils.get_all_shading_nodes(scene=scene):
        for prop_name, meta in node.prop_meta.items():
            param_type = meta['renderman_type']       
            if param_type != 'array':
                continue
            array_len = getattr(node, '%s_arraylen' % prop_name)   
            coll_nm = '%s_collection' % prop_name     
            collection = getattr(node, coll_nm)
            param_array_type = meta['renderman_array_type']
            for i in range(array_len):
                elem = collection.add()
                elem.name = '%s[%d]' % (prop_name, len(collection)-1)  
                elem.type = param_array_type

__RMAN_SCENE_UPGRADE_FUNCTIONS__ = OrderedDict()
    
__RMAN_SCENE_UPGRADE_FUNCTIONS__['24.2'] = upgrade_242
__RMAN_SCENE_UPGRADE_FUNCTIONS__['24.3'] = upgrade_243

def upgrade_scene(bl_scene):
    global __RMAN_SCENE_UPGRADE_FUNCTIONS__

    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        version = scene.renderman.renderman_version
        if version == '':
            # we started adding a renderman_version property in 24.1
            version = '24.1'

        for version_str, fn in __RMAN_SCENE_UPGRADE_FUNCTIONS__.items():
            if version < version_str:
                rfb_log().debug('Upgrade scene to %s' % version_str)
                fn(scene)
               
def update_version(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        scene.renderman.renderman_version = rman_constants.RMAN_SUPPORTED_VERSION_STRING