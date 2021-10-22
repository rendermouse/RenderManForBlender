from . import string_utils
from . import filepath_utils
from . import scene_utils
from . import shadergraph_utils
from .property_utils import BlPropInfo
#from . import object_utils
from .prefs_utils import get_pref
from ..rfb_logger import rfb_log
from rman_utils import txmanager
from rman_utils.txmanager import core as txcore
from rman_utils.txmanager import txparams as txparams
from .color_manager_blender import color_manager

from bpy.app.handlers import persistent

import os
import glob
import subprocess
import bpy
import uuid
import re

__RFB_TXMANAGER__ = None

class RfBTxManager(object):

    def __init__(self):        
        self.txmanager = txcore.TxManager(host_token_resolver_func=self.host_token_resolver_func, 
                                        host_prefs_func=self.get_prefs,
                                        host_tex_done_func=self.done_callback,
                                        host_load_func=load_scene_state,
                                        host_save_func=save_scene_state,
                                        texture_extensions=self.get_ext_list(),
                                        color_manager=color_manager())
        self.rman_scene = None

    @property
    def rman_scene(self):
        return self.__rman_scene

    @rman_scene.setter
    def rman_scene(self, rman_scene):
        self.__rman_scene = rman_scene      

    def get_prefs(self):
        prefs = dict()
        prefs['num_workers'] = get_pref('rman_txmanager_workers')
        prefs['fallback_path'] = string_utils.expand_string(get_pref('path_fallback_textures_path'), 
                                                  asFilePath=True)
        prefs['fallback_always'] = get_pref('path_fallback_textures_path_always')
        prefs['keep_extension'] = get_pref('rman_txmanager_keep_extension')

        return prefs

    def get_ext_list(self):
        ext_prefs = get_pref('rman_txmanager_tex_extensions')
        ext_list = ['.%s' % ext for ext in ext_prefs.split()]
        return ext_list

    def host_token_resolver_func(self, outpath):
        if self.rman_scene:
            outpath = string_utils.expand_string(outpath, frame=self.rman_scene.bl_frame_current, asFilePath=True)
        else:
            outpath = string_utils.expand_string(outpath, asFilePath=True)
        return outpath

    def done_callback(self, nodeID, txfile):
        def tex_done():
            try:
                # try and refresh the texture manager UI
                bpy.ops.rman_txmgr_list.refresh('EXEC_DEFAULT')
            except:
                pass
            from .. import rman_render
            output_texture = self.get_output_tex(txfile)
            rr = rman_render.RmanRender.get_rman_render()
            rr.rman_scene_sync.flush_texture_cache([output_texture])
            rr.rman_scene_sync.texture_updated(nodeID)
            
        return tex_done    

    def get_output_tex(self, txfile):
        '''
        Get the real output texture path given a TxFile 
        '''
        if txfile.state in (txmanager.STATE_EXISTS, txmanager.STATE_IS_TEX):
            output_tex = txfile.get_output_texture()
            if self.rman_scene:
                output_tex = string_utils.expand_string(output_tex, frame=self.rman_scene.bl_frame_current, asFilePath=True)
            else:
                output_tex = string_utils.expand_string(output_tex, asFilePath=True)    
        elif txfile.state == txmanager.STATE_INPUT_MISSING:       
            output_tex = txfile.input_image
            if self.rman_scene:
                output_tex = string_utils.expand_string(output_tex, frame=self.rman_scene.bl_frame_current, asFilePath=True)
            else:
                output_tex = string_utils.expand_string(output_tex, asFilePath=True)                
        else:
            output_tex = self.txmanager.get_placeholder_tex()

        return output_tex        


    def get_output_tex_from_id(self, nodeID):
        '''
        Get the real output texture path given a nodeID
        '''
        txfile = self.txmanager.get_txfile_from_id(nodeID)
        if not txfile:
            return ''

        return self.get_output_tex(txfile)

    def get_output_vdb(self, ob):
        '''
        Get the mipmapped version of the openvdb file
        '''
        if ob.type != 'VOLUME':
            return ''
        db = ob.data
        grids = db.grids

        openvdb_file = filepath_utils.get_real_path(db.filepath)
        if db.is_sequence:
            # if we have a sequence, get the current frame filepath from the grids   
            openvdb_file = string_utils.get_tokenized_openvdb_file(grids.frame_filepath, grids.frame)

        nodeID = generate_node_id(None, 'filepath', ob=ob)
        if self.does_nodeid_exists(nodeID):
            openvdb_file = self.get_output_tex_from_id(nodeID)
            return openvdb_file
        return openvdb_file

    def get_txfile_for_vdb(self, ob):
        nodeID = generate_node_id(None, 'filepath', ob=ob)
        return self.get_txfile_from_id(nodeID)

    def get_txfile_from_id(self, nodeID):
        '''
        Get the txfile from given a nodeID
        '''
        txfile = self.txmanager.get_txfile_from_id(nodeID)
        return txfile       
                
    def get_txfile(self, node, param_name, ob=None):
        nodeID = generate_node_id(node, param_name, ob=ob)
        return self.get_txfile_from_id(nodeID)

    def txmake_all(self, blocking=True):
        self.txmanager.txmake_all(start_queue=True, blocking=blocking)   

    def add_texture(self, node, ob, param_name, file_path, node_type='PxrTexture', category='pattern'):
        nodeID = generate_node_id(node, param_name, ob=ob)

        if file_path == "":
            txfile = self.txmanager.get_txfile_from_id(nodeID)
            if txfile:
                self.txmanager.remove_texture(nodeID)
                bpy.ops.rman_txmgr_list.remove_texture('EXEC_DEFAULT', nodeID=nodeID)
        else:
            txfile = self.txmanager.add_texture(nodeID, file_path, nodetype=node_type, category=category)    
            bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=file_path, nodeID=nodeID)
            txmake_all(blocking=False)
            if txfile:
                self.done_callback(nodeID, txfile)      

    def is_file_src_tex(self, node, prop_name):
        id = scene_utils.find_node_owner(node)
        nodeID = generate_node_id(node, prop_name, ob=id)
        txfile = self.get_txfile_from_id(nodeID)
        if txfile:
            return (txfile.state == txmanager.STATE_IS_TEX)  
        return False

    def does_file_exist(self, file_path):
        if self.rman_scene:
            outpath = string_utils.expand_string(file_path, frame=self.rman_scene.bl_frame_current, asFilePath=True)
        else:
            outpath = string_utils.expand_string(file_path, asFilePath=True)
        return os.path.exists(outpath)

    def does_nodeid_exists(self, nodeID):
        txfile = self.txmanager.get_txfile_from_id(nodeID)
        if txfile:
            return True
        return False

