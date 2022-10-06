import bpy
from bpy.props import *
from ..rfb_utils import shadergraph_utils
from ..rfb_utils import draw_utils
from ..rfb_logger import rfb_log
from .. import rfb_icons
import time
import re

# update node during ipr for a socket default_value
def update_func(self, context):
    # check if this prop is set on an input
    node = self.node if hasattr(self, 'node') else self

__CYCLES_GROUP_NODES__ = ['ShaderNodeGroup', 'NodeGroupInput', 'NodeGroupOutput']
__SOCKET_HIDE_VALUE__ = ['bxdf', 'projection', 'light', 'integrator', 'struct', 'vstruct'
                        'samplefilter', 'displayfilter']


# list for socket registration
# each element in the list should be:
# 
# - renderman type (str)
# - renderman type label (str)
# - bpy.types.NodeSocket class to inherit from
# - tuple to represent the color for the socket
# - bool to indicate whether to hide the value
# - dictionary of any properties wanting to be set

__RENDERMAN_TYPES_SOCKETS__ = [
    ('float', 'Float', bpy.types.NodeSocketFloat, (0.5, 0.5, 0.5, 1.0), False,
        {
            'default_value': FloatProperty(update=update_func),
        }
    ),
    ('int', 'Int', bpy.types.NodeSocketInt, (1.0, 1.0, 1.0, 1.0), False,
        {
            'default_value': IntProperty(update=update_func),
        }
    ),
    ('string', 'String', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), False,
        {
            'default_value': StringProperty(update=update_func),
            'is_texture': BoolProperty(default=False)
        }
    ),    
    ('struct', 'Struct', bpy.types.NodeSocketString, (1.0, 0.344, 0.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
            'struct_name': StringProperty(default='')
        }
    ),  
    ('vstruct', 'VStruct', bpy.types.NodeSocketString, (1.0, 0.0, 1.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('bxdf', 'Bxdf', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('color', 'Color', bpy.types.NodeSocketColor, (1.0, 1.0, .5, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="COLOR", update=update_func),
        }
    ),     
    ('vector', 'Vector', bpy.types.NodeSocketVector, (.25, .25, .75, 1.0), False,
        {
            'default_value':FloatVectorProperty(size=3, subtype="EULER", update=update_func),
        }
    ),      
    ('normal', 'Normal', bpy.types.NodeSocketVector, (.25, .25, .75, 1.0), False,
        {
            'default_value':FloatVectorProperty(size=3, subtype="EULER", update=update_func),
        }
    ), 
    ('point', 'Point', bpy.types.NodeSocketVector, (.25, .25, .75, 1.0), False,
        {
            'default_value':FloatVectorProperty(size=3, subtype="EULER", update=update_func),
        }
    ),     
    ('light', 'Light', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),    
    ('lightfilter', 'LightFilter', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),        
    ('displacement', 'Displacement', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),       
    ('samplefilter', 'SampleFilter', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),     
    ('displayfilter', 'DisplayFilter', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),    
    ('integrator', 'Integrator', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('shader', 'Shader', bpy.types.NodeSocketShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),  
    ('projection', 'Projection', bpy.types.NodeSocketString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),                    
]

# list for socket interface registration
# each element in the list should be:
# 
# - renderman type (str)
# - renderman type label (str)
# - bpy.types.NodeSocketInterface class to inherit from
# - tuple to represent the color for the socket
# - bool to indicate whether to hide the value
# - dictionary of any properties wanting to be set

__RENDERMAN_TYPES_SOCKET_INTERFACES__ =[
    ('float', 'Float', bpy.types.NodeSocketInterfaceFloat, (0.5, 0.5, 0.5, 1.0), False,
        {
            'default_value': FloatProperty() 
        }
    ),
    ('int', 'Int', bpy.types.NodeSocketInterfaceInt, (1.0, 1.0, 1.0, 1.0), False,
        {
            'default_value': IntProperty()
        }
    ),
    ('struct', 'Struct', bpy.types.NodeSocketInterfaceString, (1.0, 0.344, 0.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
            'struct_name': StringProperty(default='')
        }
    ),  
    ('vstruct', 'VStruct', bpy.types.NodeSocketInterfaceString, (1.0, 0.0, 1.0, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('bxdf', 'Bxdf', bpy.types.NodeSocketInterfaceString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),       
    ('color', 'Color', bpy.types.NodeSocketInterfaceColor, (1.0, 1.0, .5, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="COLOR", update=update_func),
        }
    ),      
    ('vector', 'Vector', bpy.types.NodeSocketInterfaceVector, (.25, .25, .75, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="EULER")
        }
    ),         
    ('normal', 'Normal', bpy.types.NodeSocketInterfaceVector, (.25, .25, .75, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="EULER")
        }
    ),       
    ('point', 'Point', bpy.types.NodeSocketInterfaceVector, (.25, .25, .75, 1.0), False,
        {
            'default_value': FloatVectorProperty(size=3, subtype="EULER")
        }
    ),             
    ('light', 'Light', bpy.types.NodeSocketInterfaceString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),      
    ('lightfilter', 'LightFilter', bpy.types.NodeSocketInterfaceString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),     
    ('displacement', 'Displacement', bpy.types.NodeSocketInterfaceString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),     
    ('samplefilter', 'SampleFilter', bpy.types.NodeSocketInterfaceString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),    
    ('displayfilter', 'DisplayFilter', bpy.types.NodeSocketInterfaceString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),             
    ('integrator', 'Integrator', bpy.types.NodeSocketInterfaceString, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),         
    ('shader', 'Shader', bpy.types.NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ), 
    ('projection', 'Projection', bpy.types.NodeSocketInterfaceShader, (0.25, 1.0, 0.25, 1.0), True,
        {
            'default_value': StringProperty(default=''),
        }
    ),           
]

class RendermanSocket:
    ui_open: BoolProperty(name='UI Open', default=True)

    def get_pretty_name(self, node):
        if node.bl_idname in __CYCLES_GROUP_NODES__:
            return self.name
        else:
            return self.identifier

    def get_value(self, node):
        if node.bl_idname in __CYCLES_GROUP_NODES__ or not hasattr(node, self.name):
            return self.default_value
        else:
            return getattr(node, self.name)

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)

    def draw_value(self, context, layout, node):
        layout.prop(node, self.identifier)

    def draw(self, context, layout, node, text):
        
        renderman_type = getattr(self, 'renderman_type', '')
        if self.hide and self.hide_value:
            pass
        elif self.hide_value:
            layout.label(text=self.get_pretty_name(node))
        elif self.is_linked or self.is_output:
            layout.label(text=self.get_pretty_name(node))
        elif node.bl_idname in __CYCLES_GROUP_NODES__ or node.bl_idname == "PxrOSLPatternNode":
            layout.prop(self, 'default_value',
                        text=self.get_pretty_name(node), slider=True)
        elif renderman_type in __SOCKET_HIDE_VALUE__:
            layout.label(text=self.get_pretty_name(node))                        
        elif hasattr(node, self.name):
            layout.prop(node, self.name,
                        text=self.get_pretty_name(node), slider=True)
        else:
            # check if this is an array element
            expr = re.compile(r'.*(\[\d+\])')
            m = expr.match(self.name)
            if m and m.groups():
                group = m.groups()[0]
                coll_nm = self.name.replace(group, '')
                collection = getattr(node, '%s_collection' % coll_nm)
                elem = None
                for e in collection:
                    if e.name == self.name:
                        elem = e
                        break
                if elem:               
                    layout.prop(elem, 'value_%s' % elem.type, text=elem.name, slider=True)
                else:
                    layout.label(text=self.get_pretty_name(node))
            else:
                layout.label(text=self.get_pretty_name(node))

        renderman_node_type = getattr(node, 'renderman_node_type', '')
        if not self.hide and context.region.type == 'UI' and renderman_node_type != 'output':            
            nt = context.space_data.edit_tree
            layout.context_pointer_set("socket", self)
            layout.context_pointer_set("node", node)
            layout.context_pointer_set("nodetree", nt)
            rman_icon = rfb_icons.get_icon('rman_connection_menu')
            layout.menu('NODE_MT_renderman_connection_menu', text='', icon_value=rman_icon.icon_id)                
            
        mat = getattr(context, 'material')
        if mat:
            output_node = shadergraph_utils.is_renderman_nodetree(mat)
            if not output_node:
                return
            if not self.is_linked and not self.is_output:
                draw_utils.draw_sticky_toggle(layout, node, self.name, output_node)

