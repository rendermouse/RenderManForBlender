from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from ..rfb_utils import string_utils
from ..rfb_logger import rfb_log
from ..rfb_utils import texture_utils
from ..rfb_utils import object_utils
from ..rfb_utils.scene_utils import RMAN_VOL_TYPES
import bpy

class COLLECTION_OT_volume_aggregates_add_remove(bpy.types.Operator):
    bl_label = "Add or Remove Volume Aggregates"
    bl_idname = "renderman.add_remove_volume_aggregates"

    action: EnumProperty(
        name="Action",
        description="Either add or remove properties",
        items=[('ADD', 'Add', ''),
               ('REMOVE', 'Remove', '')],
        default='ADD')
    context: StringProperty(
        name="Context",
        description="Name of context member to find renderman pointer in",
        default="")
    collection: StringProperty(
        name="Collection",
        description="The collection to manipulate",
        default="")
    collection_index: StringProperty(
        name="Index Property",
        description="The property used as a collection index",
        default="")
    defaultname: StringProperty(
        name="Default Name",
        description="Default name to give this collection item",
        default="")

    @classmethod
    def description(cls, context, properties):    
        description = "Add a new volume aggregate group"
        if properties.action == "REMOVE":
            description = "Remove the selected volume aggregate group"
        return description

    def invoke(self, context, event):
        scene = context.scene
        id = string_utils.getattr_recursive(context, self.properties.context)
        rm = id.renderman if hasattr(id, 'renderman') else id

        prop_coll = self.properties.collection
        coll_idx = self.properties.collection_index

        collection = getattr(rm, prop_coll)
        index = getattr(rm, coll_idx)

        if self.properties.action == 'ADD':
            dflt_name = self.properties.defaultname
            for coll in collection:
                if coll.name == dflt_name:
                    dflt_name = '%s_NEW' % dflt_name
            collection.add()
            index += 1
            setattr(rm, coll_idx, index)
            collection[-1].name = dflt_name

        elif self.properties.action == 'REMOVE':
            group = collection[index]            
            # get a list of all objects in this group
            ob_list = [member.ob_pointer for member in group.members]
            collection.remove(index)
            setattr(rm, coll_idx, index - 1)

            # now tell each object to update
            for ob in ob_list:
                ob.update_tag(refresh={'OBJECT'})

        return {'FINISHED'}                        

class PRMAN_OT_add_to_vol_aggregate(bpy.types.Operator):
    bl_idname = 'renderman.add_to_vol_aggregate'
    bl_label = 'Add Selected to Volume Aggregate'

    vol_aggregates_index: IntProperty(default=-1)
    do_scene_selected: BoolProperty(name="do_scene_selected", default=False)
    open_editor: BoolProperty(default=False)

    def add_selected(self, context):
        scene = context.scene
        rm = scene.renderman
        vol_aggregates_index = rm.vol_aggregates_index
        ob = getattr(context, "selected_obj", None)
        if not ob:
            return {'FINISHED'}       

        vol_aggregates = scene.renderman.vol_aggregates
        vol_aggregate = vol_aggregates[vol_aggregates_index]
        do_add = True
        for member in vol_aggregate.members:            
            if ob == member.ob_pointer:
                do_add = False
                break
        if do_add:
            ob_in_group = vol_aggregate.members.add()
            ob_in_group.name = ob.name
            ob_in_group.ob_pointer = ob    
            op = getattr(context, 'op_ptr')
            if op:
                op.selected_obj_name = '0'             
            ob.update_tag(refresh={'DATA'})    

    def add_scene_selected(self, context):
        scene = context.scene
        rm = scene.renderman
        if not hasattr(context, 'selected_objects'):
            return {'FINISHED'}

        vol_aggregates_index = self.properties.vol_aggregates_index
        vol_aggregates = scene.renderman.vol_aggregates
        vol_aggregate = vol_aggregates[vol_aggregates_index]
        for ob in context.selected_objects:
            if object_utils._detect_primitive_(ob) not in RMAN_VOL_TYPES:
                continue
            do_add = True
            for member in vol_aggregate.members:            
                if ob == member.ob_pointer:
                    do_add = False
                    break
            if do_add:
                ob_in_group = vol_aggregate.members.add()
                ob_in_group.name = ob.name
                ob_in_group.ob_pointer = ob    
                ob.update_tag(refresh={'DATA'})          

    def execute(self, context):
        if self.properties.do_scene_selected:
            self.add_scene_selected(context)
        else:
            self.add_selected(context)

        if self.properties.open_editor:
            bpy.ops.scene.rman_open_vol_aggregates_editor('INVOKE_DEFAULT')            
        
        return {'FINISHED'}

class PRMAN_OT_remove_from_vol_aggregate(bpy.types.Operator):
    bl_idname = 'renderman.remove_from_vol_aggregate'
    bl_label = 'Remove Selected from Volume Aggregate'

    def execute(self, context):
        scene = context.scene
        rm = scene.renderman        
        vol_aggregates_index = rm.vol_aggregates_index
        ob = getattr(context, "selected_obj", None)
        if not ob:
            return {'FINISHED'}        

        vol_aggregates = scene.renderman.vol_aggregates
        vol_aggregate = vol_aggregates[vol_aggregates_index]
        for i, member in enumerate(vol_aggregate.members):
            if member.ob_pointer == ob:
                vol_aggregate.members.remove(i)
                ob.update_tag(refresh={'OBJECT'})
                break

        return {'FINISHED'}        

class PRMAN_OT_add_vdb_to_txmanager(bpy.types.Operator):
    bl_idname = 'renderman.add_openvdb_to_txmanager'
    bl_label = 'Add to Texture Manager'
    bl_description = 'Add the current OpenVDB to the texture manager to be mipmapped.'
     
    @classmethod
    def poll(cls, context):
        if not context.volume:
            return False
        rm = context.volume.renderman
        vol = context.volume
        ob = context.object
        txfile = texture_utils.get_txmanager().get_txfile_for_vdb(ob)
        if txfile:
            grids = vol.grids
            grids.load()
            openvdb_file = string_utils.get_tokenized_openvdb_file(grids.frame_filepath, grids.frame)
            if txfile.input_image != openvdb_file:
                return True
        return False

    def execute(self, context):
        ob = context.object
        texture_utils.add_openvdb(ob)

        return {'FINISHED'}                            

classes = [
    COLLECTION_OT_volume_aggregates_add_remove,
    PRMAN_OT_add_to_vol_aggregate,
    PRMAN_OT_remove_from_vol_aggregate,
    PRMAN_OT_add_vdb_to_txmanager
]

def register():
    from ..rfb_utils import register_utils

    register_utils.rman_register_classes(classes)

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)