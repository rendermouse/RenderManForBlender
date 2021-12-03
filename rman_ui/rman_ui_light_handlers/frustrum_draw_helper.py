import math
from ...rfb_logger import rfb_log

POS = [[-0.5, 0.5, 0.0], [0.5, 0.5, 0.0], [0.5, -0.5, 0.0], [-0.5, -0.5, 0.0]]

def _gl_lines(idx_buffer, vtxbuf_start_idx, num_vtx, start_idx, loop=False):
    """Fills the index buffer to draw a number of lines.

    Args:
    - idx_buffer (lise): A pre-initialized index buffer to fill. May already contain valid data.
    - vtxbuf_start_idx (int): index of the primitive's first vertex in the vertex buffer.
    - num_vtx (int): number of vertices in the primitive
    - start_idx (p1_type): position of our first write in the index buffer.

    Kwargs:
    - loop:  add a line from the last vertex to the first one if True.
    """
    # print ('      _gl_lines(%s, vtxbuf_start_idx=%d, num_vtx=%d, start_idx=%d, loop=%s)'
    #        % (idx_buffer, vtxbuf_start_idx, num_vtx, start_idx, loop))
    num_indices = num_vtx * 2
    if not loop:
        num_indices -= 2
    vtx_idx = vtxbuf_start_idx
    last_idx = start_idx + num_indices - 2
    for i in range(start_idx, start_idx + num_indices, 2):
        idx_buffer[i] = vtx_idx
        if i == last_idx and loop:
            idx_buffer[i + 1] = vtxbuf_start_idx
        else:
            idx_buffer[i + 1] = vtx_idx + 1
        vtx_idx += 1


