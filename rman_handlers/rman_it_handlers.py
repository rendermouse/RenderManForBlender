from bpy.app.handlers import persistent
import bpy

@persistent
def ipr_it_depsgraph_update_post(bl_scene, depsgraph):
    from ..rman_render import RmanRender
    rman_render = RmanRender.get_rman_render()

    # check updates if we are render ipring into it
    if rman_render.is_ipr_to_it():
        context = bpy.context
        rman_render.update_scene(context, depsgraph)
        rman_render.update_view(context, depsgraph)  


@persistent
def ipr_frame_change_post(bl_scene):
    from ..rman_render import RmanRender
    rman_render = RmanRender.get_rman_render()
    # check updates if we are render ipring into it
    if rman_render.is_ipr_to_it():
        context = bpy.context
        depsgraph = context.evaluated_depsgraph_get()
        rman_render.update_scene(context, depsgraph)
        rman_render.update_view(context, depsgraph)   

def add_ipr_to_it_handlers():      
    '''
    This adds handlers needed when we ipr to it
    '''
    if ipr_it_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(ipr_it_depsgraph_update_post)

    if ipr_frame_change_post not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(ipr_frame_change_post)     

def remove_ipr_to_it_handlers(): 
    '''
    Remove handlers needed when we ipr to it
    '''
    if ipr_it_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(ipr_it_depsgraph_update_post)     

    if ipr_frame_change_post in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(ipr_frame_change_post)                 