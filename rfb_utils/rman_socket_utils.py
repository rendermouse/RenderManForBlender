from ..rman_constants import RFB_ARRAYS_MAX_LEN, __RMAN_SOCKET_MAP__
from .shadergraph_utils import has_lobe_enable_props
from .property_utils import __LOBES_ENABLE_PARAMS__

def update_inputs(node):
    if node.bl_idname == 'PxrMeshLightLightNode':
        return
    for prop_name in node.prop_names:
        page_name = prop_name
        if node.prop_meta[page_name]['renderman_type'] == 'page':
            for prop_name in getattr(node, page_name):
                if prop_name in __LOBES_ENABLE_PARAMS__:
                    recursive_enable_inputs(node, getattr(
                        node, page_name), getattr(node, prop_name))
                    break

def recursive_enable_inputs(node, prop_names, enable=True):
    for prop_name in prop_names:
        if type(prop_name) == str and node.prop_meta[prop_name]['renderman_type'] == 'page':
            recursive_enable_inputs(node, getattr(node, prop_name), enable)
        elif hasattr(node, 'inputs') and prop_name in node.inputs:
            node.inputs[prop_name].hide = not enable
        else:
            continue

def find_enable_param(params):
    for prop_name in params:
        if prop_name in __LOBES_ENABLE_PARAMS__:
            return prop_name

def node_add_input(node, param_type, param_name, meta, param_label):
    if param_type not in __RMAN_SOCKET_MAP__:
        return

    socket = node.inputs.new(
        __RMAN_SOCKET_MAP__[param_type], param_name, identifier=param_label)
    socket.link_limit = 1

    if param_type in ['struct',  'vstruct', 'void']:
        socket.hide_value = True
        if param_type == 'struct':
            struct_name = meta.get('struct_name', 'Manifold')
            socket.struct_name = struct_name    
    return socket

def node_add_inputs(node, node_name, prop_names, first_level=True, label_prefix='', remove=False):
    ''' Add new input sockets to this ShadingNode
    '''

    for name in prop_names:
        meta = node.prop_meta[name]
        param_type = meta['renderman_type']

        socket = node.inputs.get(name, None)
        if socket:
            if remove:
                node.inputs.remove(socket)
            continue
        notconnectable = meta.get('__noconnection', False)
        
        # if this is a page recursively add inputs
        if param_type == 'page':
            if first_level and has_lobe_enable_props(node) and name != 'page_Globals':
                # add these
                label = meta.get('label', name)
                enable_param = find_enable_param(getattr(node, name))
                if enable_param and getattr(node, enable_param):
                    node_add_inputs(node, node_name, getattr(node, name),
                                    label_prefix=label + ' ',
                                    first_level=False)
                else:
                    node_add_inputs(node, node_name, getattr(node, name),
                                    label_prefix=label + ' ',
                                    first_level=False, remove=True)
            else:
                node_add_inputs(node, node_name, getattr(node, name),
                                first_level=first_level,
                                label_prefix=label_prefix, remove=remove)
            continue
        elif param_type == 'array':
            if notconnectable:
                continue
            coll_nm = '%s_collection' % name
            param_array_type = meta.get('renderman_array_type')

            collection = getattr(node, coll_nm)
            for i in range(len(collection)):
                param_array_name = '%s[%d]' % (name, i)
                param_array_label = '%s[%d]' % (name, i)
                param_array_label = label_prefix + meta.get('label', name) + '[%d]' % i
                if param_array_name in node.inputs.keys():
                    if remove:
                        node.inputs.remove(node.inputs[param_array_name])   
                    continue          
                node_add_input(node, param_array_type, param_array_name, meta, param_array_label)

            continue

        if remove or notconnectable:
            continue
        param_name = name
        param_label = label_prefix + meta.get('label', param_name)
        node_add_input(node, param_type, param_name, meta, param_label)

    update_inputs(node)


# add output sockets
def node_add_outputs(node):
    for name, meta in node.output_meta.items():
        rman_type = meta['renderman_type']
        is_vstruct = meta.get('vstruct', False)
        if rman_type in __RMAN_SOCKET_MAP__ and 'vstructmember' not in meta:
            if is_vstruct:
                rman_type = 'vstruct'
            socket = node.outputs.new(__RMAN_SOCKET_MAP__[rman_type], name)
            socket.renderman_type = rman_type
            if rman_type == 'struct':
                struct_name = meta.get('struct_name', 'Manifold')
                socket.struct_name = struct_name