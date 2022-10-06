from .rman_ui_base import PRManButtonsPanel 
from bpy.types import Panel
import bpy

class RENDER_PT_renderman_workspace(PRManButtonsPanel, Panel):
    bl_label = "Workspace"
    bl_context = "output"

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        if context.scene.render.engine != "PRMAN_RENDER":
            return

        layout = self.layout
        layout.prop(context.scene.renderman, 'root_path_output')
        layout.operator('scene.rman_open_workspace', text='Open Workspace')

classes = [
    RENDER_PT_renderman_workspace
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes) 

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)       