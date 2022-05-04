# utils
from .rfb_utils import object_utils
from .rfb_utils import texture_utils
from .rfb_utils import scene_utils
from .rfb_utils.timer_utils import time_this
from .rfb_utils import string_utils

from .rfb_logger import rfb_log
from .rman_sg_nodes.rman_sg_lightfilter import RmanSgLightFilter

from . import rman_constants
import bpy

class RmanUpdate:
    def __init__(self):
        self.is_updated_geometry = False
        self.is_updated_transform = False
        self.is_updated_shading = False
        self.is_updated_lightfilters = False

class RmanSceneSync(object):
    '''
    The RmanSceneSync class handles keeping the RmanScene object in sync
    during IPR. 

    Attributes:
        rman_render (RmanRender) - pointer back to the current RmanRender object
        rman () - rman python module
        rman_scene (RmanScene) - pointer to the current RmanScene object
        sg_scene (RixSGSCene) - the RenderMan scene graph object

    '''

    def __init__(self, rman_render=None, rman_scene=None, sg_scene=None):
        self.rman_render = rman_render
        self.rman = rman_render.rman
        self.rman_scene = rman_scene
        self.sg_scene = sg_scene        
        self.num_instances_changed = False # if the number of instances has changed since the last update
        self.frame_number_changed = False
        self.check_all_instances = False # force checking all instances

        self.rman_updates = dict() # A dicitonary to hold RmanUpdate instances

    @property
    def sg_scene(self):
        return self.__sg_scene

    @sg_scene.setter
    def sg_scene(self, sg_scene):
        self.__sg_scene = sg_scene          

    def update_view(self, context, depsgraph):
        camera = depsgraph.scene.camera
        self.rman_scene.context = context
        self.rman_scene.depsgraph = depsgraph
        self.rman_scene.bl_scene = depsgraph.scene_eval
        rman_sg_camera = self.rman_scene.main_camera
        translator = self.rman_scene.rman_translators['CAMERA']
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            if self.rman_scene.is_viewport_render:
                ob = translator.update_viewport_resolution(rman_sg_camera)
                if ob:
                    translator.update_viewport_cam(ob, rman_sg_camera, force_update=True)
                translator.update_transform(None, rman_sg_camera)
            else:
                translator.update_transform(camera, rman_sg_camera)  

    @time_this
    def scene_updated(self):
        # Check visible objects
        visible_objects = self.rman_scene.context.visible_objects
        if not self.num_instances_changed:
            if len(visible_objects) != self.rman_scene.num_objects_in_viewlayer:
                rfb_log().debug("\tNumber of visible objects changed: %d -> %d" % (self.rman_scene.num_objects_in_viewlayer, len(visible_objects)))
                # The number of visible objects has changed.
                # Figure out the difference using sets
                set1 = set(self.rman_scene.objects_in_viewlayer)
                set2 =  set(visible_objects)
                set_diff1 = set1.difference(set2)
                set_diff2 = set2.difference(set1)

                objects = list(set_diff1.union(set_diff2))           
                for o in list(objects):
                    try:
                        if o.original not in self.rman_updates:
                            rman_update = RmanUpdate()
                            rman_update.is_updated_shading = True
                            rman_update.is_updated_transform = True
                            self.rman_updates[o.original] = rman_update
                    except:
                        continue
                #self.check_all_instances = True

        self.rman_scene.num_objects_in_viewlayer = len(visible_objects)
        self.rman_scene.objects_in_viewlayer = [o for o in visible_objects]            

        if self.rman_scene.bl_frame_current != self.rman_scene.bl_scene.frame_current:
            # frame changed, update any materials and objects that 
            # are marked as frame sensitive
            rfb_log().debug("Frame changed: %d -> %d" % (self.rman_scene.bl_frame_current, self.rman_scene.bl_scene.frame_current))
            self.rman_scene.bl_frame_current = self.rman_scene.bl_scene.frame_current
            string_utils.update_frame_token(self.rman_scene.bl_frame_current)
            self.frame_number_changed = True

            # check for frame sensitive objects
            for id in self.rman_scene.depsgraph.ids:
                if isinstance(id, bpy.types.Object):
                    o = id.original
                    if o.type == 'CAMERA':
                        rman_sg_node = self.rman_scene.rman_cameras.get(o.original, None)
                    else:
                        rman_sg_node = self.rman_scene.get_rman_prototype(object_utils.prototype_key(o), create=False)
                    if rman_sg_node and rman_sg_node.is_frame_sensitive:
                        if o.original not in self.rman_updates:
                            o.original.update_tag()
                elif isinstance(id, bpy.types.Material):
                    mat = id.original               
                    rman_sg_material = self.rman_scene.rman_materials.get(mat, None)
                    if rman_sg_material and rman_sg_material.is_frame_sensitive:
                        mat.node_tree.update_tag()                    

            with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):  
                # update frame number
                options = self.rman_scene.sg_scene.GetOptions()
                options.SetInteger(self.rman.Tokens.Rix.k_Ri_Frame, self.rman_scene.bl_frame_current)
                self.rman_scene.sg_scene.SetOptions(options)        

    def _mesh_light_update(self, mat):
        object_list = list()
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            for ob_inst in self.rman_scene.depsgraph.object_instances:                
                ob = ob_inst.object.evaluated_get(self.rman_scene.depsgraph)
                if not hasattr(ob.data, 'materials'):
                    continue   
                if ob.type in ('ARMATURE', 'CURVE', 'CAMERA'):
                    continue  
                proto_key = object_utils.prototype_key(ob_inst)                        
                rman_sg_node = self.rman_scene.get_rman_prototype(proto_key)
                if rman_sg_node:
                    found = False
                    for name, material in ob.data.materials.items():
                        if name == mat.name:
                            found = True

                    if found:
                        del self.rman_scene.rman_prototypes[proto_key]
                        if ob not in object_list:
                            object_list.append(ob)

        for ob in object_list:
            ob.update_tag()

    def material_updated(self, obj):
        mat = obj.id
        rman_sg_material = self.rman_scene.rman_materials.get(mat.original, None)
        translator = self.rman_scene.rman_translators["MATERIAL"]         
        db_name = object_utils.get_db_name(mat)
        if not rman_sg_material:
            # Double check if we can't find the material because of an undo
            rman_sg_material = self.update_materials_dict(mat)

        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):   
            mat = obj.id              
            if not rman_sg_material:
                rfb_log().debug("New material: %s" % mat.name)
                db_name = object_utils.get_db_name(mat)
                rman_sg_material = translator.export(mat, db_name)
                self.rman_scene.rman_materials[mat.original] = rman_sg_material            
            else:
                rfb_log().debug("Material, call update")
                translator.update(mat, rman_sg_material)   

        # update db_name
        rman_sg_material.db_name = db_name

    def light_filter_transform_updated(self, obj):
        ob = obj.id.evaluated_get(self.rman_scene.depsgraph)
        proto_key = object_utils.prototype_key(ob)
        rman_sg_lightfilter = self.rman_scene.get_rman_prototype(proto_key)
        if rman_sg_lightfilter:
            rman_group_translator = self.rman_scene.rman_translators['GROUP']  
            with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):              
                rman_group_translator.update_transform(ob, rman_sg_lightfilter)

    def light_filter_updated(self, obj):
        ob = obj.id.evaluated_get(self.rman_scene.depsgraph)
        proto_key = object_utils.prototype_key(ob)
        rman_sg_node = self.rman_scene.get_rman_prototype(proto_key)
        if not rman_sg_node:
            # Light filter needs to be added
            rman_update = RmanUpdate()
            rman_update.is_updated_geometry = obj.is_updated_geometry
            rman_update.is_updated_shading = obj.is_updated_shading
            rman_update.is_updated_transform = obj.is_updated_transform
            self.rman_updates[ob.original] = rman_update               
            return
        if obj.is_updated_transform or obj.is_updated_shading:
            rfb_log().debug("\tLight Filter: %s Transform Updated" % obj.id.name)
            self.light_filter_transform_updated(obj)
        if obj.is_updated_geometry:
            rfb_log().debug("\tLight Filter: %s Shading Updated" % obj.id.name)
            with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):                
                self.rman_scene.rman_translators['LIGHTFILTER'].update(ob, rman_sg_node)
                for light_ob in rman_sg_node.lights_list:
                    if isinstance(light_ob, bpy.types.Material):
                        light_ob.node_tree.update_tag()
                    else:
                        light_ob.update_tag()

    def camera_updated(self, ob_update):
        ob = ob_update.id.evaluated_get(self.rman_scene.depsgraph)
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            rman_sg_camera = self.rman_scene.rman_cameras.get(ob.original)
            translator = self.rman_scene.rman_translators['CAMERA']

            if not rman_sg_camera:
                rfb_log().debug("\tNew Camera: %s" % ob.name)
                db_name = object_utils.get_db_name(ob)
                rman_sg_camera = translator._export_render_cam(ob, db_name)
                self.rman_scene.rman_cameras[ob.original] = rman_sg_camera           
                        
                self.rman_scene.sg_scene.Root().AddChild(rman_sg_camera.sg_node)
                self.rman_scene.sg_scene.Root().AddCoordinateSystem(rman_sg_camera.sg_node)
                return

            if ob_update.is_updated_geometry:
                rfb_log().debug("\tUpdated Camera: %s" % ob.name)
                if not self.rman_scene.is_viewport_render:
                    translator.update(ob, rman_sg_camera)  
                else:
                    translator.update_viewport_cam(ob, rman_sg_camera, force_update=True)              

            if ob_update.is_updated_transform:
                # we deal with main camera transforms in view_draw
                if rman_sg_camera == self.rman_scene.main_camera:
                    return
                if translator._update_render_cam_transform(ob, rman_sg_camera):
                    rfb_log().debug("\tCamera Transform Updated: %s" % ob.name)
              

    def check_particle_instancer(self, ob_update, psys):
        # this particle system is a instancer
        inst_ob = getattr(psys.settings, 'instance_object', None) 
        collection = getattr(psys.settings, 'instance_collection', None)
        if inst_ob:
            if inst_ob.original not in self.rman_updates:
                rman_update = RmanUpdate()                
                rman_update.is_updated_shading = ob_update.is_updated_shading
                rman_update.is_updated_transform = ob_update.is_updated_transform
                self.rman_updates[inst_ob.original] = rman_update         
        elif collection:
            for col_obj in collection.all_objects:
                if not col_obj.original.data:
                    continue
                if col_obj.original in self.rman_updates:
                    continue
                rman_update = RmanUpdate()
                rman_update.is_updated_shading = ob_update.is_updated_shading
                rman_update.is_updated_transform = ob_update.is_updated_transform
                self.rman_updates[col_obj.original] = rman_update                      

    def update_particle_emitter(self, ob, psys):
        psys_translator = self.rman_scene.rman_translators['PARTICLES']
        proto_key = object_utils.prototype_key(ob)
        rman_sg_particles = self.rman_scene.get_rman_particles(proto_key, psys, ob)
        psys_translator.update(ob, psys, rman_sg_particles)

    def update_particle_emitters(self, ob):
        for psys in ob.particle_systems:
            if not object_utils.is_particle_instancer(psys):
                self.update_particle_emitter(ob, psys)
                            
    def update_empty(self, ob_update, rman_sg_node=None):
        ob = ob_update.id
        rfb_log().debug("Update empty: %s" % ob.name)
        if ob.is_instancer:
            rfb_log().debug("\tEmpty is an instancer")
            collection = ob.instance_collection
            if collection:
                for col_obj in collection.all_objects:
                    if not col_obj.original.data:
                        continue
                    if col_obj.original in self.rman_updates:
                        continue
                    rman_update = RmanUpdate()
                    rman_update.is_updated_geometry = ob_update.is_updated_geometry
                    rman_update.is_updated_shading = ob_update.is_updated_shading
                    rman_update.is_updated_transform = ob_update.is_updated_transform
                    self.rman_updates[col_obj.original] = rman_update
        else:
            rfb_log().debug("\tRegular empty")
            proto_key = object_utils.prototype_key(ob)
            rman_sg_node = self.rman_scene.get_rman_prototype(proto_key)
            if not rman_sg_node:
                return
            translator = self.rman_scene.rman_translators['EMPTY']              
            with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
                translator.export_transform(ob, rman_sg_node.sg_node)
                translator.export_object_attributes(ob, rman_sg_node)  
                self.rman_scene.attach_material(ob, rman_sg_node)                   
                if ob.renderman.export_as_coordsys:
                    self.rman_scene.get_root_sg_node().AddCoordinateSystem(rman_sg_node.sg_node)
                else:
                    self.rman_scene.get_root_sg_node().RemoveCoordinateSystem(rman_sg_node.sg_node)              
 
    def update_materials_dict(self, mat):    
        # Try to see if we already have a material with the same db_name
        # We need to do this because undo/redo causes all bpy.types.ID 
        # references to be invalidated (see: https://docs.blender.org/api/current/info_gotcha.html)
        # We don't want to accidentally mistake this for a new object, so we need to update
        # our materials dictionary with the new bpy.types.ID reference
        rman_sg_material = None
        for id, rman_sg_node in self.rman_scene.rman_materials.items():
            if rman_sg_node:
                db_name = object_utils.get_db_name(mat)
                if rman_sg_node.db_name == db_name:
                    self.rman_scene.rman_materials[mat.original] = rman_sg_node
                    del self.rman_scene.rman_materials[id]
                    rman_sg_material = rman_sg_node 
                    break
        
        return rman_sg_material

    def update_collection(self, coll):
        # mark all objects in a collection
        # as needing their instances updated
        for o in coll.all_objects:
            if o.type in ('ARMATURE', 'CAMERA'):
                continue
            if o.original not in self.rman_updates:
                rman_update = RmanUpdate()
                rman_update.is_updated_shading = True
                rman_update.is_updated_transform = True
                self.rman_updates[o.original] = rman_update            

    def update_portals(self, ob):
        for portal in scene_utils.get_all_portals(ob):
           portal.original.update_tag()

    def batch_update_scene(self, context, depsgraph):
        self.rman_scene.bl_frame_current = self.rman_scene.bl_scene.frame_current
        string_utils.update_frame_token(self.rman_scene.bl_frame_current)

        self.rman_updates = dict()
        self.num_instances_changed = False
        self.check_all_instances = False

        self.rman_scene.bl_scene = depsgraph.scene_eval
        self.rman_scene.context = context     

        options = self.rman_scene.sg_scene.GetOptions()
        options.SetInteger(self.rman.Tokens.Rix.k_Ri_Frame, self.rman_scene.bl_frame_current) 
        self.rman_scene.sg_scene.SetOptions(options)     

        # Check the number of instances. If we differ, an object may have been
        # added or deleted
        if self.rman_scene.num_object_instances != len(depsgraph.object_instances):
            rfb_log().debug("\tNumber of instances changed: %d -> %d" % (self.rman_scene.num_object_instances, len(depsgraph.object_instances)))
            self.num_instances_changed = True
            self.rman_scene.num_object_instances = len(depsgraph.object_instances)

        for obj in reversed(depsgraph.updates):
            ob = obj.id

            if isinstance(obj.id, bpy.types.ParticleSettings):
                rfb_log().debug("ParticleSettings updated: %s" % obj.id.name)
                for o in self.rman_scene.bl_scene.objects:
                    psys = None
                    ob = o.evaluated_get(depsgraph)
                    for ps in ob.particle_systems:
                        if ps.settings.original == obj.id.original:
                            psys = ps
                            break
                    if not psys:
                        continue
                    if object_utils.is_particle_instancer(psys):
                        #self.check_particle_instancer(obj, psys)
                        pass
                    else:
                        self.update_particle_emitter(ob, psys)

                    if o.original not in self.rman_updates:
                        rman_update = RmanUpdate()

                        rman_update.is_updated_geometry = obj.is_updated_geometry
                        rman_update.is_updated_shading = obj.is_updated_shading
                        rman_update.is_updated_transform = obj.is_updated_transform   
                        self.rman_updates[o.original] = rman_update                         

            elif isinstance(obj.id, bpy.types.Object):                
                ob_eval = obj.id.evaluated_get(depsgraph)
                rman_type = object_utils._detect_primitive_(ob_eval)

                if ob.type in ('ARMATURE'):
                    continue
                
                # These types need special handling              
                if rman_type == 'EMPTY':
                    self.update_empty(obj)   
                    continue 
                if rman_type == 'LIGHTFILTER':
                    rfb_log().debug("Light filter: %s updated" % obj.id.name)
                    ob_eval = obj.id.evaluated_get(self.rman_scene.depsgraph)
                    proto_key = object_utils.prototype_key(ob_eval)
                    rman_sg_lightfilter = self.rman_scene.get_rman_prototype(proto_key)
                    if not rman_sg_lightfilter:
                        continue
                    if obj.is_updated_geometry:            
                        self.rman_scene.rman_translators['LIGHTFILTER'].update(ob_eval, rman_sg_lightfilter)
                        for light_ob in rman_sg_lightfilter.lights_list:
                            if isinstance(light_ob, bpy.types.Material):
                                ob_key = light_ob.original
                            else:
                                ob_key = object_utils.prototype_key(light_ob)
                            rman_update = self.rman_updates.get(ob_key, None)
                            if not rman_update:                  
                                rman_update = RmanUpdate()
                                rman_update.is_updated_shading = True
                                rman_update.is_updated_transform = True
                                self.rman_updates[ob_key] = rman_update                       
                    if obj.is_updated_transform:
                        rman_group_translator = self.rman_scene.rman_translators['GROUP']             
                        rman_group_translator.update_transform(ob_eval, rman_sg_lightfilter)
   
                if rman_type == 'CAMERA':
                    rfb_log().debug("Camera: %s updated" % obj.id.name)
                    cam_translator = self.rman_scene.rman_translators['CAMERA']
                    rman_sg_camera = self.rman_scene.rman_cameras.get(ob_eval.original)
                    if obj.is_updated_geometry:
                        cam_translator.update(ob_eval, rman_sg_camera)  
                    if obj.is_updated_transform:
                        cam_translator._update_render_cam_transform(ob_eval, rman_sg_camera)
                    continue  

                rman_update = RmanUpdate()

                rman_update.is_updated_geometry = obj.is_updated_geometry
                rman_update.is_updated_shading = obj.is_updated_shading
                rman_update.is_updated_transform = obj.is_updated_transform

                rfb_log().debug("\tObject: %s Updated" % obj.id.name)
                rfb_log().debug("\t    is_updated_geometry: %s" % str(obj.is_updated_geometry))
                rfb_log().debug("\t    is_updated_shading: %s" % str(obj.is_updated_shading))
                rfb_log().debug("\t    is_updated_transform: %s" % str(obj.is_updated_transform))
                self.rman_updates[obj.id.original] = rman_update

        if not self.rman_updates and self.num_instances_changed:
            # The number of instances changed, but we are not able
            # to determine what changed. We are forced to check
            # all instances.
            rfb_log().debug("Set check_all_instances to True")
            self.check_all_instances = True
                         
        self.check_instances_batch()

        # update any materials
        material_translator = self.rman_scene.rman_translators['MATERIAL']
        for id, rman_sg_material in self.rman_scene.rman_materials.items():              
            if rman_sg_material.is_frame_sensitive or id.original in self.rman_updates:
                mat = id.original
                material_translator.update(mat, rman_sg_material)    
                                                
        self.rman_scene.export_integrator()
        self.rman_scene.export_samplefilters()
        self.rman_scene.export_displayfilters()
        self.rman_scene.export_displays()
        
        if self.rman_scene.do_motion_blur and self.rman_scene.moving_objects:
            self.rman_scene.export_instances_motion()

    @time_this
    def check_instances_batch(self):
        already_udpated = list() # list of objects already updated during our loop
        clear_instances = list() # list of objects who had their instances cleared            
        rfb_log().debug("Updating instances")        

        for instance in self.rman_scene.depsgraph.object_instances:
            if instance.object.type in ('ARMATURE', 'CAMERA'):
                continue
            ob_key = instance.object.original
            ob_eval = instance.object.evaluated_get(self.rman_scene.depsgraph)                
            instance_parent = None
            psys = None 
            proto_key = object_utils.prototype_key(instance)              
            if instance.is_instance:
                ob_key = instance.instance_object.original      
                psys = instance.particle_system
                instance_parent = instance.parent 

            if self.rman_scene.do_motion_blur:
                if ob_key.name_full in self.rman_scene.moving_objects:
                    continue    

            rman_type = object_utils._detect_primitive_(ob_eval)  
            rman_sg_node = self.rman_scene.get_rman_prototype(proto_key, ob=ob_eval)
            if not rman_sg_node:
                continue            

            if self.check_all_instances:
                # check all instances in the scene
                rman_update = self.rman_updates.get(ob_key, None)
                if not rman_update:                  
                    rman_update = RmanUpdate()
                    rman_update.is_updated_shading = True
                    rman_update.is_updated_transform = True
                    self.rman_updates[ob_key] = rman_update  
            else:                        
                if ob_key not in self.rman_updates:
                    if rman_sg_node.is_frame_sensitive:
                        rman_update = RmanUpdate()
                        rman_update.is_updated_geometry = True
                        rman_update.is_updated_shading = True
                        rman_update.is_updated_transform = True
                        self.rman_updates[ob_key] = rman_update  
                    else:
                        if not instance_parent:
                            continue
                        if instance_parent.original not in self.rman_updates:
                            continue
                        rman_update = self.rman_updates[instance_parent.original]
                else:
                    rman_update = self.rman_updates[ob_key]

            if rman_sg_node and not instance.is_instance:
                if rman_update.is_updated_geometry and proto_key not in already_udpated:
                    translator =  self.rman_scene.rman_translators.get(rman_type, None)
                    rfb_log().debug("\tUpdating Object: %s" % proto_key)
                    translator.update(ob_eval, rman_sg_node)  
                    self.update_particle_emitters(ob_eval)
                    already_udpated.append(proto_key)   

            if rman_type == 'EMPTY':
                self.rman_scene._export_hidden_instance(ob_eval, rman_sg_node)                   

            if rman_type in object_utils._RMAN_NO_INSTANCES_:
                continue                         
     
            # clear all instances for this prototype, if
            # we have not already done so
            if instance_parent:
                parent_proto_key = object_utils.prototype_key(instance_parent)
                rman_parent_node = self.rman_scene.get_rman_prototype(parent_proto_key, ob=instance_parent)
                if rman_parent_node and rman_parent_node not in clear_instances:
                    rfb_log().debug("\tClearing parent instances: %s" % parent_proto_key)
                    rman_parent_node.clear_instances()
                    clear_instances.append(rman_parent_node) 
            elif rman_sg_node not in clear_instances:
                rfb_log().debug("\tClearing instances: %s" % proto_key)
                rman_sg_node.clear_instances()
                clear_instances.append(rman_sg_node) 

            self.rman_scene.export_instance(ob_eval, instance, rman_sg_node, rman_type, instance_parent, psys)                
                   
    @time_this
    def update_scene(self, context, depsgraph):
        ## FIXME: this function is waaayyy too big and is doing too much stuff

        self.rman_updates = dict()
        self.num_instances_changed = False
        self.frame_number_changed = False
        self.check_all_instances = False
                
        self.rman_scene.depsgraph = depsgraph
        self.rman_scene.bl_scene = depsgraph.scene
        self.rman_scene.context = context       

        rfb_log().debug("------Start update scene--------")    
       
        # Check the number of instances. If we differ, an object may have been
        # added or deleted
        if self.rman_scene.num_object_instances != len(depsgraph.object_instances):
            rfb_log().debug("\tNumber of instances changed: %d -> %d" % (self.rman_scene.num_object_instances, len(depsgraph.object_instances)))
            self.num_instances_changed = True
            self.rman_scene.num_object_instances = len(depsgraph.object_instances)

        for obj in reversed(depsgraph.updates):
            ob = obj.id

            if isinstance(obj.id, bpy.types.Scene):
                self.scene_updated()

            elif isinstance(obj.id, bpy.types.World):
                with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene): 
                    self.rman_scene.export_integrator()
                    self.rman_scene.export_samplefilters()
                    self.rman_scene.export_displayfilters()
                    self.rman_scene.export_viewport_stats()

            elif isinstance(obj.id, bpy.types.Camera):
                rfb_log().debug("Camera updated: %s" % obj.id.name)
                if self.rman_scene.is_viewport_render:
                    if self.rman_scene.bl_scene.camera.data != obj.id:
                        continue
                    rman_sg_camera = self.rman_scene.main_camera
                    translator = self.rman_scene.rman_translators['CAMERA']
                    with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
                        translator.update_viewport_cam(self.rman_scene.bl_scene.camera, rman_sg_camera, force_update=True)       
                else:
                    translator = self.rman_scene.rman_translators['CAMERA']                 
                    with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
                        for ob, rman_sg_camera in self.rman_scene.rman_cameras.items():     
                            if ob.original.name != obj.id.name:
                                continue
                            translator._update_render_cam(ob.original, rman_sg_camera)

            elif isinstance(obj.id, bpy.types.Material):
                rfb_log().debug("Material updated: %s" % obj.id.name)
                self.material_updated(obj)    

            elif isinstance(obj.id, bpy.types.Mesh):
                rfb_log().debug("Mesh updated: %s" % obj.id.name)
                '''
                # Experimental code path. We can use context.blend_data.user_map to ask
                # what objects use this mesh. We can then loop thru and call object_update on these
                # objects.
                # We could also try doing the same thing when we add a new Material. i.e.:
                # use user_map to figure out what objects are using this material; however, that would require
                # two loops thru user_map
                users = context.blend_data.user_map(subset={obj.id.original}, value_types={'OBJECT'})
                translator = self.rman_scene.rman_translators['MESH']
                with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
                    for o in users[obj.id.original]:
                        rman_type = object_utils._detect_primitive_(o)
                        if rman_type != 'MESH':
                            continue
                        rman_sg_node = self.rman_scene.rman_objects.get(o.original, None)
                        translator.update(o, rman_sg_node)
                        # material slots could have changed, so we need to double
                        # check that too
                        for k,v in rman_sg_node.instances.items():
                            self.rman_scene.attach_material(o, v)                
                return
                '''

            elif isinstance(obj.id, bpy.types.ParticleSettings):
                rfb_log().debug("ParticleSettings updated: %s" % obj.id.name)

                with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
                    for o in self.rman_scene.bl_scene.objects:
                        psys = None
                        ob = o.evaluated_get(depsgraph)
                        for ps in ob.particle_systems:
                            if ps.settings.original == obj.id.original:
                                psys = ps
                                break
                        if not psys:
                            continue
                        if object_utils.is_particle_instancer(psys):
                            #self.check_particle_instancer(obj, psys)
                            pass
                        else:
                            self.update_particle_emitter(ob, psys)

                        if o.original not in self.rman_updates:
                            rman_update = RmanUpdate()

                            rman_update.is_updated_geometry = obj.is_updated_geometry
                            rman_update.is_updated_shading = obj.is_updated_shading
                            rman_update.is_updated_transform = obj.is_updated_transform   
                            self.rman_updates[o.original] = rman_update                         
                        
            elif isinstance(obj.id, bpy.types.ShaderNodeTree):
                if obj.id.name in bpy.data.node_groups:
                    if len(obj.id.nodes) < 1:
                        continue
                    if not obj.id.name.startswith(rman_constants.RMAN_FAKE_NODEGROUP):
                        continue
                    # this is one of our fake node groups with ramps
                    # update all of the users of this node tree
                    rfb_log().debug("ShaderNodeTree updated: %s" % obj.id.name)
                    users = context.blend_data.user_map(subset={obj.id.original})
                    for o in users[obj.id.original]:
                        if hasattr(o, 'rman_nodetree'):
                            o.rman_nodetree.update_tag()
                        elif hasattr(o, 'node_tree'):
                            o.node_tree.update_tag()                
                                            
            elif isinstance(obj.id, bpy.types.Object):                
                ob_eval = obj.id.evaluated_get(depsgraph)
                rman_type = object_utils._detect_primitive_(ob_eval)

                if ob.type in ('ARMATURE'):
                    continue
                
                # These types need special handling                
                if rman_type == 'EMPTY':
                    self.update_empty(obj)   
                    continue             
                if rman_type == 'LIGHTFILTER':
                    self.light_filter_updated(obj)
                    continue                
                if ob.type in ['CAMERA']:
                    self.camera_updated(obj)                       
                    continue         
                
                rman_update = RmanUpdate()

                rman_update.is_updated_geometry = obj.is_updated_geometry
                rman_update.is_updated_shading = obj.is_updated_shading
                rman_update.is_updated_transform = obj.is_updated_transform

                rfb_log().debug("\tObject: %s Updated" % obj.id.name)
                rfb_log().debug("\t    is_updated_geometry: %s" % str(obj.is_updated_geometry))
                rfb_log().debug("\t    is_updated_shading: %s" % str(obj.is_updated_shading))
                rfb_log().debug("\t    is_updated_transform: %s" % str(obj.is_updated_transform))
                self.rman_updates[obj.id.original] = rman_update

                # Check if this object is the focus object the camera. If it is
                # we need to update the camera
                if obj.is_updated_transform:
                    for camera in bpy.data.cameras:
                        rm = camera.renderman
                        if rm.rman_focus_object and rm.rman_focus_object.original == ob_eval.original:
                            camera.update_tag()

                    
            elif isinstance(obj.id, bpy.types.Collection):
                rfb_log().debug("Collection updated: %s" % obj.id.name)
                #self.update_collection(obj.id)

            else:
                rfb_log().debug("Not handling %s update: %s" % (str(type(obj.id)), obj.id.name))

        if not self.rman_updates and self.num_instances_changed:
            # The number of instances changed, but we are not able
            # to determine what changed. We are forced to check
            # all instances.
            rfb_log().debug("Set check_all_instances to True")
            self.check_all_instances = True
                         
        if self.check_all_instances or self.rman_updates:
            self.check_instances()
                            
        # call txmake all in case of new textures
        texture_utils.get_txmanager().txmake_all(blocking=False)                              
        rfb_log().debug("------End update scene----------")    

    @time_this
    def check_instances(self):
        deleted_obj_keys = list(self.rman_scene.rman_prototypes) # list of potential objects to delete
        already_udpated = list() # list of objects already updated during our loop
        clear_instances = list() # list of objects who had their instances cleared            
        rfb_log().debug("Updating instances")        
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene): 
            for instance in self.rman_scene.depsgraph.object_instances:
                if instance.object.type in ('ARMATURE', 'CAMERA'):
                    continue

                ob_key = instance.object.original
                ob_eval = instance.object.evaluated_get(self.rman_scene.depsgraph)                
                instance_parent = None
                psys = None 
                is_new_object = False
                proto_key = object_utils.prototype_key(instance)              
                if instance.is_instance:
                    ob_key = instance.instance_object.original      
                    psys = instance.particle_system
                    instance_parent = instance.parent 
                    
                if proto_key in deleted_obj_keys:
                    deleted_obj_keys.remove(proto_key) 

                rman_type = object_utils._detect_primitive_(ob_eval)
                
                rman_sg_node = self.rman_scene.get_rman_prototype(proto_key)
                if rman_sg_node and rman_type != rman_sg_node.rman_type:
                    # Types don't match
                    #
                    # This can happen because
                    # we have not been able to tag our types before Blender
                    # tells us an object has been added
                    # For now, just delete the existing sg_node
                    rfb_log().debug("\tTypes don't match. Removing: %s" % proto_key)
                    del self.rman_scene.rman_prototypes[proto_key]
                    rman_sg_node = None

                if not rman_sg_node:
                    # this is a new object.
                    rman_sg_node = self.rman_scene.export_data_block(proto_key, ob_eval)
                    if not rman_sg_node:
                        continue

                    rfb_log().debug("\tNew Object added: %s (%s)" % (proto_key, rman_type))

                    if rman_type == 'LIGHTFILTER':
                        # update all lights with this light filter
                        users = bpy.context.blend_data.user_map(subset={ob_eval.original})
                        for o in users[ob_eval.original]:
                            if isinstance(o, bpy.types.Light):
                                o.node_tree.update_tag()
                        continue

                    is_new_object = True
                    rman_update = self.rman_updates.get(ob_key, None)
                    if not rman_update:
                        rman_update = RmanUpdate()
                        rman_update.is_updated_geometry = True
                        rman_update.is_updated_shading = True
                        rman_update.is_updated_transform = True
                        self.rman_updates[ob_key] = rman_update    
                    rman_update.is_updated_geometry = False
                    clear_instances.append(rman_sg_node)
                                
                if self.check_all_instances:
                    # check all instances in the scene
                    rman_update = self.rman_updates.get(ob_key, None)
                    if not rman_update:                  
                        rman_update = RmanUpdate()
                        rman_update.is_updated_shading = True
                        rman_update.is_updated_transform = True
                        self.rman_updates[ob_key] = rman_update  
                else:                        
                    if ob_key not in self.rman_updates:
                        if not instance_parent:
                            continue
                        if instance_parent.original not in self.rman_updates:
                            continue
                        rman_update = self.rman_updates[instance_parent.original]
                    else:
                        rman_update = self.rman_updates[ob_key]                     

                if rman_sg_node and not is_new_object and not instance.is_instance:
                    if rman_update.is_updated_geometry and proto_key not in already_udpated:
                        translator =  self.rman_scene.rman_translators.get(rman_type, None)
                        rfb_log().debug("\tUpdating Object: %s" % proto_key)
                        translator.update(ob_eval, rman_sg_node)  
                        self.update_particle_emitters(ob_eval)
                        already_udpated.append(proto_key)   

                if rman_type == 'EMPTY':
                    self.rman_scene._export_hidden_instance(ob_eval, rman_sg_node)                   

                if rman_type in object_utils._RMAN_NO_INSTANCES_:
                    continue                         

                # clear all instances for this prototype, if
                # we have not already done so
                if instance_parent:
                    parent_proto_key = object_utils.prototype_key(instance_parent)
                    rman_parent_node = self.rman_scene.get_rman_prototype(parent_proto_key, ob=instance_parent)
                    if rman_parent_node and rman_parent_node not in clear_instances:
                        rfb_log().debug("\tClearing parent instances: %s" % parent_proto_key)
                        rman_parent_node.clear_instances()
                        clear_instances.append(rman_parent_node) 
                elif rman_sg_node not in clear_instances:
                    rfb_log().debug("\tClearing instances: %s" % proto_key)
                    rman_sg_node.clear_instances()
                    clear_instances.append(rman_sg_node) 

                if not self.rman_scene.check_visibility(instance):
                    # This instance is not visible in the viewport. Don't
                    # add an instance of it
                    continue

                self.rman_scene.export_instance(ob_eval, instance, rman_sg_node, rman_type, instance_parent, psys)

                if rman_type == 'LIGHT':
                    # We are dealing with a light. Check if it's a solo light, or muted
                    self.rman_scene.check_solo_light(rman_sg_node, ob_eval)

                    # check portal lights
                    self.update_portals(ob_eval)
                    
                    # Hide the default light
                    if self.rman_scene.default_light.GetHidden() != 1:
                        self.rman_scene.default_light.SetHidden(1)                

                # Delete any removed partcle systems
                if proto_key in self.rman_scene.rman_particles:                                                
                    ob_psys = self.rman_scene.rman_particles[proto_key]
                    rman_particle_nodes = list(ob_psys)
                    for psys in ob_eval.particle_systems:
                        try:
                            rman_particle_nodes.remove(psys.settings.original)
                        except:
                            continue
                    if rman_particle_nodes:
                        rfb_log().debug("\t\tRemoving particle nodes: %s" % proto_key)
                    for k in rman_particle_nodes:                        
                        del ob_psys[k]
                                                                                            
            # delete objects
            if deleted_obj_keys:
                self.delete_objects(deleted_obj_keys)        
                     
    @time_this
    def delete_objects(self, deleted_obj_keys=list()):
        rfb_log().debug("Deleting objects")
        for key in deleted_obj_keys:
            rman_sg_node = self.rman_scene.get_rman_prototype(key)
            if not rman_sg_node:
                continue
            
            rfb_log().debug("\tDeleting: %s" % rman_sg_node.db_name)           
            if key in self.rman_scene.rman_particles:
                rfb_log().debug("\t\tRemoving particles...")
                del self.rman_scene.rman_particles[key]

            del self.rman_scene.rman_prototypes[key]
            
            # We just deleted a light filter. We need to tell all lights
            # associated with this light filter to update
            if isinstance(rman_sg_node, RmanSgLightFilter):
                self.rman_scene.get_root_sg_node().RemoveCoordinateSystem(rman_sg_node.sg_node)
                for o in rman_sg_node.lights_list:
                    if o:
                        if hasattr(o, 'rman_nodetree'):
                            o.rman_nodetree.update_tag()
                        elif hasattr(o.data, 'node_tree'):
                            o.data.node_tree.update_tag()    
            
            
        if self.rman_scene.render_default_light:
            self.rman_scene.scene_any_lights = self.rman_scene._scene_has_lights()     
            if not self.rman_scene.scene_any_lights:
                self.rman_scene.default_light.SetHidden(0)    
                 
    def update_cropwindow(self, cropwindow=None):
        if not self.rman_render.rman_interactive_running:
            return
        if cropwindow:
            with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene): 
                options = self.rman_scene.sg_scene.GetOptions()
                options.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_CropWindow, cropwindow, 4)  
                self.rman_scene.sg_scene.SetOptions(options)           

    def update_integrator(self, context):
        if not self.rman_render.rman_interactive_running:
            return        
        if context:
            self.rman_scene.bl_scene = context.scene
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            self.rman_scene.export_integrator() 
            self.rman_scene.export_viewport_stats()

    def update_viewport_integrator(self, context, integrator):
        if not self.rman_render.rman_interactive_running:
            return        
        self.rman_scene.bl_scene = context.scene
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            integrator_sg = self.rman_scene.rman.SGManager.RixSGShader("Integrator", integrator, "integrator")       
            self.rman_scene.sg_scene.SetIntegrator(integrator_sg)     
            self.rman_scene.export_viewport_stats(integrator=integrator)  

    def update_viewport_res_mult(self, context):
        if not self.rman_render.rman_interactive_running:
            return        
        if not self.rman_scene.is_viewport_render:
            return         
        if context:
            self.rman_scene.context = context
            self.rman_scene.bl_scene = context.scene    
            self.rman_scene.viewport_render_res_mult = float(context.scene.renderman.viewport_render_res_mult)
        rman_sg_camera = self.rman_scene.main_camera
        translator = self.rman_scene.rman_translators['CAMERA']
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            translator.update_viewport_resolution(rman_sg_camera)
            translator.update_transform(None, rman_sg_camera)
            self.rman_scene.export_viewport_stats()                  

    def update_global_options(self, context):
        if not self.rman_render.rman_interactive_running:
            return        
        self.rman_scene.bl_scene = context.scene
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            self.rman_scene.export_global_options()            
            self.rman_scene.export_hider()
            self.rman_scene.export_viewport_stats()

    def update_root_node_func(self, context):
        if not self.rman_render.rman_interactive_running:
            return        
        self.rman_scene.bl_scene = context.scene
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            self.rman_scene.export_root_sg_node()         
 
    def update_material(self, mat):
        if not self.rman_render.rman_interactive_running:
            return        
        rman_sg_material = self.rman_scene.rman_materials.get(mat.original, None)
        if not rman_sg_material:
            return
        translator = self.rman_scene.rman_translators["MATERIAL"]     
        has_meshlight = rman_sg_material.has_meshlight   
        rfb_log().debug("Manual material update called for: %s." % mat.name)
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):                  
            translator.update(mat, rman_sg_material)

        if has_meshlight != rman_sg_material.has_meshlight:
            # we're dealing with a mesh light
            rfb_log().debug("Manually calling mesh_light_update")
            self.rman_scene.depsgraph = bpy.context.evaluated_depsgraph_get()
            self._mesh_light_update(mat)    

    def update_light(self, ob):
        if not self.rman_render.rman_interactive_running:
            return        
        ob.data.node_tree.update_tag()
        
    def update_light_filter(self, ob):
        if not self.rman_render.rman_interactive_running:
            return        
        ob.data.node_tree.update_tag()

    def update_solo_light(self, context):
        if not self.rman_render.rman_interactive_running:
            return        
        # solo light has changed
        self.rman_scene.bl_scene = context.scene
        self.rman_scene.scene_solo_light = self.rman_scene.bl_scene.renderman.solo_light
                    
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):            
            for light_ob in scene_utils.get_all_lights(self.rman_scene.bl_scene, include_light_filters=False):
                light_ob.update_tag()

    def update_un_solo_light(self, context):
        if not self.rman_render.rman_interactive_running:
            return        
        # solo light has changed
        self.rman_scene.bl_scene = context.scene
        self.rman_scene.scene_solo_light = self.rman_scene.bl_scene.renderman.solo_light
                    
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):                                               
            for light_ob in scene_utils.get_all_lights(self.rman_scene.bl_scene, include_light_filters=False):
                light_ob.update_tag()

    def update_viewport_chan(self, context, chan_name):
        if not self.rman_render.rman_interactive_running:
            return        
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            self.rman_scene.export_samplefilters(sel_chan_name=chan_name)

    def update_displays(self, context):
        if not self.rman_render.rman_interactive_running:
            return        
        self.rman_scene.bl_scene = context.scene    
        self.rman_scene._find_renderman_layer()
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):
            self.rman_scene.export_displays()         

    def texture_updated(self, nodeID):
        if not self.rman_render.rman_interactive_running:
            return        
        if nodeID == '':
            return
        tokens = nodeID.split('|')
        if len(tokens) < 2:
            return

        ob_name = tokens[0]
        node_name = tokens[1]
        node, ob = scene_utils.find_node_by_name(node_name, ob_name)
        if ob == None:
            return

        ob_type = type(ob)

        if isinstance(ob, bpy.types.Material):
            ob.node_tree.update_tag()
        elif isinstance(ob, bpy.types.NodeTree):
            ob.update_tag()
        elif ob_type == bpy.types.World:
            ob.update_tag()   
        else:
            # light, lightfilters, and cameras
            ob.update_tag(refresh={'DATA'})

    def flush_texture_cache(self, texture_list):
        if not self.rman_render.rman_interactive_running:
            return         
        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):  
            for tex in texture_list:
                self.rman_scene.sg_scene.InvalidateTexture(tex)   

    def update_enhance(self, context, x, y, zoom):
        if not self.rman_render.rman_interactive_running:
            return         
        rman_sg_camera = self.rman_scene.main_camera
        if rman_sg_camera.projection_shader.name.CStr() != 'PxrCamera':
            return

        with self.rman_scene.rman.SGManager.ScopedEdit(self.rman_scene.sg_scene):     
            res_x = int(self.rman_scene.viewport_render_res_mult * x)
            res_y = int(self.rman_scene.viewport_render_res_mult * y)
            projparams = rman_sg_camera.projection_shader.params         
            projparams.SetVector("enhance", [res_x, res_y, zoom])
            rman_sg_camera.sg_camera_node.SetProjection(rman_sg_camera.projection_shader)
