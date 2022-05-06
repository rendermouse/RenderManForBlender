from ..rfb_logger import rfb_log
from ..rfb_utils import texture_utils
from ..rfb_utils import string_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import upgrade_utils
from bpy.app.handlers import persistent
import bpy
import os
import re
import sys
            

__ORIGINAL_BL_FILEPATH__ = None
__ORIGINAL_BL_FILE_FORMAT__ = None
__BL_TMP_FILE__ = None
if sys.platform == ("win32"):
    __BL_TMP_DIR__ = 'C:/tmp'
else:
    __BL_TMP_DIR__ = '/tmp'

@persistent
def rman_load_post(bl_scene):
    from ..rman_ui import rman_ui_light_handlers
    
    string_utils.update_blender_tokens_cb(bl_scene)
    rman_ui_light_handlers.clear_gl_tex_cache(bl_scene)
    texture_utils.txmanager_load_cb(bl_scene)
    upgrade_utils.upgrade_scene(bl_scene)

@persistent
def rman_save_pre(bl_scene):
    string_utils.update_blender_tokens_cb(bl_scene)
    shadergraph_utils.save_bl_ramps(bl_scene)
    upgrade_utils.update_version(bl_scene)

@persistent
def rman_save_post(bl_scene):
    texture_utils.txmanager_pre_save_cb(bl_scene)

@persistent
def texture_despgraph_handler(bl_scene, depsgraph):
    texture_utils.depsgraph_handler(bl_scene, depsgraph)   

@persistent
def render_pre(bl_scene):
    '''
    render_pre handler that changes the Blender filepath attribute
    to match our filename output format. In the case of background
    mode, and use_bl_compositor is off, set it to a temporary filename. 
    The temporary filename will get removed in the render_post handler.
    '''
    global __ORIGINAL_BL_FILEPATH__
    global __ORIGINAL_BL_FILE_FORMAT__
    global __BL_TMP_FILE__
    global __BL_TMP_DIR__
    from ..rfb_utils import display_utils
    from ..rfb_utils import scene_utils

    __ORIGINAL_BL_FILEPATH__ = bl_scene.render.filepath
    __ORIGINAL_BL_FILE_FORMAT__ = bl_scene.render.image_settings.file_format    
    write_comp = scene_utils.should_use_bl_compositor(bl_scene)
    if write_comp:
        filePath = display_utils.get_beauty_filepath(bl_scene, use_blender_frame=True, expand_tokens=True, no_ext=True)
        bl_scene.render.filepath = filePath
        bl_scene.render.image_settings.file_format = 'OPEN_EXR'   
    else:
        __BL_TMP_FILE__ = os.path.join(__BL_TMP_DIR__, '####.png')
        bl_scene.render.filepath = __BL_TMP_FILE__
        bl_scene.render.image_settings.file_format = 'PNG'        

@persistent
def render_post(bl_scene):
    '''
    render_post handler that puts the Blender filepath attribute back
    to its original value. Also, remove the temporary output file if 
    it exists.
    '''

    global __ORIGINAL_BL_FILEPATH__
    global __ORIGINAL_BL_FILE_FORMAT__
    global __BL_TMP_FILE__
    from ..rfb_utils import display_utils

    bl_scene.render.filepath = __ORIGINAL_BL_FILEPATH__
    bl_scene.render.image_settings.file_format = __ORIGINAL_BL_FILE_FORMAT__
    if __BL_TMP_FILE__:
        filePath = re.sub(r'####', '%04d' % bl_scene.frame_current, __BL_TMP_FILE__)
        if os.path.exists(filePath):
            os.remove(filePath)
        __BL_TMP_FILE__ = None

@persistent
def render_stop(bl_scene):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    if rr.is_regular_rendering():
        rfb_log().debug("Render stop handler called. Try to stop the renderer.")
        rr.stop_render()

def register():

    # load_post handler
    if rman_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(rman_load_post)

    # save_pre handler
    if rman_save_pre not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(rman_save_pre)

    # save_post handler       
    if rman_save_post not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(rman_save_post)      

    # texture_depsgraph_update_post handler
    if texture_despgraph_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(texture_despgraph_handler)

    if render_pre not in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.append(render_pre)

    if render_post not in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.append(render_post) 

    if render_stop not in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.append(render_stop)

    if render_stop not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(render_stop)

def unregister():

    if rman_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(rman_load_post)

    if rman_save_pre in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(rman_save_pre)

    if rman_save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(rman_save_post)

    if texture_despgraph_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(texture_despgraph_handler)     

    if render_pre in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.remove(render_pre)

    if render_post in bpy.app.handlers.render_post:
        bpy.app.handlers.render_post.remove(render_post)            

    if render_stop in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(render_stop)

    if render_stop in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(render_stop)

    from . import rman_it_handlers
    rman_it_handlers.remove_ipr_to_it_handlers()                
