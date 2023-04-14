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

def upgrade_250_1(scene):   
    '''
    Upgrade lama nodes

    25.0b2 changed the names of input parameters for lama nodes,
    because they were using OSL reserved keywords (ex: color)
    '''         

    def copy_param(old_node, new_node, old_nm, new_nm):
        socket = old_node.inputs.get(old_nm, None)
        if socket and socket.is_linked:            
            connected_socket = socket.links[0].from_socket
            nt.links.new(connected_socket, new_node.inputs[new_nm])
        else:
            setattr(new_node, new_nm, getattr(n, old_nm))

    for mat in bpy.data.materials:
        if mat.node_tree is None:
            continue
        nt = mat.node_tree
        nodes = [n for n in nt.nodes]
        for n in nodes:
            new_node = None
            if n.bl_label == 'LamaDiffuse':
                new_node = nt.nodes.new('LamaDiffuseBxdfNode')
                nms = ['color', 'normal']
                copy_param(n, new_node, 'color', 'diffuseColor')
                copy_param(n, new_node, 'normal', 'diffuseNormal')
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)
            elif n.bl_label == 'LamaSheen':
                new_node = nt.nodes.new('LamaSheenBxdfNode')
                nms = ['color', 'normal']
                copy_param(n, new_node, 'color', 'sheenColor')
                copy_param(n, new_node, 'normal', 'sheenNormal')
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                
            elif n.bl_label == 'LamaConductor':
                new_node = nt.nodes.new('LamaConductorBxdfNode')
                nms = ['normal']
                copy_param(n, new_node, 'normal', 'conductorNormal')       
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                            
            elif n.bl_label == 'LamaDielectric':
                new_node = nt.nodes.new('LamaDielectricBxdfNode')
                nms = ['normal']
                copy_param(n, new_node, 'normal', 'dielectricNormal')
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                   
            elif n.bl_label == 'LamaEmission':
                new_node = nt.nodes.new('LamaEmissionBxdfNode')
                nms = ['color']
                copy_param(n, new_node, 'color', 'emissionColor')   
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                        
            elif n.bl_label == 'LamaGeneralizedSchlick':
                new_node = nt.nodes.new('LamaGeneralizedSchlickBxdfNode')
                nms = ['normal']
                copy_param(n, new_node, 'normal', 'genSchlickNormal')
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                     
            elif n.bl_label == 'LamaSSS':
                new_node = nt.nodes.new('LamaSSSBxdfNode')
                nms = ['color', 'normal']
                copy_param(n, new_node, 'color', 'sssColor')
                copy_param(n, new_node, 'normal', 'sssNormal')
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                   
            elif n.bl_label == 'LamaTranslucent':
                new_node = nt.nodes.new('LamaTranslucentBxdfNode')
                nms = ['color', 'normal']
                copy_param(n, new_node, 'color', 'translucentColor')
                copy_param(n, new_node, 'normal', 'translucentNormal')
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                   
            elif n.bl_label == 'LamaTricolorSSS':
                new_node = nt.nodes.new('LamaTricolorSSSBxdfNode')
                nms = ['normal']
                copy_param(n, new_node, 'normal', 'sssNormal')      
                for prop_name, meta in n.prop_meta.items():
                    if prop_name in nms:
                        continue
                    copy_param(n, new_node, prop_name, prop_name)                             

            if new_node:
                new_node.location[0] = n.location[0]
                new_node.location[1] = n.location[1]      
                if n.outputs['bxdf_out'].is_linked:
                    for link in n.outputs['bxdf_out'].links:
                        connected_socket = link.to_socket
                        nt.links.new(new_node.outputs['bxdf_out'], connected_socket)
                node_name = n.name
                nt.nodes.remove(n)
                new_node.name = node_name   
                new_node.select = False                       

__RMAN_SCENE_UPGRADE_FUNCTIONS__ = OrderedDict()
    
__RMAN_SCENE_UPGRADE_FUNCTIONS__['24.2'] = upgrade_242
__RMAN_SCENE_UPGRADE_FUNCTIONS__['24.3'] = upgrade_243
__RMAN_SCENE_UPGRADE_FUNCTIONS__['25.0'] = upgrade_250
__RMAN_SCENE_UPGRADE_FUNCTIONS__['25.0.1'] = upgrade_250_1

def upgrade_scene(bl_scene):
    global __RMAN_SCENE_UPGRADE_FUNCTIONS__

    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        version = scene.renderman.renderman_version
        if version == '':
            # we started adding a renderman_version property in 24.1
            version = '24.1'

        scene_major = None
        scene_minor = None
        scene_patch = None
        tokens = version.split('.')
        scene_major = tokens[0]
        scene_minor = tokens[1]
        if len(tokens) > 2:
            scene_patch = tokens[2]

        for version_str, fn in __RMAN_SCENE_UPGRADE_FUNCTIONS__.items():
            upgrade_major = None
            upgrade_minor = None
            upgrade_patch = None
            tokens = version_str.split('.')
            upgrade_major = tokens[0]
            upgrade_minor = tokens[1]
            if len(tokens) > 2:
                upgrade_patch = tokens[2]

            if scene_major < upgrade_major:
                rfb_log().debug('Upgrade scene to %s' % version_str)
                fn(scene)
                continue

            if scene_major == upgrade_major and scene_minor < upgrade_minor:
                rfb_log().debug('Upgrade scene to %s' % version_str)
                fn(scene)
                continue

            if not scene_patch and not upgrade_patch:
                continue

            if not scene_patch and upgrade_patch:
                # The scene version doesn't include a patch version
                # This is probably from an older version i.e.: < 25.0b1
                rfb_log().debug('Upgrade scene to %s' % version_str)
                fn(scene)
                continue

            if upgrade_patch and scene_patch < upgrade_patch:
                rfb_log().debug('Upgrade scene to %s' % version_str)
                fn(scene)
            
        scene.renderman.renderman_version = rman_constants.RFB_SCENE_VERSION_STRING                
               
def update_version(bl_scene):
    if bpy.context.engine != 'PRMAN_RENDER':
        return    
    for scene in bpy.data.scenes:
        scene.renderman.renderman_version = rman_constants.RFB_SCENE_VERSION_STRING