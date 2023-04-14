from ..rfb_logger import rfb_log
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty
import bpy

class PRMAN_OT_Renderman_printer(Operator):
    """An operator to simply print messages."""

    bl_idname = "renderman.printer"
    bl_label = "RenderMan Message"
    bl_options = {'INTERNAL'}

    message: StringProperty()
    
    level: EnumProperty(
        name="level",
        items=[
            ('INFO', 'INFO', ''),
            ('ERROR', 'ERROR', ''),
            ('DEBUG', 'DEBUG', ''),
            ('WARNING', 'WARNING', '')
        ]
    )

    @classmethod
    def poll(cls, context):
        if hasattr(context, 'window_manager'):
            return True
        return False


    def draw(self, context):
        layout = self.layout
        col = layout.column()
        rman_icon = 'ERROR'
        if self.level == 'INFO':
            rman_icon = 'INFO'

        col.label(text='%s' % self.message, icon=rman_icon)  

    def execute(self, context): 
        #self.report({'ERROR'}, '%s' % self.message ) 
        return{'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        width = len(self.properties.message) * 10
        return wm.invoke_props_dialog(self, width=width)

classes = [
   PRMAN_OT_Renderman_printer 
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)