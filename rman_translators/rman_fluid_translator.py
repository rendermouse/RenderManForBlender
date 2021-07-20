from platform import system_alias
from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_fluid import RmanSgFluid
from ..rfb_utils import transform_utils
from ..rfb_utils import string_utils
from ..rfb_utils import scenegraph_utils
from ..rfb_utils import particles_utils
from ..rfb_logger import rfb_log
import bpy
import os

def locate_openVDB_cache(cache_dir, frameNum):
    if not bpy.data.is_saved:
        return None
    cacheDir = os.path.join(bpy.path.abspath(cache_dir), 'data')
    if not os.path.exists(cacheDir):
        return None
    for f in os.listdir(cacheDir):
        if os.path.splitext(f)[1] != '.vdb':
            continue
        if 'density' in f and "%04d" % frameNum in f:
            return os.path.join(cacheDir, f)

    return None

def find_fluid_modifier(ob):
    fluid_modifier = None
    for mod in ob.modifiers:
        if mod.type == "FLUID":
            fluid_modifier = mod
            break    
    return fluid_modifier

class RmanFluidTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'FLUID' 

    def export(self, ob, db_name):

        sg_node = self.rman_scene.sg_scene.CreateGroup(db_name)
        rman_sg_fluid = RmanSgFluid(self.rman_scene, sg_node, db_name)
        if self.rman_scene.do_motion_blur:
            rman_sg_fluid.is_deforming = rman_sg_fluid._is_deforming_(ob)        

        return rman_sg_fluid

    def export_deform_sample(self, rman_sg_fluid, ob, time_sample):
        fluid_modifier = find_fluid_modifier(ob)
        fluid_data = fluid_modifier.domain_settings
        if fluid_data.domain_type == 'GAS':
            return
        psys = None
        for sys in ob.particle_systems:
            if sys.settings.type == 'FLIP':
                psys = sys
                break
        if not psys:
            return            

        sg_node = rman_sg_fluid.rman_sg_liquid_node

        rm = psys.settings.renderman
        inv_mtx = ob.matrix_world.inverted_safe()
        P, rot, width = self.get_particles(ob, psys, inv_mtx, get_width=False)

        if (len(P) < 3):
            return

        primvar = sg_node.GetPrimVars()
        primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex", time_sample)

        sg_node.SetPrimVars(primvar)   

    def clear_children(self, rman_sg_fluid):
        if rman_sg_fluid.sg_node:
            for c in [ rman_sg_fluid.sg_node.GetChild(i) for i in range(0, rman_sg_fluid.sg_node.GetNumChildren())]:
                rman_sg_fluid.sg_node.RemoveChild(c)
                self.rman_scene.sg_scene.DeleteDagNode(c)     

    def update(self, ob, rman_sg_fluid):
        rm = ob.renderman

        fluid_modifier = find_fluid_modifier(ob)
        fluid_data = fluid_modifier.domain_settings
        # the original object has the modifier too.
        if not fluid_data:
            return

        self.clear_children(rman_sg_fluid)

        if fluid_data.domain_type == 'GAS':
            rman_sg_fluid.rman_sg_liquid_node = None
            rman_sg_fluid.rman_sg_volume_node = self.rman_scene.sg_scene.CreateGroup('%s-GAS' % rman_sg_fluid.db_name)

            rman_sg_fluid.rman_sg_volume_node.sg_node.Define(0,0,0)
            if fluid_data.cache_data_format == 'OPENVDB':
                pass
                # for now, read the grids directly from the domain settings.
                # the vdb files exported from manta don't seem to follow naming conventions. 
                # ex: the name of the density grid seems to be different per frame?
                #self.update_fluid_openvdb(ob, rman_sg_fluid, fluid_data)
            
            self.update_fluid(ob, rman_sg_fluid, fluid_data)
            rman_sg_fluid.sg_node.AddChild(rman_sg_fluid.rman_sg_volume_node)
        else:
            rman_sg_fluid.rman_sg_volume_node = None
            psys = None
            for sys in ob.particle_systems:
                if sys.settings.type == 'FLIP':
                    psys = sys
                    break
            if not psys:
                return

            rman_sg_fluid.rman_sg_liquid_node = self.rman_scene.sg_scene.CreatePoints('%s-POINTS' % rman_sg_fluid.db_name)                
            self.update_fluid_particles(ob, rman_sg_fluid, psys, fluid_data)
            rman_sg_fluid.sg_node.AddChild(rman_sg_fluid.rman_sg_liquid_node)

    def update_fluid_particles(self, ob, rman_sg_fluid, psys, fluid_data):
        sg_node = rman_sg_fluid.rman_sg_liquid_node

        rm = psys.settings.renderman
        inv_mtx = ob.matrix_world.inverted_safe()
        P, rot, width = particles_utils.get_particles(ob, psys, inv_mtx, self.rman_scene.bl_scene.frame_current)

        if (len(P) < 3):
            return

        nm_pts = int(len(P)/3)
        sg_node.Define(nm_pts)          

        primvar = sg_node.GetPrimVars()
        primvar.Clear()
            
        if rman_sg_fluid.is_deforming and rman_sg_fluid.motion_steps:
            super().set_primvar_times(rman_sg_fluid.motion_steps, primvar)
        
        particles_utils.get_primvars_particle(primvar, self.rman_scene.bl_scene.frame_current, psys, [self.rman_scene.bl_scene.frame_current], 0)      
        
        primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, P, "vertex")           
        primvar.SetFloatDetail(self.rman_scene.rman.Tokens.Rix.k_width, fluid_data.particle_radius*0.005, "constant")

        sg_node.SetPrimVars(primvar)

        # Attach material
        mat_idx = psys.settings.material - 1
        if mat_idx < len(ob.material_slots):
            mat = ob.material_slots[mat_idx].material
            material_sg_node = None
            if mat:
                rman_sg_material = self.rman_scene.rman_materials.get(mat.original, None)
                if rman_sg_material:
                    material_sg_node = rman_sg_material.sg_node
            scenegraph_utils.set_material(sg_node, material_sg_node)        

    def update_fluid_openvdb(self, ob, rman_sg_fluid, fluid_data):
        cacheFile = locate_openVDB_cache(fluid_data.cache_directory, self.rman_scene.bl_frame_current)
        if not cacheFile:
            rfb_log().debug('error', "Please save and export OpenVDB files before rendering.")
            return

        primvar = rman_sg_fluid.rman_sg_volume_node.sg_node.GetPrimVars()
        primvar.SetString(self.rman_scene.rman.Tokens.Rix.k_Ri_type, "blobbydso:impl_openvdb")
        primvar.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_Bound, transform_utils.convert_ob_bounds(ob.bound_box), 6)
        primvar.SetStringArray(self.rman_scene.rman.Tokens.Rix.k_blobbydso_stringargs, [cacheFile, "density:fogvolume"], 2)

        primvar.SetFloatDetail("density", [], "varying")
        primvar.SetFloatDetail("flame", [], "varying")        
        primvar.SetColorDetail("color", [], "varying")                  
        rman_sg_fluid.rman_sg_volume_node.sg_node.SetPrimVars(primvar)             


    def update_fluid(self, ob, rman_sg_fluid, fluid_data):

        fluid_res = fluid_data.domain_resolution
        rman_sg_fluid.rman_sg_volume_node.sg_node.Define(fluid_res[0], fluid_res[1], fluid_res[2])

        primvar = rman_sg_fluid.rman_sg_volume_node.sg_node.GetPrimVars()
        primvar.SetString(self.rman_scene.rman.Tokens.Rix.k_Ri_type, "box")
        primvar.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_Bound, transform_utils.convert_ob_bounds(ob.bound_box), 6)

        primvar.SetFloatDetail("density", fluid_data.density_grid, "varying")
        primvar.SetFloatDetail("flame", fluid_data.flame_grid, "varying")   
        primvar.SetFloatDetail("heat", fluid_data.heat_grid, "varying")
        primvar.SetColorDetail("color", [item for index, item in enumerate(fluid_data.color_grid) if index % 4 != 0], "varying")
        primvar.SetVectorDetail("velocity", fluid_data.velocity_grid, "varying")
        primvar.SetFloatDetail("temperature", fluid_data.temperature_grid, "varying")

        rman_sg_fluid.rman_sg_volume_node.sg_node.SetPrimVars(primvar)     
