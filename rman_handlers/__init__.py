from ..rman_utils import texture_utils
from ..rman_utils import string_utils
from bpy.app.handlers import persistent
import bpy

@persistent
def _update_renderman_lights_(bl_scene):
    '''Update older scenes to use new RenderMan light properties
    '''

    for ob in bpy.context.scene.objects:
        if ob.type != 'LIGHT':
            continue
        if not hasattr(ob.data, 'renderman'):
            continue
        light = ob.data
        rm = light.renderman
        if rm.renderman_type == 'UPDATED':
            continue

        if rm.renderman_type == 'SKY':
            rm.renderman_light_shader = 'PxrEnvDayLight'
            rm.renderman_light_role = 'RMAN_LIGHT'
        elif rm.renderman_type == 'ENV':
            rm.renderman_light_shader = 'PxrDomeLight'
            rm.renderman_light_role = 'RMAN_LIGHT'
        elif rm.renderman_type == 'DIST':
            rm.renderman_light_shader == 'PxrDistantLight'
            rm.renderman_light_role = 'RMAN_LIGHT'                            
        elif rm.renderman_type == 'SPOT':
            light_shader = 'PxrRectLight' if light.use_square else 'PxrDiskLight'
            rm.renderman_light_shader == light_shader
            rm.renderman_light_role = 'RMAN_LIGHT'
        elif rm.renderman_type == 'POINT':            
            rm.renderman_light_shader == 'PxrSphereLight'
            rm.renderman_light_role = 'RMAN_LIGHT'   
        elif rm.renderman_type == 'PORTAL':            
            rm.renderman_light_shader == 'PxrPortalLight'
            rm.renderman_light_role = 'RMAN_LIGHT' 
        elif rm.renderman_type == 'AREA':
            light_shader = 'PxrRectLight'
            if rm.area_shape == 'disk':            
                light_shader = 'PxrDiskLight'
            elif rm.area_shape == 'sphere':
                light_shader = 'PxrSphereLight'
            elif rm.area_shape == 'cylinder':
                light_shader = 'PxrCylinder'
            rm.renderman_light_shader == light_shader
            rm.renderman_light_role = 'RMAN_LIGHT'
        elif rm.renderman_type == 'FILTER':
            lightfilter_shader = 'PxrBlockerLightFilter'
            if rm.filter_type == 'cookie':
                lightfilter_shader = 'PxrCookieLightFilter'
            elif rm.filter_type == 'gobo':
                lightfilter_shader = 'PxrGoboLightFilter'
            elif rm.filter_type == 'intmult':
                lightfilter_shader = 'PxrIntMultLightFilter'
            elif rm.filter_type == 'ramp':
                lightfilter_shader = 'PxrRampLightFilter'                
            elif rm.filter_type == 'rod':
                lightfilter_shader = 'PxrRodLightFilter'
            elif rm.filter_type == 'barn':
                lightfilter_shader = 'PxrBarnLightFilter'
            rm.renderman_light_filter_shader = lightfilter_shader
            rm.renderman_light_role = 'RMAN_LIGHTFILTER'

        rm.renderman_type = 'UPDATED'

def register():
    # parse for textures to convert on scene load
    if texture_utils.parse_for_textures_load_cb not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(texture_utils.parse_for_textures_load_cb)

    # token updater on scene load
    if string_utils.update_blender_tokens_cb not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(string_utils.update_blender_tokens_cb)

    # token updater on scene save
    if string_utils.update_blender_tokens_cb not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(string_utils.update_blender_tokens_cb)     

    # renderman light updater        
    if _update_renderman_lights_ not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_update_renderman_lights_)    

def remove_handlers():
    if texture_utils.parse_for_textures_load_cb in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(texture_utils.parse_for_textures_load_cb)

    if string_utils.update_blender_tokens_cb in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(string_utils.update_blender_tokens_cb)

    if string_utils.update_blender_tokens_cb in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(string_utils.update_blender_tokens_cb)        

    if _update_renderman_lights_ in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_update_renderman_lights_)            