from bpy.props import BoolProperty, PointerProperty, StringProperty, EnumProperty

from ...rfb_logger import rfb_log 
from ...rman_config import RmanBasePropertyGroup
from ...rfb_utils import filepath_utils
import os
import bpy

class RendermanVolumeGeometrySettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    
    def check_openvdb(self):
        ob = bpy.context.object
        if ob.type != 'VOLUME':
            return False        
        volume = bpy.context.volume
        openvdb_file = filepath_utils.get_real_path(volume.filepath)
        return os.path.exists(openvdb_file)

    has_openvdb: BoolProperty(name='', get=check_openvdb)

    def get_velocity_grids(self, context):
        ob = context.object
        items = []
        items.append(('__NONE__', 'None', ''))
        if ob.type != 'VOLUME':
            return items
        volume = ob.data
        grids = volume.grids            
        for i, grid in enumerate(grids):
            if grid.data_type in ['VECTOR_FLOAT', 'VECTOR_DOUBLE', 'VECTOR_INT']:
                items.append((grid.name, grid.name, ''))
                
        return items

    openvdb_velocity_grid_name: EnumProperty(name="Velocity Grid", items=get_velocity_grids)

classes = [         
    RendermanVolumeGeometrySettings
]           

def register():

    for cls in classes:
        cls._add_properties(cls, 'rman_properties_volume')
        bpy.utils.register_class(cls)  

    bpy.types.Volume.renderman = PointerProperty(
        type=RendermanVolumeGeometrySettings,
        name="Renderman Voume Geometry Settings")

def unregister():

    del bpy.types.Volume.renderman

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            rfb_log().debug('Could not unregister class: %s' % str(cls))
            pass