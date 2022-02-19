import rman
from mathutils import Matrix,Vector

def convert_matrix(m):
    v = [m[0][0], m[1][0], m[2][0], m[3][0],
        m[0][1], m[1][1], m[2][1], m[3][1],
        m[0][2], m[1][2], m[2][2], m[3][2],
        m[0][3], m[1][3], m[2][3], m[3][3]]

    return v    

def convert_matrix4x4(m):
    mtx = m
    if len(m) == 4:
        # convert this to a flat list
        mtx = convert_matrix( m )
    rman_mtx = rman.Types.RtMatrix4x4( mtx[0],mtx[1],mtx[2],mtx[3],
                                mtx[4],mtx[5],mtx[6],mtx[7],
                                mtx[8],mtx[9],mtx[10],mtx[11],
                                mtx[12],mtx[13],mtx[14],mtx[15])

    return rman_mtx

def get_world_bounding_box(selected_obs):
    min_list = list()
    max_list = list()

    min_vector = None
    max_vector = None

    for ob in selected_obs:
        v = ob.matrix_world @ Vector(ob.bound_box[0])
        if min_vector is None:
            min_vector = v
        elif v < min_vector:
            min_vector = v
        v = ob.matrix_world @ Vector(ob.bound_box[7])
        if max_vector is None:
            max_vector = v
        elif v > max_vector:
            max_vector = v        

    return "%f %f %f %f %f %f" % (min_vector[0], max_vector[0], min_vector[1], max_vector[1], min_vector[2], max_vector[2])

def convert_ob_bounds(ob_bb):
    return (ob_bb[0][0], ob_bb[7][0], ob_bb[0][1],
            ob_bb[7][1], ob_bb[0][2], ob_bb[1][2])    

def convert_to_blmatrix(m):
    bl_matrix = Matrix()
    bl_matrix[0][0] = m[0]
    bl_matrix[1][0] = m[1]
    bl_matrix[2][0] = m[2]
    bl_matrix[3][0] = m[3]

    bl_matrix[0][1] = m[4]
    bl_matrix[1][1] = m[5]
    bl_matrix[2][1] = m[6]
    bl_matrix[3][1] = m[7]

    bl_matrix[0][2] = m[8]
    bl_matrix[1][2] = m[9]
    bl_matrix[2][2] = m[10]
    bl_matrix[3][2] = m[11]

    bl_matrix[0][3] = m[12]
    bl_matrix[1][3] = m[13]
    bl_matrix[2][3] = m[14]
    bl_matrix[3][3] = m[15]  

    return bl_matrix

def transform_points(transform_mtx, P):
    transform_pts = []
    mtx = convert_matrix( transform_mtx )
    m = rman.Types.RtMatrix4x4( mtx[0],mtx[1],mtx[2],mtx[3],
                                mtx[4],mtx[5],mtx[6],mtx[7],
                                mtx[8],mtx[9],mtx[10],mtx[11],
                                mtx[12],mtx[13],mtx[14],mtx[15])
    for i in range(0, len(P), 3):
        pt = m.pTransform( rman.Types.RtFloat3(P[i], P[i+1], P[i+2]) )
        transform_pts.append(pt.x)
        transform_pts.append(pt.y)
        transform_pts.append(pt.z)

    return transform_pts 