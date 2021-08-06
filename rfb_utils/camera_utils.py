from bpy_extras.view3d_utils import location_3d_to_region_2d

def render_get_resolution_(r):
    xres = int(r.resolution_x * r.resolution_percentage * 0.01)
    yres = int(r.resolution_y * r.resolution_percentage * 0.01)
    return xres, yres    

def render_get_aspect_(r, camera=None, x=-1, y=-1):
    if x != -1 and y != -1:
        xratio = x * r.pixel_aspect_x / 200.0
        yratio = y * r.pixel_aspect_y / 200.0        
    else:
        xres, yres = render_get_resolution_(r)
        xratio = xres * r.pixel_aspect_x / 200.0
        yratio = yres * r.pixel_aspect_y / 200.0

    if camera is None or camera.type != 'PERSP':
        fit = 'AUTO'
    else:
        fit = camera.sensor_fit

    if fit == 'HORIZONTAL' or fit == 'AUTO' and xratio > yratio:
        aspectratio = xratio / yratio
        xaspect = aspectratio
        yaspect = 1.0
    elif fit == 'VERTICAL' or fit == 'AUTO' and yratio > xratio:
        aspectratio = yratio / xratio
        xaspect = 1.0
        yaspect = aspectratio
    else:
        aspectratio = xaspect = yaspect = 1.0

    return xaspect, yaspect, aspectratio    


def get_viewport_cam_borders(ob, render, region, region_data, scene):

# Code reference:
# https://blender.stackexchange.com/questions/6377/coordinates-of-corners-of-camera-view-border

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