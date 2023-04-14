import bpy
from bpy.props import PointerProperty, StringProperty, BoolProperty, \
    IntProperty, CollectionProperty, EnumProperty, FloatProperty
from ..rman_properties_misc import RendermanMeshPrimVar     


class RendermanWorldSettings(bpy.types.PropertyGroup):

    use_renderman_node: BoolProperty(
        name="Use RenderMans World Node",
        description="Will enable RenderMan World Nodes, opening more options",
        default=False)

classes = [         
    RendermanWorldSettings
]           

def register():
    from ...rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

    bpy.types.World.renderman = PointerProperty(
        type=RendermanWorldSettings, name="Renderman World Settings")

def unregister():
    from ...rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)