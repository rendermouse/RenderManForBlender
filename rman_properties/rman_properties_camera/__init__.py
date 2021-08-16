import bpy
from bpy.props import PointerProperty, BoolProperty, \
    EnumProperty, FloatProperty, StringProperty
from ... import rman_config
from ...rman_config import RmanBasePropertyGroup
from ...rfb_logger import rfb_log

class RendermanCameraSettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    bl_label = "RenderMan Camera Settings"
    bl_idname = 'RendermanCameraSettings'

    rman_config_name: StringProperty(name='rman_config_name',
                                    default='rman_properties_camera')    

    rman_nodetree: PointerProperty(
        name="NodeTree",
        type=bpy.types.ShaderNodeTree
    )

    rman_use_cam_fov: BoolProperty(
        name="Use Camera FOV",
        default=True,
        description="When using a projection plugin, copy the FOV settings from the camera object, effectively ignoring any FOV params on the projection plugin."
    )

    def validate_shift_object(self, ob):
        if ob.type == 'MESH':
            return True
        return False

    rman_tilt_shift_object: PointerProperty(
        name="Tilt-Shift Object Focus",
        type=bpy.types.Object,
        poll=validate_shift_object,
        description="Select an object to represent the tilt-shift focus points. Must be a triangle. If an object is selected, Focus 1, Focus 2, and Focus 3 values are ignored."
    )    

classes = [
    RendermanCameraSettings,
]

def register():
    for cls in classes:
        cls._add_properties(cls, 'rman_properties_camera')
        bpy.utils.register_class(cls)

    bpy.types.Camera.renderman = PointerProperty(
        type=RendermanCameraSettings, name="Renderman Camera Settings")  
   
def unregister():

    del bpy.types.Camera.renderman

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            rfb_log().debug('Could not unregister class: %s' % str(cls))
            pass     