def get_txmanager():
    global __RFB_TXMANAGER__
    if __RFB_TXMANAGER__ is None:
        __RFB_TXMANAGER__ = RfBTxManager()
    return __RFB_TXMANAGER__    

def update_texture(node, ob=None, check_exists=False):
    bl_idname = getattr(node, 'bl_idname', '')
    if bl_idname == "PxrOSLPatternNode":
        for input_name, input in node.inputs.items():
            if hasattr(input, 'is_texture') and input.is_texture:
                prop = input.default_value
                nodeID = generate_node_id(node, input_name)
                real_file = filepath_utils.get_real_path(prop)
                get_txmanager().txmanager.add_texture(nodeID, real_file)    
                bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=real_file, nodeID=nodeID)                                                      
        return
    elif node.bl_idname == 'ShaderNodeGroup':
        nt = node.node_tree
        for node in nt.nodes:
            update_texture(node, ob=ob)
        return

    prop_meta = getattr(node, 'prop_meta', dict())
    for prop_name, meta in prop_meta.items():
        bl_prop_info = BlPropInfo(node, prop_name, meta)
        if not bl_prop_info.prop:
            continue
        if bl_prop_info.renderman_type == 'page':
            continue
        elif bl_prop_info.is_texture:
            node_type = ''
            if isinstance(ob, bpy.types.Object):
                if ob.type == 'LIGHT':
                    node_type = ob.data.renderman.get_light_node_name()
                else:
                    node_type = node.bl_label                            
            else:
                node_type = node.bl_label

            if ob and check_exists:
                nodeID = generate_node_id(node, prop_name, ob=ob)
                if get_txmanager().does_nodeid_exists(nodeID):
                    continue

            category = getattr(node, 'renderman_node_type', 'pattern') 
            get_txmanager().add_texture(node, ob, prop_name, bl_prop_info.prop, node_type=node_type, category=category)

def generate_node_id(node, prop_name, ob=None):
    if node is None:
        nodeID = '%s|%s' % (prop_name, ob.name)
        return nodeID
    
    nm = shadergraph_utils.get_nodetree_name(node)
    if nm:
        nodeID = '%s|%s|%s|%s' % (node.name, prop_name, nm, ob.name)
    elif ob:
        nodeID = '%s|%s|%s|%s' % (node.name, prop_name, ob.name, ob.name)
    else:
        prop = ''
        real_file = ''
        if hasattr(node, prop_name):
            prop = getattr(node, prop_name)
            real_file = filepath_utils.get_real_path(prop)
        nodeID = '%s|%s|%s' % (node.name, prop_name, real_file)
    return nodeID

def get_textures(id, check_exists=False, mat=None):
    if id is None or not id.node_tree:
        return

    nt = id.node_tree
    ob = id
    if mat:
        ob = mat
    for node in nt.nodes:
        if node.bl_idname == 'ShaderNodeGroup':
            get_textures(node, check_exists=check_exists, mat=ob)
        else:            
            update_texture(node, ob=ob, check_exists=check_exists)

