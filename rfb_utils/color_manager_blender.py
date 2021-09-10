import os
import bpy
import sys
from ..rfb_utils.envconfig_utils import envconfig
try:
    from rman_utils.color_manager import ColorManager
except:
    ColorManager = None

__clrmgr__ = None

class ColorManagerBlender(ColorManager):
    def __init__(self, config_path, **kwargs):
        super(ColorManagerBlender, self).__init__(config_path, **kwargs)

    def update(self):
        ociopath = get_env_config_path()
        super(ColorManagerBlender, self).update(ociopath)

def color_manager():
    """return the color manager singleton
    """
    if __clrmgr__ is None:
        init()
    return __clrmgr__


def init():
    """initialize ColorManager
    """
    global __clrmgr__

    if __clrmgr__ is None:
        ociopath = get_env_config_path()
        if ColorManager:
            __clrmgr__ = ColorManagerBlender(ociopath)

def get_env_config_path():
    """return ocio config path from the environment
    """
    blender_config_path = envconfig().get_blender_ocio_config()
    ociopath = envconfig().getenv('OCIO', blender_config_path)
    return ociopath

def get_config_path():
    """return ocio config path
    """
    clrmgr = color_manager()
    if clrmgr:
        return clrmgr.config_file_path()

    return get_env_config_path()

def get_colorspace_name():
    """return the scene colorspace name. updating with $OCIO
    """
    clrmgr = color_manager()
    
    if ColorManager:
        clrmgr.update()
        return clrmgr.scene_colorspace_name
        
    return ""