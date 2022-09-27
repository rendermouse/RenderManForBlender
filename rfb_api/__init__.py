from .. import rman_config
from .. import rman_bl_nodes
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import object_utils
from ..rfb_logger import rfb_log
import bpy
import os
import json

def create_light(node_type):
    '''Create a RenderMan light

    Arguments:
        node_type (str) - name of the RenderMan light caller wants to create (ex: PxrRectLight)

    Returns:
        (bpy.types.Object, bpy.types.Node) - the light object and light shader node

    '''
    bpy.ops.object.rman_add_light(rman_light_name=node_type)   
    ob = bpy.context.object
    shader = ob.data.renderman.get_light_node()
    return (ob, shader)

def create_lightfilter(node_type):
    '''Create a RenderMan light filter

    Arguments:
        node_type (str) - name of the RenderMan light filter caller wants to create (ex: PxrRectLight)

    Returns:
        (bpy.types.Object, bpy.types.Node) - the lightfilter object and lightfilter shader node

    '''
    bpy.ops.object.rman_add_light_filter(rman_lightfilter_name=node_type, add_to_selected=False)   
    ob = bpy.context.object
    shader = ob.data.renderman.get_light_node()
    return (ob, shader)    

def attach_lightfilter(light, lightfilter):
    '''Attach a lightfilter to a light

    Arguments:
        light (bpy.types.Object) - light object
        lightfilter (bpy.types.Object) - lightfilter object

    Returns:
        (bpy.types.Object, bpy.types.Node) - the lightfilter object and lightfilter shader node

    '''    
    rman_type = object_utils._detect_primitive_(light)
    if rman_type == 'LIGHT':
        light_filter_item = light.data.renderman.light_filters.add()
        light_filter_item.linked_filter_ob = lightfilter
    elif shadergraph_utils.is_mesh_light(light):
        mat = light.active_material
        if mat:
            light_filter_item = mat.renderman_light.light_filters.add()
            light_filter_item.linked_filter_ob = lightfilter     

def create_monkey(as_subdiv=False):
    '''Create a Suzanne model


    Arguments:
        as_subdiv (bool) - whether to convert to a subdivision mesh

    Returns:
        (bpy.types.Object)

    '''
    bpy.ops.mesh.primitive_monkey_add()
    ob = bpy.context.object    
    if as_subdiv:
        bpy.ops.mesh.rman_convert_subdiv() 
    return ob

def create_openvdb_node(openvdb=None):    
    '''Import an OpenVDB file.

    Arguments:
        openvdb (str) - full path to an OpeVDB file

    Returns:
        (bpy.types.Object)

    '''
    if not os.path.exists(openvdb):
        return None

    bpy.ops.object.rman_add_rman_geo('EXEC_DEFAULT', rman_default_name='OpenVDB', rman_prim_type='', bl_prim_type='VOLUME', filepath=openvdb, rman_convert_to_zup=True)
    ob = bpy.context.object
    return ob

def create_volume_box():    
    '''Create a volume box.

    Returns:
        (bpy.types.Object)

    '''

    bpy.ops.object.rman_add_rman_geo('EXEC_DEFAULT', rman_default_name='RiVolume', rman_prim_type='RI_VOLUME', bl_prim_type='')
    ob = bpy.context.object
    return ob    

def create_ribarchive_node(ribarchive=None):    
    '''Import a RIB archive file.

    Arguments:
        ribarchive (str) - full path to an RIB archive file

    Returns:
        (bpy.types.Object)

    '''
    if not os.path.exists(ribarchive):
        return None

    bpy.ops.object.rman_add_rman_geo('EXEC_DEFAULT', rman_default_name='RIB_Archive', rman_prim_type='DELAYED_LOAD_ARCHIVE', bl_prim_type='', filepath=ribarchive, rman_convert_to_zup=False)
    ob = bpy.context.object
    return ob    

