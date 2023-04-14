from bpy.props import (StringProperty, BoolProperty, EnumProperty)

from ...rman_ui.rman_ui_base import CollectionPanel   
from ...rfb_logger import rfb_log
from ...rman_operators.rman_operators_collections import return_empty_list   
from ...rman_config import __RFB_CONFIG_DICT__ as rfb_config
from ...rfb_utils import scene_utils
import bpy
import re

class RENDERMAN_UL_Volume_Aggregates_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        custom_icon = 'OBJECT_DATAMODE'
        layout.context_pointer_set("selected_obj", item.ob_pointer)
        op = layout.operator('renderman.remove_from_vol_aggregate', text='', icon='REMOVE')     
        label = item.ob_pointer.name
        layout.label(text=label, icon=custom_icon) 

class PRMAN_OT_Renderman_Open_Volume_Aggregates_Editor(CollectionPanel, bpy.types.Operator):

    bl_idname = "scene.rman_open_vol_aggregates_editor"
    bl_label = "RenderMan Volume Aggregates Editor"
    bl_description = "Volume Aggregates Editor"

    def updated_object_selected_name(self, context):
        ob = context.scene.objects.get(self.selected_obj_name, None)
        if not ob:
            return
                
        if context.view_layer.objects.active:
            context.view_layer.objects.active.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob      

    def obj_list_items(self, context):
        pattern = re.compile(self.object_search_filter)        
        scene = context.scene
        rm = scene.renderman

        if self.do_object_filter and self.object_search_filter == '':
            return return_empty_list(label='No Objects Found')     

        group = rm.vol_aggregates[rm.vol_aggregates_index]
        objs_in_group = []
        for member in group.members:
            objs_in_group.append(member.ob_pointer.name)               

        items = []

        for ob in scene_utils.get_all_volume_objects(scene):
            ob_name = ob.name
            if ob_name not in objs_in_group:
                if self.do_object_filter and not re.match(pattern, ob_name):
                    continue
                items.append((ob_name, ob_name, ''))
            
        if not items:
            return return_empty_list(label='No Objects Found')               
        elif self.do_object_filter:
            items.insert(0, ('0', 'Results (%d)' % len(items), '', '', 0))
        else:
            items.insert(0, ('0', 'Select Object', '', '', 0))
        return items  

    def update_do_object_filter(self, context):
        self.selected_obj_name = '0'            

    do_object_filter: BoolProperty(name="Object Filter", 
                                description="Search and add multiple objects",
                                default=False,
                                update=update_do_object_filter)    
    object_search_filter: StringProperty(name="Object Filter Search", default="")       
    selected_obj_name: EnumProperty(name="", items=obj_list_items, update=updated_object_selected_name)       

    def execute(self, context):
        self.check_aggregates(context)
        return{'FINISHED'}         

    def draw(self, context):
        layout = self.layout
        scene = context.scene   
        rm = scene.renderman
        layout.separator()
        self._draw_collection(context, layout, rm, "Volume Aggregates",
                            "renderman.add_remove_volume_aggregates",
                            "scene.renderman",
                            "vol_aggregates", "vol_aggregates_index",
                            default_name='VolumeAggreagte_%d' % len(rm.vol_aggregates))          

    def draw_objects_item(self, layout, context, item):
        row = layout.row()
        scene = context.scene
        rm = scene.renderman
        vol_aggregate = rm.vol_aggregates[rm.vol_aggregates_index]

        row = layout.row()
        row.separator()   

        row.prop(self, 'do_object_filter', text='', icon='FILTER', icon_only=True)
        if not self.do_object_filter:
            row.prop(self, 'selected_obj_name', text='')
            col = row.column()
            if self.selected_obj_name == '0' or self.selected_obj_name == '':
                col.enabled = False
                op = col.operator("renderman.add_to_vol_aggregate", text='', icon='ADD')
                op.open_editor = False
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_obj', scene.objects[self.selected_obj_name])
                op = col.operator("renderman.add_to_vol_aggregate", text='', icon='ADD')
                op.vol_aggregates_index = rm.vol_aggregates_index    
                op.do_scene_selected = False
                op.open_editor = False
        else:
            row.prop(self, 'object_search_filter', text='', icon='VIEWZOOM')
            row = layout.row()  
            row.prop(self, 'selected_obj_name')
            col = row.column()
            if self.selected_obj_name == '0' or self.selected_obj_name == '':
                col.enabled = False
                op = col.operator("renderman.add_to_vol_aggregate", text='', icon='ADD')
                op.open_editor = False
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_obj', scene.objects[self.selected_obj_name])                
                op = col.operator("renderman.add_to_vol_aggregate", text='', icon='ADD')
                op.vol_aggregates_index = rm.vol_aggregates_index
                op.do_scene_selected = False
                op.open_editor = False

        row = layout.row()
        
        row.template_list('RENDERMAN_UL_Volume_Aggregates_List', "",
                        vol_aggregate, "members", vol_aggregate, 'members_index', rows=6)        

    def draw_item(self, layout, context, item):
        self.draw_objects_item(layout, context, item)

    def cancel(self, context):
        if self.event and self.event.type == 'LEFTMOUSE':
            bpy.ops.scene.rman_open_vol_aggregates_editor('INVOKE_DEFAULT')
        else:
            self.check_aggregates(context)
            
    def __init__(self):
        self.event = None      

    def check_aggregates(self, context):
        scene = context.scene
        rm = scene.renderman
        
        for lg in rm.vol_aggregates:
            delete_objs = []
            for j in range(len(lg.members)-1, -1, -1):
                member = lg.members[j]
                if member.ob_pointer is None or member.ob_pointer.name not in scene.objects:
                    delete_objs.insert(0, j)
            for j in delete_objs:
                lg.members.remove(j)
                lg.members_index -= 1              

    def invoke(self, context, event):

        wm = context.window_manager
        width = rfb_config['editor_preferences']['vol_aggregates_editor']['width']
        self.event = event
        self.check_aggregates(context)
        return wm.invoke_props_dialog(self, width=width) 

classes = [    
    PRMAN_OT_Renderman_Open_Volume_Aggregates_Editor,
    RENDERMAN_UL_Volume_Aggregates_List
]

def register():
    from ...rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

def unregister():
    from ...rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)                         