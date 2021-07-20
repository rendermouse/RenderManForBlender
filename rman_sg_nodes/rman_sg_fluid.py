from .rman_sg_node import RmanSgNode

class RmanSgFluid(RmanSgNode):

    def __init__(self, rman_scene, sg_node, db_name):
        super().__init__(rman_scene, sg_node, db_name)
        self.rman_sg_volume_node = None
        self.rman_sg_liquid_node = None