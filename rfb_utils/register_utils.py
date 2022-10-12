from ..rfb_logger import rfb_log
import bpy

def rman_register_class(cls):
    try:
        if hasattr(bpy.types, str(cls)):
            rman_unregister_class(cls)
        bpy.utils.register_class(cls)
    except ValueError as e:
        rfb_log().debug("Could not register class, %s, because: %s" % (str(cls), str(e)))
        pass    

def rman_register_classes(classes):
    for cls in classes:
        rman_register_class(cls)

def rman_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError:
        rfb_log().debug('Could not unregister class: %s' % str(cls))
        pass       

def rman_unregister_classes(classes):
    for cls in classes:
        rman_unregister_class(cls)