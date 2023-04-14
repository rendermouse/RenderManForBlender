import numpy as np

def get_mesh_points_(mesh):
    '''
    Get just the points for the input mesh.

    Arguments:
    mesh (bpy.types.Mesh) - Blender mesh

    Returns:
    (list) - the points on the mesh
    '''

    nvertices = len(mesh.vertices)
    P = np.zeros(nvertices*3, dtype=np.float32)
    mesh.vertices.foreach_get('co', P)
    P = np.reshape(P, (nvertices, 3))
    return P.tolist()

def get_mesh(mesh, get_normals=False):
    '''
    Get the basic primvars needed to render a mesh.

    Arguments:
    mesh (bpy.types.Mesh) - Blender mesh
    get_normals (bool) - Whether or not normals are needed

    Returns:
    (list) - this includes nverts (the number of vertices for each face), 
            vertices list, points, and normals
    '''

    P = get_mesh_points_(mesh)
    N = []    

    npolygons = len(mesh.polygons)
    fastnvertices = np.zeros(npolygons, dtype=np.int)
    mesh.polygons.foreach_get('loop_total', fastnvertices)
    nverts = fastnvertices.tolist()

    loops = len(mesh.loops)
    fastvertices = np.zeros(loops, dtype=np.int)
    mesh.loops.foreach_get('vertex_index', fastvertices)
    verts = fastvertices.tolist()

    if get_normals:
        fastsmooth = np.zeros(npolygons, dtype=np.int)
        mesh.polygons.foreach_get('use_smooth', fastsmooth)
        if mesh.use_auto_smooth or True in fastsmooth:
            mesh.calc_normals_split()
            fastnormals = np.zeros(loops*3, dtype=np.float32)
            mesh.loops.foreach_get('normal', fastnormals)
            fastnormals = np.reshape(fastnormals, (loops, 3))
            N = fastnormals.tolist()            
        else:            
            fastnormals = np.zeros(npolygons*3, dtype=np.float32)
            mesh.polygons.foreach_get('normal', fastnormals)
            fastnormals = np.reshape(fastnormals, (npolygons, 3))
            N = fastnormals.tolist()

    return (nverts, verts, P, N)