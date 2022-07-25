from bpy.props import (StringProperty, BoolProperty, EnumProperty)

from ...rman_ui.rman_ui_base import CollectionPanel   
from ...rfb_utils import scene_utils
from ...rfb_utils import shadergraph_utils
from ...rfb_logger import rfb_log
from ... import rfb_icons
from ...rman_operators.rman_operators_collections import return_empty_list   
from ...rman_config import __RFB_CONFIG_DICT__ as rfb_config
import bpy
import re

class RENDERMAN_UL_LightMixer_Group_Members_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        rm = context.scene.renderman
        light = item.light_ob
        layout.context_pointer_set("selected_light", light)        
        op = layout.operator('renderman.remove_light_from_light_mixer_group', text='', icon='REMOVE')
   
        light_shader = shadergraph_utils.get_light_node(light)
        if not light_shader:
            layout.label(text=light.name)
            layout.label(text='NO LIGHT SHADER')
            return 

        icon = rfb_icons.get_light_icon(light_shader.bl_label)
        op.group_index = rm.light_mixer_groups_index
        layout.label(text=light.name, icon_value=icon.icon_id)

        light_rm = shadergraph_utils.get_rman_light_properties_group(light)
        if light_shader.bl_label == 'PxrPortalLight':
            layout.prop(light_shader, 'enableTemperature', text='Temp')
            if light_shader.enableTemperature:
                layout.prop(light_shader, 'temperature', text='', slider=True)
            else:
                layout.prop(light_shader, 'tint', text='')        
            layout.prop(light_shader, 'intensityMult', slider=True)                
        else:
            if light_shader.bl_label == 'PxrEnvDayLight':
                layout.prop(light_shader, 'skyTint', text='')
            else:
                layout.prop(light_shader, 'enableTemperature', text='Temp')
                if light_shader.enableTemperature:
                    layout.prop(light_shader, 'temperature', text='', slider=True)
                else:
                    layout.prop(light_shader, 'lightColor', text='')
            layout.prop(light_shader, 'intensity', slider=True)
            layout.prop(light_shader, 'exposure', slider=True)        
        solo_icon = 'LIGHT'        
        if light.renderman.solo:
            solo_icon = 'OUTLINER_OB_LIGHT'
        layout.prop(light.renderman, 'solo', text='', icon=solo_icon, icon_only=True, emboss=False )
        mute_icon = 'HIDE_OFF'
        if light.renderman.mute:
            mute_icon = 'HIDE_ON'
        layout.prop(light.renderman, 'mute', text='', icon=mute_icon, icon_only=True, emboss=False)