def create_alembic_node(alembic=None):    
    '''Import an alembic file (delayed).

    Arguments:
        alembic (str) - full path to an Alembic file

    Returns:
        (bpy.types.Object)

    '''
    if not os.path.exists(alembic):
        return None

    bpy.ops.object.rman_add_rman_geo('EXEC_DEFAULT', rman_default_name='rman_AlembicArchive', rman_prim_type='ALEMBIC', bl_prim_type='', filepath=alembic, rman_convert_to_zup=True)
    ob = bpy.context.object
    return ob        

def create_bxdf(node_type):
    '''Create a bxdf shader node and material


    Arguments:
        node_type (str) - name of the Bxdf you want to create (ex: PxrSurface)
        ob (bpy.types.Object) - optional object to attach material to

    Returns:
        (bpy.types.Material, bpy.types.Node) - material and bxdf node

    '''    
    material = shadergraph_utils.create_bxdf(node_type)
    nt = material.node_tree    
    output = shadergraph_utils.find_node_from_nodetree(nt, 'RendermanOutputNode')
    bxdf = output.inputs[0].links[0].from_node
    return (material, bxdf)

def attach_material(material, ob):
    '''Attach material to object


    Arguments:
        node_type (bpy.types.Material) - material
        ob (bpy.types.Object) - object to attach material to

    Returns:
        (bool) - True if material attached. False otherwise

    '''   
    try:
        if ob.type == 'EMPTY':     
            ob.renderman.rman_material_override = material
        else:
            ob.active_material = material    
    except:
        return False
    return True

def create_pattern(node_type, material):
    '''Create a pattern node


    Arguments:
        node_type (str) - name of the pattern node you want to create (ex: PxrChecker)
        material (bpy.types.Material) - material to create the pattern node in

    Returns:
        (bpy.types.Node) - pattern node

    '''  
    nt = material.node_tree
    pattern = nt.nodes.new('%sPatternNode' % node_type)
    return pattern

def connect_nodes(output_node, output_socket, input_node, input_socket):
    '''Connect shading nodes

    Example:
        import RenderManForBlender.rfb_api as rfb_api

        # create material and bxdf
        material, bxdf = rfb_api.create_bxdf('PxrDisneyBsdf')
        
        # create PxrChecker pattern node
        checker = rfb_api.create_pattern('PxrChecker', material)
        checker.colorB = (0.0, 1.0, 0.4)
        
        # connect PxrChecker to Bxdf        
        rfb_api.connect_nodes(checker, 'resultRGB', bxdf, 'baseColor')


    Arguments:
        output_node (bpy.types.Node) - output node
        output_socket (str) - output node socket name
        input_node (bpy.types.Node) - input node
        input_socket (str) - input node socket name        

    Returns:
        (bool) - True if connection was successful. False otherwise.

    '''      
    if output_node.id_data != input_node.id_data:
        rfb_log().error("%s and %s are from different node trees" % (output_node.name, input_node.name))
        return False
    if output_socket not in output_node.outputs:
        rfb_log().error("%s does not have output %s" % (output_node.name, output_socket))
        return False
    if input_socket not in input_node.inputs:
        rfb_log().error("%s does not have input %s" % (input_node.name, input_socket))
        return False
        
    nt = output_node.id_data
    nt.links.new(output_node.outputs[output_socket], input_node.inputs[input_socket])    

    return True

def get_node_inputs(node):
    '''
    Return a list of the node's inputs' names

    Arguments:
        node (bpy.types.Node) - the shading node we want to interrogate

    Returns:
        (list) - the list of names of the node's inputs

    '''
    return node.inputs.keys()

def get_node_outputs(node):
    '''
    Return a list of the node's outputs' names

    Arguments:
        node (bpy.types.Node) - the shading node we want to interrogate

    Returns:
        (list) - the list of names of the node's outputs

    '''    
    return node.outputs.keys()


