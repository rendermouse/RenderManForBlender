from .rman_ui_base import CollectionPanel
from ..rfb_utils.draw_utils import _draw_ui_from_rman_config
from ..rfb_utils import object_utils
from ..rfb_logger import rfb_log
from bpy.types import Panel
import bpy
import os
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

        #layout.operator('renderman.add_openvdb_to_txmanager')
        _draw_ui_from_rman_config('rman_properties_volume', 'VOLUME_PT_renderman_openvdb_attributes', context, layout, rm)             


classes = [
    VOLUME_PT_renderman_openvdb_attributes
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)   