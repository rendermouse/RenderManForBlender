from .envconfig_utils import envconfig
import time

def time_this(f):   
    if not envconfig().getenv('RFB_DEVELOPER'):
        return f
    """Function that can be used as a decorator to time any method."""
    def timed(*args, **kw):
        tstart = time.time()
        result = f(*args, **kw)
        tstop = time.time()
        elapsed = (tstop - tstart) * 1000.0
        print('  _ %0.2f ms: %s(%s, %s)' % (
            elapsed, f.__name__,
            ', '.join([repr(a) for a in args]),
            ', '.join(['%s=%r' % (k, w) for k, w in kw.items()])))
        return result

    return timed