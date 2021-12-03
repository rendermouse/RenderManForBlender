from .. import rman_constants
from ..rfb_utils import shadergraph_utils
from ..rfb_logger import rfb_log
import bpy

def upgrade_242(scene):
    shadergraph_utils.reload_bl_ramps(scene, check_library=False)

def upgrade_243(scene):
    for node in shadergraph_utils.get_all_shading_nodes():
        nt = node.id_data

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


def upgrade_scene(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        version = scene.renderman.renderman_version
        if version == '':
            version = '24.1'

        if version < '24.2':
            rfb_log().debug('Upgrade scene to 24.2')
            upgrade_242(scene)
            
        if version < '24.3':
            rfb_log().debug('Upgrade scene to 24.3')
            upgrade_243(scene)
               
def update_version(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        scene.renderman.renderman_version = rman_constants.RMAN_SUPPORTED_VERSION_STRING