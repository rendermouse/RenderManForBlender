from bpy_extras.view3d_utils import location_3d_to_region_2d

def get_viewport_cam_borders(ob, render, region, region_data, scene):
    cam = ob.data
    frame = cam.view_frame(scene=scene)

    # move from object-space into world-space 
    frame = [ob.matrix_world @ v for v in frame]

    # move into pixelspace
    frame_px = [location_3d_to_region_2d(region, region_data, v) for v in frame]
    min_x = -1
    min_y = -1
    max_x = -1
    max_y = -1
    for v in frame_px:
        if min_x == -1:
            min_x = v[0]
        elif min_x > v[0]:
            min_x = v[0]
        if max_x < v[0]:
            max_x = v[0]
        if min_y == -1:
            min_y = v[1]
        elif min_y > v[1]:
            min_y = v[1]
        if max_y < v[1]:
            max_y = v[1]

    cam_width = max_x - min_x
    cam_height = max_y - min_y
    x0 = min_x + render.border_min_x * cam_width
    x1 = min_x + render.border_max_x * cam_width
    y0 = min_y + render.border_min_y * cam_height
    y1 = min_y + render.border_max_y * cam_height

    return (x0, x1, y0, y1)