class RendermanSocketInterface:

    def draw_color(self, context):
        return (0.25, 1.0, 0.25, 1.0)

    def draw(self, context, layout):
        layout.label(text=self.name)

    def from_socket(self, node, socket):
        if hasattr(self, 'default_value'):
            self.default_value = socket.get_value(node)
        if hasattr(self, 'struct_name'):
            self.struct_name = socket.struct_name         
        if hasattr(self, 'is_texture'):
            self.is_texture = socket.is_texture
        self.name = socket.name

    def init_socket(self, node, socket, data_path):
        time.sleep(.01)
        socket.name = self.name
        if hasattr(self, 'default_value'):
            socket.default_value = self.default_value
        if hasattr(self, 'struct_name'):
            socket.struct_name = self.struct_name   
        if hasattr(self, 'is_texture'):
            socket.is_texture = self.is_texture                     

classes = []

def register_socket_classes():
    global classes

    def draw_color(self, context, node):
        return self.socket_color

    for socket_info in __RENDERMAN_TYPES_SOCKETS__:
        renderman_type = socket_info[0]
        label = socket_info[1]
        typename = 'RendermanNodeSocket%s' % label
        ntype = type(typename, (socket_info[2], RendermanSocket,), {})
        ntype.bl_label = 'RenderMan %s Socket' % label
        ntype.bl_idname = typename
        if "__annotations__" not in ntype.__dict__:
            setattr(ntype, "__annotations__", {})        
        ntype.draw_color = draw_color
        ntype.socket_color = socket_info[3]
        ntype.__annotations__['renderman_type'] = StringProperty(default='%s' % renderman_type)
        if socket_info[4]:
            ntype.__annotations__['hide_value'] = True
        ann_dict = socket_info[5]
        for k, v in ann_dict.items():
            ntype.__annotations__[k] = v

        classes.append(ntype)

def register_socket_interface_classes():
    global classes

    def draw_socket_color(self, context):
        return self.socket_color
    
    for socket_info in __RENDERMAN_TYPES_SOCKET_INTERFACES__:
        renderman_type = socket_info[0]
        label = socket_info[1]
        typename = 'RendermanNodeSocketInterface%s' % label
        ntype = type(typename, (socket_info[2], RendermanSocketInterface,), {})        
        # bl_socket_idname needs to correspond to the RendermanNodeSocket class
        ntype.bl_socket_idname = 'RendermanNodeSocket%s' % label
        if "__annotations__" not in ntype.__dict__:
            setattr(ntype, "__annotations__", {})        
        ntype.draw_color = draw_socket_color
        ntype.socket_color = socket_info[3]
        if socket_info[4]:
            ntype.__annotations__['hide_value'] = True        
        ann_dict = socket_info[5]
        for k, v in ann_dict.items():
            ntype.__annotations__[k] = v

        classes.append(ntype)            

def register():
    from ..rfb_utils import register_utils

    register_socket_interface_classes()
    register_socket_classes()

    register_utils.rman_register_classes(classes)

def unregister():
    from ..rfb_utils import register_utils

    register_utils.rman_unregister_classes(classes)