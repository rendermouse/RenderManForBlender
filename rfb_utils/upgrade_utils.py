from .. import rman_constants
from ..rfb_utils import shadergraph_utils
from ..rfb_logger import rfb_log
from collections import OrderedDict
import bpy

def upgrade_242(scene):
    shadergraph_utils.reload_bl_ramps(scene, check_library=False)

def upgrade_243(scene):
    for node in shadergraph_utils.get_all_shading_nodes(scene=scene):
        for prop_name, meta in node.prop_meta.items():
            param_type = meta['renderman_type']       
            if param_type != 'array':
                continue
            array_len = getattr(node, '%s_arraylen' % prop_name)   
            coll_nm = '%s_collection' % prop_name     
            collection = getattr(node, coll_nm)
            param_array_type = meta['renderman_array_type']
            for i in range(array_len):
                elem = collection.add()
                elem.name = '%s[%d]' % (prop_name, len(collection)-1)  
                elem.type = param_array_type

def upgrade_250(scene):
    '''
    Rename input/output sockets:
        Bxdf -> bxdf_in/bxdf_out
        Light -> light_in/light_out
        Displacement -> displace_in/displace_out
        LightFilter -> lightfilter_in/lightfilter_out
        Integrator -> integrator_in/integrator_out
        Projection -> projection_in/projection_out
        DisplayFilter -> displayfilter_in/displayfilter_out
        SampleFilter -> samplefilter_in/samplefilter_out

    Add: color ramp to PxrStylizedToon

    '''
    for node in shadergraph_utils.get_all_shading_nodes(scene=scene):
        renderman_node_type = getattr(node, 'renderman_node_type', '')
        if renderman_node_type in ['bxdf', 'projection', 'light', 'integrator']:
            old_name = renderman_node_type.capitalize()
            if old_name in node.outputs:
                node.outputs[old_name].name = '%s_out' % renderman_node_type
        elif renderman_node_type in ['displace', 'displacement']:
            if 'Displacement' in node.outputs:
                node.outputs['Displacement'].name = 'displace_out'
        elif renderman_node_type == 'lightfilter':
            if 'LightFilter' in node.outputs:
                node.outputs['LightFilter'].name = '%s_out' % renderman_node_type
        elif renderman_node_type == 'samplefilter':
            if 'SampleFilter' in node.outputs:
                node.outputs['SampleFilter'].name = '%s_out' % renderman_node_type
        elif renderman_node_type == 'displayfilter':
            if 'DisplayFilter' in node.outputs:
                node.outputs['DisplayFilter'].name = '%s_out' % renderman_node_type

            if node.bl_label == 'PxrStylizedToon':
                nt = node.rman_fake_node_group_ptr
                n = nt.nodes.new('ShaderNodeValToRGB')             
                setattr(node, 'colorRamp', n.name)                 

    
    for mat in bpy.data.materials:
        output = shadergraph_utils.find_node(mat, 'RendermanOutputNode')
        if output:
            if 'Bxdf' in output.inputs:
                output.inputs['Bxdf'].name = 'bxdf_in'
            if 'Light' in output.inputs:
                output.inputs['Light'].name = 'light_in'
            if 'Displacement' in output.inputs:
                output.inputs['Displacement'].name = 'displace_in'
            if 'LightFilter' in output.inputs:
                output.inputs['LightFilter'].name = 'lightfilter_in'

    for light in bpy.data.lights:
        output = shadergraph_utils.is_renderman_nodetree(light)
        if output:
            if 'Light' in output.inputs:
                output.inputs['Light'].name = 'light_in'
            if 'LightFilter' in output.inputs:                
                output.inputs['LightFilter'].name = 'lightfilter_in'

    for world in bpy.data.worlds:
        output = shadergraph_utils.find_node(world, 'RendermanIntegratorsOutputNode')
        if output:
            if 'Integrator' in output.inputs:
                output.inputs['Integrator'].name = 'integrator_in'

        output = shadergraph_utils.find_node(world, 'RendermanSamplefiltersOutputNode')
        if output:
            for i, o in enumerate(output.inputs):
                o.name = 'samplefilter_in[%d]' % i

        output = shadergraph_utils.find_node(world, 'RendermanDisplayfiltersOutputNode')
        if output:
            for i, o in enumerate(output.inputs):
                o.name = 'displayfilter_in[%d]' % i            

    for camera in bpy.data.cameras:
        nt = camera.renderman.rman_nodetree
        if nt:
            output = shadergraph_utils.find_node_from_nodetree(nt, 'RendermanProjectionsOutputNode')
            if 'Projection' in output.inputs:
                output.inputs['Projection'].name = 'projection_in'
            

__RMAN_SCENE_UPGRADE_FUNCTIONS__ = OrderedDict()
    
__RMAN_SCENE_UPGRADE_FUNCTIONS__['24.2'] = upgrade_242
__RMAN_SCENE_UPGRADE_FUNCTIONS__['24.3'] = upgrade_243
__RMAN_SCENE_UPGRADE_FUNCTIONS__['25.0'] = upgrade_250

def upgrade_scene(bl_scene):
    global __RMAN_SCENE_UPGRADE_FUNCTIONS__

    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        version = scene.renderman.renderman_version
        if version == '':
            # we started adding a renderman_version property in 24.1
            version = '24.1'

        for version_str, fn in __RMAN_SCENE_UPGRADE_FUNCTIONS__.items():
            if version < version_str:
                rfb_log().debug('Upgrade scene to %s' % version_str)
                fn(scene)

        scene.renderman.renderman_version = rman_constants.RMAN_SUPPORTED_VERSION_STRING                
               
def update_version(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        scene.renderman.renderman_version = rman_constants.RMAN_SUPPORTED_VERSION_STRING