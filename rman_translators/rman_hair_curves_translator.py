from .rman_translator import RmanTranslator
from ..rfb_utils import transform_utils
from ..rfb_utils import scenegraph_utils
from ..rfb_logger import rfb_log
from ..rman_sg_nodes.rman_sg_haircurves import RmanSgHairCurves
from mathutils import Vector
import math
import bpy    
import numpy as np

class BlHair:

    def __init__(self):        
        self.points = []
        self.next_points = []
        self.vertsArray = []
        self.scalpST = []
        self.mcols = []
        self.nverts = 0
        self.hair_width = []
        self.index = []

    @property
    def constant_width(self):
        return (len(self.hair_width) < 2)

class RmanHairCurvesTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'CURVES'  

    def export(self, ob, db_name):

        sg_node = self.rman_scene.sg_scene.CreateGroup(db_name)
        rman_sg_hair = RmanSgHairCurves(self.rman_scene, sg_node, db_name)

        return rman_sg_hair

    def clear_children(self, ob, rman_sg_hair):
        if rman_sg_hair.sg_node:
            for c in [ rman_sg_hair.sg_node.GetChild(i) for i in range(0, rman_sg_hair.sg_node.GetNumChildren())]:
                rman_sg_hair.sg_node.RemoveChild(c)
                self.rman_scene.sg_scene.DeleteDagNode(c)     
                rman_sg_hair.sg_curves_list.clear()   

    def export_deform_sample(self, rman_sg_hair, ob, time_sample):
        curves = self._get_strands_(ob)
        for i, bl_curve in enumerate(curves):
            curves_sg = rman_sg_hair.sg_curves_list[i]
            if not curves_sg:
                continue
            primvar = curves_sg.GetPrimVars()

            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.points, "vertex", time_sample)  
            curves_sg.SetPrimVars(primvar)

    def update(self, ob, rman_sg_hair):
        if rman_sg_hair.sg_node:
            if rman_sg_hair.sg_node.GetNumChildren() > 0:
                self.clear_children(ob, rman_sg_hair)

        curves = self._get_strands_(ob)
        if not curves:
            return

        for i, bl_curve in enumerate(curves):
            curves_sg = self.rman_scene.sg_scene.CreateCurves("%s-%d" % (rman_sg_hair.db_name, i))
            curves_sg.Define(self.rman_scene.rman.Tokens.Rix.k_cubic, "nonperiodic", "catmull-rom", len(bl_curve.vertsArray), len(bl_curve.points))
            primvar = curves_sg.GetPrimVars()                  
            primvar.SetPointDetail(self.rman_scene.rman.Tokens.Rix.k_P, bl_curve.points, "vertex")

            primvar.SetIntegerDetail(self.rman_scene.rman.Tokens.Rix.k_Ri_nvertices, bl_curve.vertsArray, "uniform")
            index_nm = 'index'
            primvar.SetIntegerDetail(index_nm, bl_curve.index, "uniform")

            width_detail = "vertex" 
            primvar.SetFloatDetail(self.rman_scene.rman.Tokens.Rix.k_width, bl_curve.hair_width, width_detail)
            
            '''
            if len(bl_curve.scalpST):
                primvar.SetFloatArrayDetail("scalpST", bl_curve.scalpST, 2, "uniform")

            if len(bl_curve.mcols):
                primvar.SetColorDetail("Cs", bl_curve.mcols, "uniform")
            '''
                    
            curves_sg.SetPrimVars(primvar)
            rman_sg_hair.sg_node.AddChild(curves_sg)  
            rman_sg_hair.sg_curves_list.append(curves_sg)
        
    def add_object_instance(self, rman_sg_hair, rman_sg_group):
        rman_sg_hair.sg_node.AddChild(rman_sg_group.sg_node)                
        rman_sg_hair.instances[rman_sg_group.db_name] = rman_sg_group
        rman_sg_group.rman_sg_group_parent = rman_sg_hair

    def _get_strands_(self, ob):

        curve_sets = []
        bl_curve = BlHair()
        db = ob.data
        for curve in db.curves:
            if curve.points_length < 4:
                continue

            npoints = len(curve.points)
            strand_points = np.zeros(npoints*3, dtype=np.float32)
            widths = np.zeros(npoints, dtype=np.float32)
            curve.points.foreach_get('position', strand_points)
            curve.points.foreach_get('radius', widths)
            strand_points = np.reshape(strand_points, (npoints, 3))
            widths = widths * 2
            strand_points = strand_points.tolist()
            widths = widths.tolist()

            '''
            # do we really need to double the end points?
            strand_points = strand_points[:1] + \
                strand_points + strand_points[-1:]

            widths = widths[:1] + widths + widths[-1:]
            '''
            vertsInStrand = len(strand_points)

            bl_curve.points.extend(strand_points)
            bl_curve.vertsArray.append(vertsInStrand)
            bl_curve.hair_width.extend(widths)
            bl_curve.index.append(curve.index)
            bl_curve.nverts += vertsInStrand
               
            # if we get more than 100000 vertices, start a new BlHair.  This
            # is to avoid a maxint on the array length
            if bl_curve.nverts > 100000:
                curve_sets.append(bl_curve)
                bl_curve = BlHair()

        if bl_curve.nverts > 0:       
            curve_sets.append(bl_curve)

        return curve_sets              
            