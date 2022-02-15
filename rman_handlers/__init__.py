from ..rfb_utils import texture_utils
from ..rfb_utils import string_utils
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import upgrade_utils
from ..rman_ui import rman_ui_light_handlers
from bpy.app.handlers import persistent
import bpy

@persistent
def rman_load_post(bl_scene):
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
def depsgraph_update_post(bl_scene, depsgraph):
    texture_utils.depsgraph_handler(bl_scene, depsgraph)             

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

    # depsgraph_update_post handler
    if depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)

def unregister():

    if rman_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(rman_load_post)

    if rman_save_pre in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(rman_save_pre)

    if rman_save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(rman_save_post)

    if depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)              
