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
        self.bl_hair_attributes = []

class BlHairAttribute:

    def __init__(self):
        self.rman_type = ''
        self.rman_name = ''
        self.rman_detail = None
        self.values = []

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
            
            for hair_attr in bl_curve.bl_hair_attributes:
                if hair_attr.rman_detail is None:
                    continue
                if hair_attr.rman_type == "float":
                    primvar.SetFloatDetail(hair_attr.rman_name, hair_attr.values, hair_attr.rman_detail)
                elif hair_attr.rman_type == "float2":
                    primvar.SetFloatArrayDetail(hair_attr.rman_name, hair_attr.values, 2, hair_attr.rman_detail)
                elif hair_attr.rman_type == "vector":
                    primvar.SetVectorDetail(hair_attr.rman_name, hair_attr.values, hair_attr.rman_detail)
                elif hair_attr.rman_type == 'color':
                    primvar.SetColorDetail(hair_attr.rman_name, hair_attr.values, hair_attr.rman_detail)
                elif hair_attr.rman_type == 'integer':
                    primvar.SetIntegerDetail(hair_attr.rman_name, hair_attr.values, hair_attr.rman_detail)
                    
            curves_sg.SetPrimVars(primvar)
            rman_sg_hair.sg_node.AddChild(curves_sg)  
            rman_sg_hair.sg_curves_list.append(curves_sg)
        
    def add_object_instance(self, rman_sg_hair, rman_sg_group):
        rman_sg_hair.sg_node.AddChild(rman_sg_group.sg_node)                
        rman_sg_hair.instances[rman_sg_group.db_name] = rman_sg_group
        rman_sg_group.rman_sg_group_parent = rman_sg_hair

    def get_attributes(self, ob, bl_curve):
        for attr in ob.data.attributes:
            if attr.name in ['position']:
                continue
            hair_attr = None
            if attr.data_type == 'FLOAT2':
                hair_attr = BlHairAttribute()
                hair_attr.rman_name = attr.name
                hair_attr.rman_type = 'float2'

                npoints = len(attr.data)
                values = np.zeros(npoints*2, dtype=np.float32)
                attr.data.foreach_get('vector', values)
                values = np.reshape(values, (npoints, 2))
                hair_attr.values = values.tolist()

            elif attr.data_type == 'FLOAT_VECTOR':
                hair_attr = BlHairAttribute()
                hair_attr.rman_name = attr.name
                hair_attr.rman_type = 'vector'

                npoints = len(attr.data)
                values = np.zeros(npoints*3, dtype=np.float32)
                attr.data.foreach_get('vector', values)
                values = np.reshape(values, (npoints, 3))
                hair_attr.values = values.tolist()
            
            elif attr.data_type in ['BYTE_COLOR', 'FLOAT_COLOR']:
                hair_attr = BlHairAttribute()
                hair_attr.rman_name = attr.name
                if attr.name == 'color':
                    hair_attr.rman_name = 'Cs'
                hair_attr.rman_type = 'color'

                npoints = len(attr.data)
                values = np.zeros(npoints*4, dtype=np.float32)
                attr.data.foreach_get('color', values)
                values = np.reshape(values, (npoints, 4))
                hair_attr.values .extend(values[0:, 0:3].tolist())

            elif attr.data_type == 'FLOAT':
                hair_attr = BlHairAttribute()
                hair_attr.rman_name = attr.name
                hair_attr.rman_type = 'float'
                hair_attr.array_len = -1

                npoints = len(attr.data)
                values = np.zeros(npoints, dtype=np.float32)
                attr.data.foreach_get('value', values)
                hair_attr.values = values.tolist()                          
            elif attr.data_type in ['INT8', 'INT']:
                hair_attr = BlHairAttribute()
                hair_attr.rman_name = attr.name
                hair_attr.rman_type = 'integer'
                hair_attr.array_len = -1

                npoints = len(attr.data)
                values = np.zeros(npoints, dtype=np.int)
                attr.data.foreach_get('value', values)
                hair_attr.values = values.tolist()                
            
            if hair_attr:
                bl_curve.bl_hair_attributes.append(hair_attr)
                if len(attr.data) == len(ob.data.curves):
                    hair_attr.rman_detail = 'uniform'
                elif len(attr.data) == len(ob.data.points):
                    hair_attr.rman_detail = 'vertex'        

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
            if np.count_nonzero(widths) == 0:
                # radius is 0. Default to 0.005
                widths.fill(0.005)
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
                self.get_attributes(ob, bl_curve)
                curve_sets.append(bl_curve)
                bl_curve = BlHair()

        if bl_curve.nverts > 0:       
            self.get_attributes(ob, bl_curve)
            curve_sets.append(bl_curve)

        return curve_sets              
            