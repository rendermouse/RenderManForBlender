def set_material(sg_node, sg_material_node):
    '''Sets the material on a scenegraph group node and sets the materialid
    user attribute at the same time.

    Arguments:
        sg_node (RixSGGroup) - scene graph group node to attach the material.
        sg_material_node (RixSGMaterial) - the scene graph material node
    '''    


    sg_node.SetMaterial(sg_material_node)
    attrs = sg_node.GetAttributes()
    attrs.SetString('user:__materialid', sg_material_node.GetIdentifier().CStr())
    sg_node.SetAttributes(attrs) 

def update_sg_integrator(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_integrator(context)            

def update_sg_options(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_global_options(context)   

def update_sg_root_node(context):
    from .. import rman_render
    rr = rman_render.RmanRender.get_rman_render()
    rr.rman_scene_sync.update_root_node_func(context)    