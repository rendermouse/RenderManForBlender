from bpy.props import BoolProperty, PointerProperty, StringProperty, EnumProperty

from ...rfb_logger import rfb_log 
from ...rman_config import RmanBasePropertyGroup
from ...rfb_utils import filepath_utils
import os
import bpy

class RendermanVolumeGeometrySettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    
    def check_openvdb(self):
        ob = bpy.context.object
        if ob.type != 'VOLUME':
            return False        
        volume = bpy.context.volume
        openvdb_file = filepath_utils.get_real_path(volume.filepath)
        return os.path.exists(openvdb_file)

    has_openvdb: BoolProperty(name='', get=check_openvdb)

classes = [         
    RendermanVolumeGeometrySettings
]           

def register():
    from ...rfb_utils import register_utils  

    for cls in classes:
        cls._add_properties(cls, 'rman_properties_volume')
        register_utils.rman_register_class(cls)  

    bpy.types.Volume.renderman = PointerProperty(
        type=RendermanVolumeGeometrySettings,
        name="Renderman Voume Geometry Settings")

def unregister():

    del bpy.types.Volume.renderman

    from ...rfb_utils import register_utils  

    register_utils.rman_unregister_classes(classes)