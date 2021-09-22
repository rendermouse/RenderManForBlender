from .rman_ui_base import CollectionPanel
from ..rfb_utils.draw_utils import _draw_ui_from_rman_config
from ..rfb_utils import object_utils
from ..rfb_logger import rfb_log
from bpy.types import Panel
import bpy

class VOLUME_PT_renderman_openvdb_attributes(CollectionPanel, Panel):
    bl_context = "data"
    bl_label = "OpenVDB"

    @classmethod
    def poll(cls, context):
        if not context.volume:
            return False
        return CollectionPanel.poll(context)

    def draw(self, context):
        layout = self.layout
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False        
        volume = context.volume
        rm = volume.renderman

        layout.prop(rm, 'openvdb_velocity_grid_name')
        _draw_ui_from_rman_config('rman_properties_volume', 'VOLUME_PT_renderman_openvdb_attributes', context, layout, rm)             


classes = [
    VOLUME_PT_renderman_openvdb_attributes
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            rfb_log().debug('Could not unregister class: %s' % str(cls))
            pass      