from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, PointerProperty

from ...rfb_logger import rfb_log
from ...rman_config import RmanBasePropertyGroup

import bpy

class RendermanMaterialSettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    rman_config_name: StringProperty(name='rman_config_name',
                                    default='rman_properties_material') 

classes = [         
    RendermanMaterialSettings
]           

def register():

    from ...rfb_utils import register_utils

    for cls in classes:
        cls._add_properties(cls, 'rman_properties_material')
        register_utils.rman_register_class(cls)  

    bpy.types.Material.renderman = PointerProperty(
        type=RendermanMaterialSettings, name="Renderman Material Settings")

def unregister():

    del bpy.types.Material.renderman

    from ...rfb_utils import register_utils
    register_utils.rman_unregister_classes(classes)