class PRMAN_OT_Renderman_Open_Light_Mixer_Editor(CollectionPanel, bpy.types.Operator):

    bl_idname = "scene.rman_open_light_mixer_editor"
    bl_label = "RenderMan Light Mixer Editor"

    def updated_light_selected_name(self, context):
        light_ob = context.scene.objects.get(self.selected_light_name, None)
        if not light_ob:
            return
                
        if context.view_layer.objects.active:
            context.view_layer.objects.active.select_set(False)
        light_ob.select_set(True)
        context.view_layer.objects.active = light_ob   

    def light_list_items(self, context):
        pattern = re.compile(self.light_search_filter)   
        scene = context.scene
        rm = scene.renderman

        if self.do_light_filter and self.light_search_filter == '':
            return return_empty_list(label='No Lights Found')

        group_index = rm.light_mixer_groups_index
        lights_in_group = []
        object_groups = rm.light_mixer_groups
        object_group = object_groups[group_index]
        lights_in_group = [member.light_ob.name for member in object_group.members]        

        items = []
        for light in scene_utils.get_all_lights(context.scene, include_light_filters=False):
            if light.name not in lights_in_group:
                if self.do_light_filter and not re.match(pattern, light.name):
                    continue
                items.append((light.name, light.name, ''))
        if not items:
            return return_empty_list(label='No Lights Found') 
        elif self.do_light_filter:
            items.insert(0, ('0', 'Results (%d)' % len(items), '', '', 0))
        else:
            items.insert(0, ('0', 'Select Light', '', '', 0))                  
        return items

    def update_do_light_filter(self, context):
        self.selected_light_name = '0'

    selected_light_name: EnumProperty(name="Light", items=light_list_items, update=updated_light_selected_name)
    light_search_filter: StringProperty(name="Light Filter Search", default="")
    do_light_filter: BoolProperty(name="Filter", 
                                description="Search and add multiple lights",
                                default=False,
                                update=update_do_light_filter)    

    def check_light_mixer_links(self, context):
        scene = context.scene
        rm = scene.renderman
        
        for lg in rm.light_mixer_groups:
            delete_objs = []
            for j in range(len(lg.members)-1, -1, -1):
                member = lg.members[j]
                if member.light_ob is None or member.light_ob.name not in scene.objects:
                    delete_objs.insert(0, j)
            for j in delete_objs:
                lg.members.remove(j)
                lg.members_index -= 1                             

    def execute(self, context):
        self.check_light_mixer_links(context)
        return{'FINISHED'}         

    def cancel(self, context):
        if self.event and self.event.type == 'LEFTMOUSE':
            bpy.ops.scene.rman_open_light_mixer_editor('INVOKE_DEFAULT')
        else:
            self.check_light_mixer_links(context)
            
    def __init__(self):
        self.event = None         

    def invoke(self, context, event):

        wm = context.window_manager
        width = rfb_config['editor_preferences']['lightmixer_editor']['width']
        self.event = event
        self.check_light_mixer_links(context)
        return wm.invoke_props_dialog(self, width=width)         

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        self._draw_collection(context, layout, rm, "Light Mixer Groups",
                              "collection.add_remove",
                              "scene.renderman",
                              "light_mixer_groups", "light_mixer_groups_index", 
                              default_name='mixerGroup_%d' % len(rm.light_mixer_groups))

    def draw_item(self, layout, context, item):
        scene = context.scene
        rm = scene.renderman
        light_group = rm.light_mixer_groups[rm.light_mixer_groups_index]

        lights = [member.light_ob for member in light_group.members]
        row = layout.row(align=True)
        row.separator()        

        box = layout.box()
        row = box.row()
        split = row.split(factor=0.25)
        row = split.row()
        row.prop(self, 'do_light_filter', text='', icon='FILTER', icon_only=True)
        if not self.do_light_filter:
            row.prop(self, 'selected_light_name', text='')
            col = row.column()            
            if self.selected_light_name == '0' or self.selected_light_name == '':
                col.enabled = False
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
                op.open_editor = False
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_light', bpy.data.objects[self.selected_light_name])
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
                op.do_scene_selected = False
                op.open_editor = False
        else:
            row.prop(self, 'light_search_filter', text='', icon='VIEWZOOM')
            row = box.row()
            split = row.split(factor=0.25)
            row = split.row()
            row.prop(self, 'selected_light_name', text='')
            col = row.column()
            if self.selected_light_name == '0' or self.selected_light_name == '':
                col.enabled = False
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
                op.open_editor = False
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_light', bpy.data.objects[self.selected_light_name])
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
                op.do_scene_selected = False
                op.open_editor = False
        row = layout.row()
        split = row.split(factor=0.25)
        op = split.operator('renderman.convert_mixer_group_to_light_group', text='Convert to Light Group')
        op.group_index = rm.light_mixer_groups_index

        layout.template_list("RENDERMAN_UL_LightMixer_Group_Members_List", "Renderman_light_mixer_list",
                            light_group, "members", light_group, 'members_index', rows=6)

classes = [
    PRMAN_OT_Renderman_Open_Light_Mixer_Editor, 
    RENDERMAN_UL_LightMixer_Group_Members_List
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