def get_blender_image_path(bl_image):
    if bl_image.packed_file:
        bl_image.unpack()
    real_file = bpy.path.abspath(bl_image.filepath, library=bl_image.library)          
    return real_file 

def add_images_from_image_editor():
    
    # convert images in the image editor
    for img in bpy.data.images:
        if img.type != 'IMAGE':
            continue
        img_path = get_blender_image_path(img)
        if img_path != '' and os.path.exists(img_path): 
            nodeID = str(uuid.uuid1())
            txfile = get_txmanager().txmanager.add_texture(nodeID, img_path)        
            bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=img_path, nodeID=nodeID)       
            if txfile:
                get_txmanager().done_callback(nodeID, txfile)  

def add_openvdb(ob):
    db = ob.data
    grids = db.grids
    grids.load()                
    openvdb_file = filepath_utils.get_real_path(db.filepath)
    if db.is_sequence:
        grids.load()
        # if we have a sequence, get the current frame filepath and
        # then substitute with <f>
        openvdb_file = string_utils.get_tokenized_openvdb_file(grids.frame_filepath, grids.frame)

    if openvdb_file:
        input_name = 'filepath'
        nodeID = generate_node_id(None, input_name, ob=ob)
        get_txmanager().txmanager.add_texture(nodeID, openvdb_file, category='openvdb')    
        bpy.ops.rman_txmgr_list.add_texture('EXEC_DEFAULT', filepath=openvdb_file, nodeID=nodeID)          

def parse_scene_for_textures(bl_scene=None):

    #add_images_from_image_editor()

    if bl_scene:
        for o in scene_utils.renderable_objects(bl_scene):
            if o.type == 'EMPTY':
                continue
            elif o.type == 'CAMERA':
                node = shadergraph_utils.find_projection_node(o) 
                if node:
                    update_texture(node, ob=o)
            elif o.type == 'LIGHT':
                node = o.data.renderman.get_light_node()
                if node:
                    update_texture(node, ob=o)
            elif o.type == 'VOLUME':
                add_openvdb(o)
   
    for world in bpy.data.worlds:
        if not world.use_nodes:
            continue
        node = shadergraph_utils.find_integrator_node(world)
        if node:
            update_texture(node, ob=world)
        for node in shadergraph_utils.find_displayfilter_nodes(world):
            update_texture(node, ob=world)
        for node in shadergraph_utils.find_samplefilter_nodes(world):
            update_texture(node, ob=world)            
 
    for mat in bpy.data.materials:
        get_textures(mat)
            
def parse_for_textures(bl_scene):    
    rfb_log().debug("Parsing scene for textures.")                                   
    parse_scene_for_textures(bl_scene)

def save_scene_state(state):
    """Save the serialized TxManager object in scene.renderman.txmanagerData.
    """
    if bpy.context.engine != 'PRMAN_RENDER':
        return
    scene = bpy.context.scene
    rm = getattr(scene, 'renderman', None)
    if rm:
        setattr(rm, 'txmanagerData', state)

def load_scene_state():
    """Load the JSON serialization from scene.renderman.txmanagerData and use it
    to update the texture manager.
    """
    if bpy.context.engine != 'PRMAN_RENDER':
        return
    scene = bpy.context.scene
    rm = getattr(scene, 'renderman', None)
    state = '{}'
    if rm:
        state = getattr(rm, 'txmanagerData', state)
    return state

@persistent
def txmanager_load_cb(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    get_txmanager().txmanager.load_state()
    bpy.ops.rman_txmgr_list.parse_scene('EXEC_DEFAULT')
    bpy.ops.rman_txmgr_list.clear_unused('EXEC_DEFAULT')

@persistent
def txmanager_pre_save_cb(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    get_txmanager().txmanager.save_state()  

@persistent
def depsgraph_handler(bl_scene):
    for update in bpy.context.evaluated_depsgraph_get().updates:
        id = update.id
        if id.library:
            link_file_handler(id)
            continue
        if isinstance(id, bpy.types.Object):
            if id.type == 'VOLUME':
                continue
                '''
                vol = id.data
                ob = id
                txfile = get_txmanager().get_txfile_for_vdb(ob)
                if txfile:
                    grids = vol.grids
                    grids.load()
                    openvdb_file = string_utils.get_tokenized_openvdb_file(grids.frame_filepath, grids.frame)
                    if txfile.input_image != openvdb_file:
                        add_openvdb(ob)
                '''
        
def link_file_handler(id):
    if isinstance(id, bpy.types.Material):
        get_textures(id, check_exists=True)

    elif isinstance(id, bpy.types.Object):
        if id.type == 'CAMERA':
            node = shadergraph_utils.find_projection_node(id) 
            if node:
                update_texture(node, ob=id, check_exists=True)

        elif id.type == 'LIGHT':
            node = id.data.renderman.get_light_node()
            if node:
                update_texture(node, ob=id, check_exists=True)           

def txmake_all(blocking=True):
    get_txmanager().txmake_all(blocking=blocking)        