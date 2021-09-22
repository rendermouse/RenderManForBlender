from . import rman_operators_editors_lightlink
from . import rman_operators_editors_stylized
from . import rman_operators_editors_tracegroups
from . import rman_operators_editors_workspace
from . import rman_operators_editors_lightmixer
from . import rman_operators_editors_vol_aggregates


def register():
    rman_operators_editors_lightlink.register()
    rman_operators_editors_stylized.register()
    rman_operators_editors_tracegroups.register()
    rman_operators_editors_workspace.register()
    rman_operators_editors_lightmixer.register()
    rman_operators_editors_vol_aggregates.register()

def unregister():
    rman_operators_editors_lightlink.unregister()
    rman_operators_editors_stylized.unregister()
    rman_operators_editors_tracegroups.unregister()
    rman_operators_editors_workspace.unregister()
    rman_operators_editors_lightmixer.unregister()  
    rman_operators_editors_vol_aggregates.unregister()  
                             