class Frustum(object):

    def __init__(self, *args, **kwargs):
        self.depth = 5.0
        self._opacity = 0.333

    def update_input_params(self, *args, **kwargs):
        self.method = kwargs.get('method', 'rect')
        self.base_shape = self._build_base_shape()
        self.angle = kwargs.get('coneAngle', 90.0)
        self.softness = kwargs.get('coneSoftness', 0.0)        

    def disk_vtx_buffer(self):
        vtxs = []
        subdivs = 32
        radius = 0.5
        pos = [0.0, 0.0, 0.0]      
        theta_step = 2.0 * math.pi / float(subdivs)

        # default with z axis
        idx1 = 0
        idx2 = 1

        # compute
        for i in range(subdivs):
            theta = float(i) * theta_step
            p = [pos[0], pos[1], pos[2]]
            p[idx1] = radius * math.cos(theta) + pos[idx1]
            p[idx2] = radius * math.sin(theta) + pos[idx2]
            vtxs.append(p)
        # vtxs.append(vtxs[0])

        return vtxs        

    def rect_vtx_buffer(self):
        """Return a list of vertices (list) in local space."""
        vtxs = []
        for i in range(len(POS)):
            vtx = [POS[i][0],
                   POS[i][1],
                   POS[i][2]]

            vtxs.append(vtx)

        return vtxs        

    def _build_base_shape(self):
        if self.method == 'rect':
            return self.rect_vtx_buffer()
        elif self.method == 'disk':
            return self.disk_vtx_buffer()
        else:
            raise RuntimeError("Unknown base shape method.")

    def vtx_buffer_count(self):
        """Return the number of vertices in this buffer."""
        return len(self.base_shape) * 3 + 4

    def vtx_buffer(self):
        """Return a list of vertices (list) in local space.

        Use the vtx_list (the original light shape) to build the outer coneAngle
        at the specified depth.
        """

        if self.angle >= 90.0:
            # do not draw
            return [[0.0, 0.0, 0.0]] * self.vtx_buffer_count()

        # print 'frustum.vtx_buffer()'
        # print '   |__ base shape'
        # for v in self.base_shape:
        #     print '       |__ %s' % v

        # far shape
        # print '   |__ far angle'
        vertices = []
        rad = math.radians(self.angle)
        d = 1.0 + max(0.0, self.depth)
        rscale = 1.0 + math.tan(rad) * 2.0 * d
        for vtx in self.base_shape:
            x = vtx[0] * rscale
            y = vtx[1] * rscale
            z = vtx[2] - d
            vertices.append([x, y, z])
            # print '       |__ #%02d:  %0.2f  %0.2f  %0.2f' % (len(vertices)-1,
            #                                                   x, y, z)

        # far softness
        # print '   |__ far softness'
        soft_scale = 1.0 - self.softness
        for vtx in self.base_shape:
            x = vtx[0] * rscale * soft_scale
            y = vtx[1] * rscale * soft_scale
            z = vtx[2] - d
            vertices.append([x, y, z])
            # print '       |__ #%02d:  %0.2f  %0.2f  %0.2f' % (len(vertices)-1,
            #                                                   x, y, z)

        # near softness
        # print '   |__ near softness'
        for vtx in self.base_shape:
            vertices.append([vtx[0] * soft_scale,
                             vtx[1] * soft_scale,
                             vtx[2]])
            # print '       |__ #%02d:  %0.2f  %0.2f  %0.2f' % (len(vertices)-1,
            #                                                   vertices[-1][0],
            #                                                   vertices[-1][1],
            #                                                   vertices[-1][2])

        # frustum edges
        # print '   |__ edges'
        num_vtx = len(self.base_shape)
        vtx_step = num_vtx // 4
        for i in range(0, num_vtx, vtx_step):
            vertices.append(self.base_shape[i])
            # print '       |__ #%02d:  %0.2f  %0.2f  %0.2f' % (len(vertices)-1,
            #                                                   vertices[-1][0],
            #                                                   vertices[-1][1],
            #                                                   vertices[-1][2])

        return vertices

    def idx_buffer(self, num_vtx, start_idx, inst_idx):
        """
        Fill the provided index buffer to draw the shape.

        Args:
        - num_vtx (int): The total number of vertices in the VBO.
        - startIdx (int): the index of our first vtx in the VBO
        - item_idx (int): 0 = outer frustum, 1 = inner frustum, 2 = frustum edges
        """
        # print 'idx_buffer: %s' % self.__class__
        # print('>> frustum.idx_buffer(%s, %d, %d, %d)' %
        #       (idx_buffer, num_vtx, start_idx, inst_idx))

        # 3 shapes in the frustum with same number of vtxs. Plus 4 edges.
        grp_n_vtx = (num_vtx - 4) // 3

        num_indices_per_shape = [grp_n_vtx * 2,
                                 grp_n_vtx * 2 * 2,
                                 4 * 2]

        n_indices = num_indices_per_shape[0] + \
                    num_indices_per_shape[1] + \
                    num_indices_per_shape[2]
        # print '   |__ generating %s indices' % n_indices
        indices = list([None] * n_indices)

        for item_idx in range(3):

            if item_idx == 0:
                # angle: far shape
                _gl_lines(indices, start_idx, grp_n_vtx, 0, loop=True)

            elif item_idx == 1:
                # softness: far shape
                _gl_lines(indices, start_idx + grp_n_vtx,
                          grp_n_vtx, grp_n_vtx * 2, loop=True)
                # softness: near shape
                _gl_lines(indices, start_idx + grp_n_vtx *2,
                          grp_n_vtx, grp_n_vtx * 4, loop=True)
            elif item_idx == 2:
                # edges
                in_idx = grp_n_vtx * 3 * 2
                # frustum edges
                # we need to create 4 equi-distant lines from the far angle
                # shape to the base shape.
                stride = grp_n_vtx // 4
                ofst = (grp_n_vtx * 3)
                near_vtx_idx = start_idx + ofst
                far_vtx_idx = start_idx
                # print '   |__ frustum'
                for i in range(in_idx, in_idx + num_indices_per_shape[2], 2):
                    indices[i] = near_vtx_idx
                    indices[i + 1] = far_vtx_idx
                    # print '       |__ %d -> %d' % (indices[i], indices[1+1])
                    near_vtx_idx += 1
                    far_vtx_idx += stride

            else:
                print('WARNING: unknown item_idx: %s' % item_idx)

        indices = [indices[i:i+2] for i in range(0, len(indices), 2)]
        return indices

    def opacity(self):
        return self._opacity

    def instance_enabled(self, instance_idx):
        """Return the enable state of the instance/MRenderItem, potentially
        taking named params into account."""
        return self.angle < 90.0

    def set_input_params(self, obj, **kwargs):
        """Update internal input param values using kwargs."""
        # print 'frustum.set_input_params(%s)' % kwargs
        self.angle = kwargs.get('coneAngle', 90.0)
        self.softness = kwargs.get('coneSoftness', 0.0)
        self.depth = kwargs.get('rman_coneAngleDepth', 10.0)
        self._opacity = kwargs.get('rman_coneAngleOpacity', 0.333)