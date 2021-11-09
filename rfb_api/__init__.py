from .. import rman_config
from .. import rman_bl_nodes
import bpy
import json
import pprint
import os

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
                               