def GetConfigurablePanels():
    '''Return the names of RenderForBlender panels that are configurable.

    Example:
        import RenderManForBlender.rfb_api as rfb_api
        rfb_api.GetConfigurablePanels()

    Returns:
        (dict)

    '''

    panels = dict()
    for config_name,cfg in rman_config.__RMAN_CONFIG__.items():
        for param_name, ndp in cfg.params.items():
            panel = getattr(ndp, 'panel', '')
            if panel == '':
                continue
            if panel not in panels:
                #panels.append(ndp.panel)
                cls = getattr(bpy.types, panel)
                panels[panel] = { 'bl_label': cls.bl_label }
    print("RenderMan Configurable Panels")
    print("------------------------------")
    for panel, props in panels.items():
        print("%s (%s)" % (panel, props['bl_label']))
    print("------------------------------\n")
    return panels

def GetConfigurablePanelProperties(panel):
    '''Return all properties in a given panel that are configurable.

    Example:
        import RenderManForBlender.rfb_api as rfb_api
        rfb_api.GetConfigurablePanelProperties('RENDER_PT_renderman_sampling')  

    Args:
        panel (str) - the name of the panel caller is interested in

    Returns:
        (dict)
    '''
    props = dict()
    for config_name,cfg in rman_config.__RMAN_CONFIG__.items():
        for param_name, ndp in cfg.params.items():
            if not hasattr(ndp, 'panel'):
                continue
            if ndp.panel == panel:
                label = ndp.name
                if hasattr(ndp, 'label'):
                    label = ndp.label
                props[label] = ndp.name
    print("Configurable Properties (%s)" % panel)
    print("------------------------------")
    for label, prop in props.items():
        print("%s (%s)" % (prop, label))
    print("------------------------------\n")
    return props

def GetPanelPropertyAsJson(panel, prop):
    '''Get a configurable panel property as JSON

    Example:
        import RenderManForBlender.rfb_api as rfb_api
        rfb_api.GetPanelPropertyAsJson('RENDER_PT_renderman_sampling', 'hider_maxSamples')

    Args:
        panel (str) - the name of the panel caller is interested in
        prop (str) - property name caller is interested in
    '''

    json_str = ''
    for config_name,cfg in rman_config.__RMAN_CONFIG__.items():
        for param_name, ndp in cfg.params.items():
            if not hasattr(ndp, 'panel'):
                continue
            if ndp.panel == panel and ndp.name == prop:
                json_str = json.dumps(ndp.as_dict())
                break
    return json_str

def GetSkeletonLocaleJson(jsonfile=None):
    '''Get a skeleton JSON locale file

    Example:
        import RenderManForBlender.rfb_api as rfb_api
        rfb_api.GetSkeletonLocaleJson()

    Args:
        jsonfile (str): path to a file to also write the JSON to

    '''

    from ..rman_bl_nodes import __RMAN_NODES__

    json_str = ''
    jdata = dict()
    jdata['locale'] = '[name of your locale]'
    translations = dict()
    for config_name,cfg in rman_config.__RMAN_CONFIG__.items():
        for param_name, ndp in cfg.params.items():
            label = ndp.name
            label = getattr(ndp, 'label', label)
            translations[label] = {"context": "*", "translation": ""} 
            help = getattr(ndp, 'help', None)
            if help:
                translations[help] = {"context": "*", "translation": ""} 

    for nm, nodes in __RMAN_NODES__.items():
        for node_desc in nodes:
            description = getattr(node_desc, 'help', None)
            if description:
                translations[help] = {"context": "*", "translation": ""} 

            for ndp in node_desc.params:
                label = ndp.name
                label = getattr(ndp, 'label', label)
                translations[label] = {"context": "*", "translation": ""} 
                help = getattr(ndp, 'help', None)
                if help:
                    translations[help] = {"context": "*", "translation": ""}                 

    jdata['translations'] = translations
    json_str = json.dumps(jdata, indent=2)

    if jsonfile:
        with open(jsonfile, 'w') as f:
            json.dump(jdata, f, indent=2)

    return json_str    
                               
