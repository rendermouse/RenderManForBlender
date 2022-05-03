import time
import os
import rman
import bpy
import sys
from .rman_constants import RFB_VIEWPORT_MAX_BUCKETS, RMAN_RENDERMAN_BLUE
from .rman_scene import RmanScene
from .rman_scene_sync import RmanSceneSync
from. import rman_spool
from. import chatserver
from .rfb_logger import rfb_log
import socketserver
import threading
import subprocess
import ctypes
import numpy
import traceback

# for viewport buckets
import gpu
from gpu_extras.batch import batch_for_shader

# utils
from .rfb_utils.envconfig_utils import envconfig
from .rfb_utils import string_utils
from .rfb_utils import display_utils
from .rfb_utils import scene_utils
from .rfb_utils import transform_utils
from .rfb_utils.prefs_utils import get_pref
from .rfb_utils.timer_utils import time_this

# config
from .rman_config import __RFB_CONFIG_DICT__ as rfb_config

# roz stats
from .rman_stats import RfBStatsManager

# handlers
from .rman_handlers.rman_it_handlers import add_ipr_to_it_handlers, remove_ipr_to_it_handlers

__RMAN_RENDER__ = None
__RMAN_IT_PORT__ = -1
__BLENDER_DSPY_PLUGIN__ = None
__DRAW_THREAD__ = None
__RMAN_STATS_THREAD__ = None

def __update_areas__():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()

def __draw_callback__():
    # callback function for the display driver to call tag_redraw
    global __RMAN_RENDER__
    if __RMAN_RENDER__.rman_is_viewport_rendering and __RMAN_RENDER__.bl_engine:
        try:
            __RMAN_RENDER__.bl_engine.tag_redraw()
            pass
        except ReferenceError as e:
            return  False
        return True
    return False     

DRAWCALLBACK_FUNC = ctypes.CFUNCTYPE(ctypes.c_bool)
__CALLBACK_FUNC__ = DRAWCALLBACK_FUNC(__draw_callback__)    

class ItHandler(chatserver.ItBaseHandler):

    def dspyRender(self):
        global __RMAN_RENDER__
        if not __RMAN_RENDER__.is_running:                        
            bpy.ops.render.render(layer=bpy.context.view_layer.name)             

    def dspyIPR(self):
        global __RMAN_RENDER__
        if __RMAN_RENDER__.rman_interactive_running:
            crop = []
            for c in self.msg.getOpt('crop').split(' '):
                crop.append(float(c))
            if len(crop) == 4:
                __RMAN_RENDER__.rman_scene_sync.update_cropwindow(crop)

    def stopRender(self):
        global __RMAN_RENDER__
        rfb_log().debug("Stop Render Requested.")
        if __RMAN_RENDER__.rman_interactive_running:
            __RMAN_RENDER__.stop_render(stop_draw_thread=False)
        __RMAN_RENDER__.del_bl_engine() 

    def selectObjectById(self):
        global __RMAN_RENDER__

        obj_id = int(self.msg.getOpt('id', '0'))
        if obj_id < 0 or not (obj_id in __RMAN_RENDER__.rman_scene.obj_hash):
            return
        name = __RMAN_RENDER__.rman_scene.obj_hash[obj_id]
        rfb_log().debug('ID: %d Obj Name: %s' % (obj_id, name))
        obj = bpy.context.scene.objects[name]
        if obj:
            if bpy.context.view_layer.objects.active:
                bpy.context.view_layer.objects.active.select_set(False)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

    def selectSurfaceById(self):
        self.selectObjectById()
        window = bpy.context.window_manager.windows[0]
        if window.screen:
            for a in window.screen.areas:
                if a.type == "PROPERTIES":
                    for s in a.spaces:
                        if s.type == "PROPERTIES":
                            try:
                                s.context = "MATERIAL"
                            except:
                                pass
                            return

def start_cmd_server():

    global __RMAN_IT_PORT__

    if __RMAN_IT_PORT__ != -1:
        return __RMAN_IT_PORT__

    # zero port makes the OS pick one
    host, port = "localhost", 0

    # install handler
    chatserver.protocols['it'] = ItHandler

    # Create the server, binding to localhost on some port
    server = socketserver.TCPServer((host, port),
                                    chatserver.CommandHandler)
    ip, port = server.server_address

    thread = threading.Thread(target=server.serve_forever)

    # Exit the server thread when the main thread terminates
    thread.daemon = True
    thread.start()

    __RMAN_IT_PORT__ = port

    return __RMAN_IT_PORT__        

def draw_threading_func(db):
    refresh_rate = get_pref('rman_viewport_refresh_rate', default=0.01)
    while db.rman_is_live_rendering:
        if db.bl_viewport.shading.type != 'RENDERED':
            # if the viewport is not rendering, stop IPR
            db.del_bl_engine()
            break
        if db.xpu_slow_mode:
            if db.has_buffer_updated():
                try:
                    db.bl_engine.tag_redraw()
                    db.reset_buffer_updated()
                
                except ReferenceError as e:
                    # calling tag_redraw has failed. This might mean
                    # that there are no more view_3d areas that are shading. Try to
                    # stop IPR.
                    #rfb_log().debug("Error calling tag_redraw (%s). Aborting..." % str(e))
                    db.del_bl_engine()
                    return            
            time.sleep(refresh_rate)
        else:            
            time.sleep(1.0)

def call_stats_export_payloads(db):
    while db.rman_is_exporting:
        db.stats_mgr.update_payloads()
        time.sleep(0.1)  

def call_stats_update_payloads(db):
    while db.rman_running:
        if not db.bl_engine:
            break
        if db.rman_is_xpu and db.is_regular_rendering():
            # stop the render if we are rendering in XPU mode
            # and we've reached ~100%
            if float(db.stats_mgr._progress) > 98.0:
                db.rman_is_live_rendering = False
                break        
        db.stats_mgr.update_payloads()
        time.sleep(0.1)

def progress_cb(e, d, db):
    if not db.stats_mgr.is_connected():
        # set the progress in stats_mgr
        # we can at least get progress from the event callback
        # in case the stats listener is not connected
        db.stats_mgr._progress = int(d)
    if db.rman_is_live_rendering and int(d) == 100:
        db.rman_is_live_rendering = False

def bake_progress_cb(e, d, db): 
    if not db.stats_mgr.is_connected():
        db.stats_mgr._progress = int(d)      

def batch_progress_cb(e, d, db):
    # just tell the stats mgr to draw
    db.stats_mgr._progress = int(d)
    db.stats_mgr.draw_render_stats()    
    print("R90000 %4d%%" % int(d), file = sys.stderr )
    sys.stderr.flush()

def render_cb(e, d, db):
    if d == 0:
        rfb_log().debug("RenderMan has exited.")
        if db.rman_is_live_rendering:
            db.rman_is_live_rendering = False

def live_render_cb(e, d, db):
    if d == 0:
        db.rman_is_refining = False
    else:
        db.rman_is_refining = True

def preload_xpu():
    """On linux there is a problem with std::call_once and
    blender, by default, being linked with a static libstdc++.
    The loader seems to not be able to get the right tls key
    for the __once_call global when libprman loads libxpu. By preloading
    we end up calling the proxy in the blender executable and
    that works.
    
    Returns:
    ctypes.CDLL of xpu or None if that fails. None if not on linux
    """
    if sys.platform != 'linux':
        return None

    tree = envconfig().rmantree
    xpu_path = os.path.join(tree, 'lib', 'libxpu.so')

    try:
        xpu = ctypes.CDLL(xpu_path)
        return xpu
    except OSError as error:
        rfb_log().debug('Failed to preload xpu: {0}'.format(error))
        return None

class RmanRender(object):
    '''
    RmanRender class. This class is responsible for starting and stopping
    the renderer. There should only be one instance of this class per session.

    Do not create an instance of this class directly. Use RmanRender.get_rman_render()
    '''

    def __init__(self):
        global __RMAN_RENDER__
        self.rictl = rman.RiCtl.Get()
        self.sgmngr = rman.SGManager.Get()
        self.rman = rman
        self.sg_scene = None
        self.rman_scene = RmanScene(rman_render=self)
        self.rman_scene_sync = RmanSceneSync(rman_render=self, rman_scene=self.rman_scene)
        self.bl_engine = None
        self.rman_running = False
        self.rman_is_exporting = False
        self.rman_interactive_running = False
        self.rman_swatch_render_running = False
        self.rman_is_live_rendering = False
        self.rman_is_viewport_rendering = False
        self.rman_is_xpu = False
        self.rman_is_refining = False
        self.rman_render_into = 'blender'
        self.rman_license_failed = False
        self.rman_license_failed_message = ''
        self.it_port = -1 
        self.rman_callbacks = dict()
        self.viewport_res_x = -1
        self.viewport_res_y = -1
        self.viewport_buckets = list()
        self._draw_viewport_buckets = False
        self.stats_mgr = RfBStatsManager(self)
        self.deleting_bl_engine = threading.Lock()
        self.stop_render_mtx = threading.Lock()
        self.bl_viewport = None
        self.xpu_slow_mode = False

        self._start_prman_begin()

        # hold onto this or python will unload it
        self.preload_xpu = preload_xpu()

    @classmethod
    def get_rman_render(self):
        global __RMAN_RENDER__
        if __RMAN_RENDER__ is None:
            __RMAN_RENDER__ = RmanRender()

        return __RMAN_RENDER__

    @property
    def bl_engine(self):
        return self.__bl_engine

    @bl_engine.setter
    def bl_engine(self, bl_engine):
        self.__bl_engine = bl_engine        

    def _start_prman_begin(self):
        argv = []
        argv.append("prman") 
        #argv.append("-Progress")  
        argv.append("-dspyserver")
        argv.append("%s" % envconfig().rman_it_path)

        argv.append("-statssession")
        argv.append(self.stats_mgr.rman_stats_session_name)

        woffs = ',' . join(rfb_config['woffs'])
        if woffs:
            argv.append('-woff')
            argv.append(woffs)

        self.rictl.PRManBegin(argv)  

    def __del__(self):   
        self.rictl.PRManEnd()

    def del_bl_engine(self):
        if not self.bl_engine:
            return
        if not self.deleting_bl_engine.acquire(timeout=2.0):
            return
        self.bl_engine = None
        self.deleting_bl_engine.release()
        
    def _append_render_cmd(self, render_cmd):
        return render_cmd

    def _dump_rib_(self, frame=1):
        if envconfig().getenv('RFB_DUMP_RIB'):
            rfb_log().debug("Writing to RIB...")
            rib_time_start = time.time()
            if sys.platform == ("win32"):
                self.sg_scene.Render("rib C:/tmp/blender.%04d.rib -format ascii -indent" % frame)
            else:
                self.sg_scene.Render("rib /var/tmp/blender.%04d.rib -format ascii -indent" % frame)     
            rfb_log().debug("Finished writing RIB. Time: %s" % string_utils._format_time_(time.time() - rib_time_start))            

    def _load_placeholder_image(self):   
        placeholder_image = os.path.join(envconfig().rmantree, 'lib', 'textures', 'placeholder.png')

        render = self.bl_scene.render
        image_scale = 100.0 / render.resolution_percentage
        result = self.bl_engine.begin_result(0, 0,
                                    render.resolution_x * image_scale,
                                    render.resolution_y * image_scale)
        lay = result.layers[0]
        try:
            lay.load_from_file(placeholder_image)
        except:
            pass
        self.bl_engine.end_result(result)               

    def _call_brickmake_for_selected(self):  
        rm = self.bl_scene.renderman
        ob = bpy.context.active_object
        if rm.external_animation:
            for frame in range(self.bl_scene.frame_start, self.bl_scene.frame_end + 1):        
                expanded_str = string_utils.expand_string(ob.renderman.bake_filename_attr, frame=self.bl_scene.frame_current) 
                ptc_file = '%s.ptc' % expanded_str            
                bkm_file = '%s.bkm' % expanded_str
                args = []
                args.append('%s/bin/brickmake' % envconfig().rmantree)
                args.append('-progress')
                args.append('2')
                args.append(ptc_file)
                args.append(bkm_file)
                subprocess.run(args)
        else:     
            expanded_str = string_utils.expand_string(ob.renderman.bake_filename_attr, frame=self.bl_scene.frame_current) 
            ptc_file = '%s.ptc' % expanded_str            
            bkm_file = '%s.bkm' % expanded_str
            args = []
            args.append('%s/bin/brickmake' % envconfig().rmantree)
            args.append('-progress')
            args.append('2')
            args.append(ptc_file)
            args.append(bkm_file)
            subprocess.run(args)   

    def _check_prman_license(self):
        if not envconfig().is_valid_license:
            self.rman_license_failed = True
            self.rman_license_failed_message = 'Cannot find a valid RenderMan license. Aborting.'
        
        elif not envconfig().has_rps_license:
            self.rman_license_failed = True
            self.rman_license_failed_message = 'Cannot find RPS-%s license feature. Aborting.' % (envconfig().feature_version)
        else:
            # check for any available PhotoRealistic-RenderMan licenses
            status = envconfig().get_prman_license_status()
            if not(status.found and status.is_available):
                self.rman_license_failed = True
                self.rman_license_failed_message = 'No PhotoRealistic-RenderMan licenses available. Aborting.'
            elif status.is_expired():
                self.rman_license_failed = True
                self.rman_license_failed_message = 'PhotoRealistic-RenderMan licenses have expired (%s).' % str(status.exp_date)
       
        if self.rman_license_failed:
            if not self.rman_interactive_running:
                self.bl_engine.report({'ERROR'}, self.rman_license_failed_message)
                self.stop_render()
            return False

        return True     

    def is_regular_rendering(self):
        # return if we are doing a regular render and not interactive
        return (self.rman_running and not self.rman_interactive_running)   

    def is_ipr_to_it(self):
        return (self.rman_interactive_running and self.rman_scene.ipr_render_into == 'it')

    def do_draw_buckets(self):
        return get_pref('rman_viewport_draw_bucket', default=True) and self.rman_is_refining

    def do_draw_progressbar(self):
        return get_pref('rman_viewport_draw_progress') and self.stats_mgr.is_connected() and self.stats_mgr._progress < 100    

    def start_export_stats_thread(self): 
        # start an export stats thread
        global __RMAN_STATS_THREAD__       
        __RMAN_STATS_THREAD__ = threading.Thread(target=call_stats_export_payloads, args=(self, ))
        __RMAN_STATS_THREAD__.start()              

    def start_stats_thread(self): 
        # start a stats thread so we can periodically call update_payloads
        global __RMAN_STATS_THREAD__
        if __RMAN_STATS_THREAD__:
            __RMAN_STATS_THREAD__.join()
            __RMAN_STATS_THREAD__ = None
        __RMAN_STATS_THREAD__ = threading.Thread(target=call_stats_update_payloads, args=(self, ))
        if self.rman_is_xpu:
            # FIXME: for now, add a 1 second delay before starting the stats thread
            # for some reason, XPU doesn't seem to reset the progress between renders
            time.sleep(1.0)        
        __RMAN_STATS_THREAD__.start()         

    def reset(self):
        self.rman_license_failed = False
        self.rman_license_failed_message = ''
        self.rman_is_xpu = False
        self.rman_is_refining = False
        self.bl_viewport = None
        self.xpu_slow_mode = False

    def start_render(self, depsgraph, for_background=False):
    
        self.reset()
        self.bl_scene = depsgraph.scene_eval
        rm = self.bl_scene.renderman
        self.it_port = start_cmd_server()    
        rfb_log().info("Parsing scene...")
        time_start = time.time()

        if not self._check_prman_license():
            return False        

        use_compositor = scene_utils.should_use_bl_compositor(self.bl_scene)
        if for_background:
            self.rman_render_into = ''
            is_external = True
            if use_compositor:
                self.rman_render_into = 'blender'
                is_external = False
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb  
            if envconfig().getenv('RFB_BATCH_NO_PROGRESS') is None:  
                ec.RegisterCallback("Progress", batch_progress_cb, self)
                self.rman_callbacks["Progress"] = batch_progress_cb               
            rman.Dspy.DisableDspyServer()          
        else:

            self.rman_render_into = rm.render_into
            is_external = False                    
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Progress", progress_cb, self)
            self.rman_callbacks["Progress"] = progress_cb
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb        
            
            try:
                if self.rman_render_into == 'it':
                    rman.Dspy.EnableDspyServer()
                else:
                    rman.Dspy.DisableDspyServer()
            except:
                pass

        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()
        rendervariant = scene_utils.get_render_variant(self.bl_scene)
        scene_utils.set_render_variant_config(self.bl_scene, config, render_config)
        self.rman_is_xpu = (rendervariant == 'xpu')

        self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session) 
        was_connected = self.stats_mgr.is_connected()
        if self.rman_is_xpu:
            if not was_connected:
                # force the stats to start in the case of XPU
                # this is so that we can get a progress percentage
                # if we can't get it to start, abort
                self.stats_mgr.attach(force=True)
                time.sleep(0.5) # give it a second to attach
                if not self.stats_mgr.is_connected():
                    self.bl_engine.report({'ERROR'}, 'Cannot start live stats. Aborting XPU render')
                    self.stop_render(stop_draw_thread=False)
                    self.del_bl_engine()
                    return False            

        try:
            bl_layer = depsgraph.view_layer
            self.rman_is_exporting = True
            self.rman_running = True
            self.start_export_stats_thread()
            self.rman_scene.export_for_final_render(depsgraph, self.sg_scene, bl_layer, is_external=is_external)
            self.rman_is_exporting = False
            self.stats_mgr.reset_progress()

            self._dump_rib_(self.bl_scene.frame_current)
            rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start)) 
            self.rman_is_live_rendering = True
        except Exception as e:      
            self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
            rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False            
        
        render_cmd = "prman"
        if self.rman_render_into == 'blender':
            render_cmd = "prman -live"
        render_cmd = self._append_render_cmd(render_cmd)
        self.sg_scene.Render(render_cmd)
        if self.rman_render_into == 'blender':  
            dspy_dict = display_utils.get_dspy_dict(self.rman_scene, include_holdouts=False)
            
            render = self.rman_scene.bl_scene.render
            render_view = self.bl_engine.active_view_get()
            image_scale = render.resolution_percentage / 100.0
            width = int(render.resolution_x * image_scale)
            height = int(render.resolution_y * image_scale)

            bl_image_rps= dict()

            # register any AOV's as passes
            for i, dspy_nm in enumerate(dspy_dict['displays'].keys()):
                if i == 0:
                    continue     

                num_channels = -1
                while num_channels == -1:
                    num_channels = self.get_numchannels(i)    

                dspy = dspy_dict['displays'][dspy_nm]
                dspy_chan = dspy['params']['displayChannels'][0]
                chan_info = dspy_dict['channels'][dspy_chan]
                chan_type = chan_info['channelType']['value']                        

                if num_channels == 4:
                    self.bl_engine.add_pass(dspy_nm, 4, 'RGBA')
                elif num_channels == 3:
                    if chan_type == 'color':
                        self.bl_engine.add_pass(dspy_nm, 3, 'RGB')
                    else:
                        self.bl_engine.add_pass(dspy_nm, 3, 'XYZ')
                elif num_channels == 2:
                    self.bl_engine.add_pass(dspy_nm, 2, 'XY')                        
                else:
                    self.bl_engine.add_pass(dspy_nm, 1, 'X')

            size_x = width
            size_y = height
            if render.use_border:
                size_x = int(width * (render.border_max_x - render.border_min_x))
                size_y = int(height * (render.border_max_y - render.border_min_y))     

            result = self.bl_engine.begin_result(0, 0,
                                        size_x,
                                        size_y,
                                        view=render_view)                        

            for i, dspy_nm in enumerate(dspy_dict['displays'].keys()):
                if i == 0:
                    render_pass = result.layers[0].passes.find_by_name("Combined", render_view)           
                else:
                    render_pass = result.layers[0].passes.find_by_name(dspy_nm, render_view)
                bl_image_rps[i] = render_pass            
            
            self.start_stats_thread()
            while self.bl_engine and not self.bl_engine.test_break() and self.rman_is_live_rendering:
                time.sleep(0.01)
                for i, rp in bl_image_rps.items():
                    buffer = self._get_buffer(width, height, image_num=i, 
                                                num_channels=rp.channels, 
                                                as_flat=False, 
                                                back_fill=False,
                                                render=render)
                    if buffer is None:
                        continue
                    rp.rect = buffer
        
                if self.bl_engine:
                    self.bl_engine.update_result(result)        
        
            if result:
                if self.bl_engine:
                    self.bl_engine.end_result(result) 

                # check if we should write out the AOVs
                if use_compositor and rm.use_bl_compositor_write_aovs:
                    for i, dspy_nm in enumerate(dspy_dict['displays'].keys()):
                        filepath = dspy_dict['displays'][dspy_nm]['filePath']
                        buffer = self._get_buffer(width, height, image_num=i, as_flat=True)
                        if buffer is None:
                            continue

                        if i == 0:
                            # write out the beauty with a 'raw' substring
                            toks = os.path.splitext(filepath)
                            filepath = '%s_beauty_raw.exr' % (toks[0])
 
                        bl_image = bpy.data.images.new(dspy_nm, width, height)
                        try:
                            if isinstance(buffer, numpy.ndarray):
                                buffer = buffer.tolist()
                            bl_image.use_generated_float = True
                            bl_image.filepath_raw = filepath                            
                            bl_image.pixels.foreach_set(buffer)
                            bl_image.file_format = 'OPEN_EXR'
                            bl_image.update()
                            bl_image.save()
                        except:
                            pass
                        finally:
                            bpy.data.images.remove(bl_image)      

            if not was_connected and self.stats_mgr.is_connected():
                # if stats were not started before rendering, disconnect
                self.stats_mgr.disconnect()                                 
        else:
            self.start_stats_thread()
            while self.bl_engine and not self.bl_engine.test_break() and self.rman_is_live_rendering:
                time.sleep(0.01)        

        self.del_bl_engine()
        self.stop_render()                          

        return True   

    def start_external_render(self, depsgraph):  

        bl_scene = depsgraph.scene_eval
        rm = bl_scene.renderman

        self.rman_running = True
        self.rman_render_into = ''
        rib_options = ""
        if rm.rib_compression == "gzip":
            rib_options += " -compression gzip"
        rib_format = 'ascii'
        if rm.rib_format == 'binary':
            rib_format = 'binary' 
        rib_options += " -format %s" % rib_format
        if rib_format == "ascii":
            rib_options += " -indent"

        if rm.external_animation:
            original_frame = bl_scene.frame_current
            rfb_log().debug("Writing to RIB...")             
            for frame in range(bl_scene.frame_start, bl_scene.frame_end + 1):
                bl_view_layer = depsgraph.view_layer
                config = rman.Types.RtParamList()
                render_config = rman.Types.RtParamList()

                self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session) 
                try:
                    self.bl_engine.frame_set(frame, subframe=0.0)
                    rfb_log().debug("Frame: %d" % frame)
                    self.rman_is_exporting = True
                    self.rman_scene.export_for_final_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                    self.rman_is_exporting = False
                    rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                            frame=frame, 
                                                            asFilePath=True)                                                                            
                    self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))
                    self.sgmngr.DeleteScene(self.sg_scene) 
                    self.sg_scene = None   
                    self.rman_scene.reset()                     

                except Exception as e:      
                    self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                    rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                    self.stop_render(stop_draw_thread=False)
                    self.del_bl_engine()
                    return False                       

            self.bl_engine.frame_set(original_frame, subframe=0.0)
            

        else:
            config = rman.Types.RtParamList()
            render_config = rman.Types.RtParamList()

            self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session) 
            try:
                time_start = time.time()
                        
                bl_view_layer = depsgraph.view_layer         
                rfb_log().info("Parsing scene...")      
                self.rman_is_exporting = True       
                self.rman_scene.export_for_final_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                self.rman_is_exporting = False
                rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                        frame=bl_scene.frame_current, 
                                                        asFilePath=True)            

                rfb_log().debug("Writing to RIB: %s..." % rib_output)
                rib_time_start = time.time()
                self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))     
                rfb_log().debug("Finished writing RIB. Time: %s" % string_utils._format_time_(time.time() - rib_time_start)) 
                rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start))
                self.sgmngr.DeleteScene(self.sg_scene)     
                self.sg_scene = None
                self.rman_scene.reset()                       
            except Exception as e:      
                self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False                         

        if rm.queuing_system != 'none':
            spooler = rman_spool.RmanSpool(self, self.rman_scene, depsgraph)
            spooler.batch_render()
        self.rman_running = False
        self.del_bl_engine()
        return True          

    def start_bake_render(self, depsgraph, for_background=False):
        self.reset()
        self.bl_scene = depsgraph.scene_eval
        rm = self.bl_scene.renderman
        self.it_port = start_cmd_server()    
        rfb_log().info("Parsing scene...")
        time_start = time.time()
        if not self._check_prman_license():
            return False             

        if for_background:
            is_external = True
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb       
            rman.Dspy.DisableDspyServer()          
        else:
            is_external = False                    
            self.rman_callbacks.clear()
            ec = rman.EventCallbacks.Get()
            ec.RegisterCallback("Progress", bake_progress_cb, self)
            self.rman_callbacks["Progress"] = bake_progress_cb
            ec.RegisterCallback("Render", render_cb, self)
            self.rman_callbacks["Render"] = render_cb              

        self.rman_render_into = ''
        rman.Dspy.DisableDspyServer()
        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()

        self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session) 
        try:
            bl_layer = depsgraph.view_layer
            self.rman_is_exporting = True
            self.rman_running = True
            self.start_export_stats_thread()
            self.rman_scene.export_for_bake_render(depsgraph, self.sg_scene, bl_layer, is_external=is_external)
            self.rman_is_exporting = False

            self._dump_rib_(self.bl_scene.frame_current)
            rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start)) 
            render_cmd = "prman -blocking"
            render_cmd = self._append_render_cmd(render_cmd)        
            self.sg_scene.Render(render_cmd)
            self.start_stats_thread()
        except Exception as e:      
            self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
            rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False                  
        self.stop_render()
        if rm.hider_type == 'BAKE_BRICKMAP_SELECTED':
            self._call_brickmake_for_selected()
        self.del_bl_engine()
        return True        

    def start_external_bake_render(self, depsgraph):  

        bl_scene = depsgraph.scene_eval
        rm = bl_scene.renderman

        self.rman_running = True
        self.rman_render_into = ''
        rib_options = ""
        if rm.rib_compression == "gzip":
            rib_options += " -compression gzip"
        rib_format = 'ascii'
        if rm.rib_format == 'binary':
            rib_format = 'binary' 
        rib_options += " -format %s" % rib_format
        if rib_format == "ascii":
            rib_options += " -indent"

        if rm.external_animation:
            original_frame = bl_scene.frame_current
            rfb_log().debug("Writing to RIB...")             
            for frame in range(bl_scene.frame_start, bl_scene.frame_end + 1):
                bl_view_layer = depsgraph.view_layer
                config = rman.Types.RtParamList()
                render_config = rman.Types.RtParamList()

                self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session) 
                try:
                    self.bl_engine.frame_set(frame, subframe=0.0)
                    self.rman_is_exporting = True
                    self.rman_scene.export_for_bake_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                    self.rman_is_exporting = False
                    rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                            frame=frame, 
                                                            asFilePath=True)                                                                            
                    self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))
                except Exception as e:      
                    self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                    self.stop_render(stop_draw_thread=False)
                    self.del_bl_engine()
                    return False                         
                self.sgmngr.DeleteScene(self.sg_scene)  
                self.sg_scene = None
                self.rman_scene.reset()                     

            self.bl_engine.frame_set(original_frame, subframe=0.0)
            

        else:
            config = rman.Types.RtParamList()
            render_config = rman.Types.RtParamList()

            self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session) 

            try:
                time_start = time.time()
                        
                bl_view_layer = depsgraph.view_layer         
                rfb_log().info("Parsing scene...")
                self.rman_is_exporting = True             
                self.rman_scene.export_for_bake_render(depsgraph, self.sg_scene, bl_view_layer, is_external=True)
                self.rman_is_exporting = False
                rib_output = string_utils.expand_string(rm.path_rib_output, 
                                                        frame=bl_scene.frame_current, 
                                                        asFilePath=True)            

                rfb_log().debug("Writing to RIB: %s..." % rib_output)
                rib_time_start = time.time()
                self.sg_scene.Render("rib %s %s" % (rib_output, rib_options))     
                rfb_log().debug("Finished writing RIB. Time: %s" % string_utils._format_time_(time.time() - rib_time_start)) 
                rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start))
            except Exception as e:      
                self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False                     

            self.sgmngr.DeleteScene(self.sg_scene)
            self.sg_scene = None
            self.rman_scene.reset()              

        if rm.queuing_system != 'none':
            spooler = rman_spool.RmanSpool(self, self.rman_scene, depsgraph)
            spooler.batch_render()
        self.rman_running = False
        self.del_bl_engine()
        return True                  

    def start_interactive_render(self, context, depsgraph):

        global __DRAW_THREAD__
        self.reset()
        self.rman_interactive_running = True
        self.rman_running = True
        __update_areas__()
        self.bl_scene = depsgraph.scene_eval
        rm = depsgraph.scene_eval.renderman
        self.it_port = start_cmd_server()    
        render_into_org = '' 
        self.rman_render_into = self.rman_scene.ipr_render_into
        self.bl_viewport = context.space_data
        
        self.rman_callbacks.clear()
        # register the blender display driver
        try:
            if self.rman_render_into == 'blender':
                # turn off dspyserver mode if we're not rendering to "it"
                self.rman_is_viewport_rendering = True    
                rman.Dspy.DisableDspyServer()             
                self.rman_callbacks.clear()
                ec = rman.EventCallbacks.Get()      
                ec.RegisterCallback("Render", live_render_cb, self)
                self.rman_callbacks["Render"] = live_render_cb                    
                self.viewport_buckets.clear()
                self._draw_viewport_buckets = True                           
            else:
                rman.Dspy.EnableDspyServer()
                add_ipr_to_it_handlers()
        except:
            # force rendering to 'it'
            rfb_log().error('Could not register Blender display driver. Rendering to "it".')
            render_into_org = rm.render_ipr_into
            rm.render_ipr_into = 'it'
            self.rman_render_into = 'it'
            rman.Dspy.EnableDspyServer()

        if not self._check_prman_license():
            return False
        time_start = time.time()      

        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()
        rendervariant = scene_utils.get_render_variant(self.bl_scene)
        scene_utils.set_render_variant_config(self.bl_scene, config, render_config)
        self.rman_is_xpu = (rendervariant == 'xpu')
        if self.rman_is_xpu:
            self.xpu_slow_mode = envconfig().getenv('RFB_XPU_SLOW_MODE', default=False)

        self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session) 

        try:
            self.rman_scene_sync.sg_scene = self.sg_scene
            rfb_log().info("Parsing scene...")        
            self.rman_is_exporting = True
            self.start_export_stats_thread()        
            self.rman_scene.export_for_interactive_render(context, depsgraph, self.sg_scene)
            self.rman_is_exporting = False

            self._dump_rib_(self.bl_scene.frame_current)
            rfb_log().info("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start))      
            self.rman_is_live_rendering = True     
            render_cmd = "prman -live"   
            render_cmd = self._append_render_cmd(render_cmd)
            self.sg_scene.Render(render_cmd)
            self.start_stats_thread()

            rfb_log().info("RenderMan Viewport Render Started.")  

            if render_into_org != '':
                rm.render_ipr_into = render_into_org    
            
            if not self.xpu_slow_mode:
                self.set_redraw_func()
            else:
                rfb_log().debug("XPU slow mode enabled.")
            # start a thread to periodically call engine.tag_redraw()                
            __DRAW_THREAD__ = threading.Thread(target=draw_threading_func, args=(self, ))
            __DRAW_THREAD__.start()

            return True
        except Exception as e:      
            bpy.ops.renderman.printer('INVOKE_DEFAULT', level="ERROR", message='Export failed: %s' % str(e))
            rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
            self.stop_render(stop_draw_thread=False)
            self.del_bl_engine()
            return False

    def start_swatch_render(self, depsgraph):
        self.reset()
        self.bl_scene = depsgraph.scene_eval

        rfb_log().debug("Parsing scene...")
        time_start = time.time()                
        self.rman_callbacks.clear()
        ec = rman.EventCallbacks.Get()
        rman.Dspy.DisableDspyServer()
        ec.RegisterCallback("Progress", progress_cb, self)
        self.rman_callbacks["Progress"] = progress_cb        
        ec.RegisterCallback("Render", render_cb, self)
        self.rman_callbacks["Render"] = render_cb        

        config = rman.Types.RtParamList()
        render_config = rman.Types.RtParamList()

        self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session)         
        self.rman_is_exporting = True
        self.rman_scene.export_for_swatch_render(depsgraph, self.sg_scene)
        self.rman_is_exporting = False

        self.rman_running = True
        self.rman_swatch_render_running = True
        self._dump_rib_()
        rfb_log().debug("Finished parsing scene. Total time: %s" % string_utils._format_time_(time.time() - time_start)) 
        if not self._check_prman_license():
            return False
        self.rman_is_live_rendering = True
        self.sg_scene.Render("prman")
        render = self.rman_scene.bl_scene.render
        render_view = self.bl_engine.active_view_get()
        image_scale = render.resolution_percentage / 100.0
        width = int(render.resolution_x * image_scale)
        height = int(render.resolution_y * image_scale)
        result = self.bl_engine.begin_result(0, 0,
                                    width,
                                    height,
                                    view=render_view)
        layer = result.layers[0].passes.find_by_name("Combined", render_view)        
        while not self.bl_engine.test_break() and self.rman_is_live_rendering:
            time.sleep(0.001)
            if layer:
                buffer = self._get_buffer(width, height, image_num=0, as_flat=False)
                if buffer:
                    layer.rect = buffer
                    self.bl_engine.update_result(result)
        # try to get the buffer one last time before exiting
        if layer:
            buffer = self._get_buffer(width, height, image_num=0, as_flat=False)
            if buffer:
                layer.rect = buffer
                self.bl_engine.update_result(result)        
        self.stop_render()              
        self.bl_engine.end_result(result)  
        self.del_bl_engine()         
       
        return True  

    def start_export_rib_selected(self, context, rib_path, export_materials=True, export_all_frames=False):

        self.rman_running = True  
        bl_scene = context.scene
        if export_all_frames:
            original_frame = bl_scene.frame_current
            rfb_log().debug("Writing to RIB...")             
            for frame in range(bl_scene.frame_start, bl_scene.frame_end + 1):        
                bl_scene.frame_set(frame, subframe=0.0)
                config = rman.Types.RtParamList()
                render_config = rman.Types.RtParamList()

                self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session)   
                try:
                    self.rman_is_exporting = True
                    self.rman_scene.export_for_rib_selection(context, self.sg_scene)
                    self.rman_is_exporting = False
                    rib_output = string_utils.expand_string(rib_path, 
                                                        frame=frame, 
                                                        asFilePath=True) 
                    cmd = 'rib ' + rib_output + ' -archive'                                                        
                    cmd = cmd + ' -bbox ' + transform_utils.get_world_bounding_box(context.selected_objects)
                    self.sg_scene.Render(cmd)
                except Exception as e:      
                    self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                    self.stop_render(stop_draw_thread=False)
                    self.del_bl_engine()
                    return False                    
                self.sgmngr.DeleteScene(self.sg_scene)     
                self.sg_scene = None
                self.rman_scene.reset()            
            bl_scene.frame_set(original_frame, subframe=0.0)    
        else:
            config = rman.Types.RtParamList()
            render_config = rman.Types.RtParamList()

            self.sg_scene = self.sgmngr.CreateScene(config, render_config, self.stats_mgr.rman_stats_session)   
            try:
                self.rman_is_exporting = True
                self.rman_scene.export_for_rib_selection(context, self.sg_scene)
                self.rman_is_exporting = False
                rib_output = string_utils.expand_string(rib_path, 
                                                    frame=bl_scene.frame_current, 
                                                    asFilePath=True) 
                cmd = 'rib ' + rib_output + ' -archive'
                cmd = cmd + ' -bbox ' + transform_utils.get_world_bounding_box(context.selected_objects)
                self.sg_scene.Render(cmd)
            except Exception as e:      
                self.bl_engine.report({'ERROR'}, 'Export failed: %s' % str(e))
                rfb_log().error('Export Failed:\n%s' % traceback.format_exc())
                self.stop_render(stop_draw_thread=False)
                self.del_bl_engine()
                return False    
            self.sgmngr.DeleteScene(self.sg_scene)            
            self.sg_scene = None
            self.rman_scene.reset()  

        self.rman_running = False        
        return True                 

    def stop_render(self, stop_draw_thread=True):
        global __DRAW_THREAD__
        global __RMAN_STATS_THREAD__
        is_main_thread = (threading.current_thread() == threading.main_thread())

        if is_main_thread:
            rfb_log().debug("Trying to acquire stop_render_mtx")
        if not self.stop_render_mtx.acquire(timeout=5.0):
            return
        
        if not self.rman_interactive_running and not self.rman_running:
            return

        self.rman_running = False
        self.rman_interactive_running = False  
        self.rman_swatch_render_running = False
        self.rman_is_viewport_rendering = False       
        self.rman_is_exporting = False     

        # Remove callbacks
        ec = rman.EventCallbacks.Get()
        if is_main_thread:
            rfb_log().debug("Unregister any callbacks")
        for k,v in self.rman_callbacks.items():
            ec.UnregisterCallback(k, v, self)
        self.rman_callbacks.clear()          
        remove_ipr_to_it_handlers()

        self.rman_is_live_rendering = False

        # wait for the drawing thread to finish
        # if we are told to.
        if stop_draw_thread and __DRAW_THREAD__:
            __DRAW_THREAD__.join()
            __DRAW_THREAD__ = None

        # stop retrieving stats
        if __RMAN_STATS_THREAD__:
            __RMAN_STATS_THREAD__.join()
            __RMAN_STATS_THREAD__ = None

        if is_main_thread:
            rfb_log().debug("Telling SceneGraph to stop.")    
        if self.sg_scene:    
            self.sg_scene.Stop()
            if is_main_thread:
                rfb_log().debug("Delete Scenegraph scene")
            self.sgmngr.DeleteScene(self.sg_scene)

        self.sg_scene = None
        #self.stats_mgr.reset()
        self.rman_scene.reset()
        self.viewport_buckets.clear()
        self._draw_viewport_buckets = False                
        __update_areas__()
        self.stop_render_mtx.release()
        if is_main_thread:
            rfb_log().debug("RenderMan has Stopped.")

    def get_blender_dspy_plugin(self):
        global __BLENDER_DSPY_PLUGIN__
        if __BLENDER_DSPY_PLUGIN__ == None:
            # grab a pointer to the Blender display driver
            ext = '.so'
            if sys.platform == ("win32"):
                    ext = '.dll'
            __BLENDER_DSPY_PLUGIN__ = ctypes.CDLL(os.path.join(envconfig().rmantree, 'lib', 'plugins', 'd_blender%s' % ext))

        return __BLENDER_DSPY_PLUGIN__

    def set_redraw_func(self):
        # pass our callback function to the display driver
        dspy_plugin = self.get_blender_dspy_plugin()
        dspy_plugin.SetRedrawCallback(__CALLBACK_FUNC__)

    def has_buffer_updated(self):        
        dspy_plugin = self.get_blender_dspy_plugin()
        return dspy_plugin.HasBufferUpdated()      

    def reset_buffer_updated(self):
        dspy_plugin = self.get_blender_dspy_plugin()
        dspy_plugin.ResetBufferUpdated()        
                
    def draw_pixels(self, width, height):
        self.viewport_res_x = width
        self.viewport_res_y = height
        if self.rman_is_viewport_rendering:
            dspy_plugin = self.get_blender_dspy_plugin()

            # (the driver will handle pixel scaling to the given viewport size)
            dspy_plugin.DrawBufferToBlender(ctypes.c_int(width), ctypes.c_int(height))

            if self.do_draw_buckets():
                # draw bucket indicator
                image_num = 0
                arXMin = ctypes.c_int(0)
                arXMax = ctypes.c_int(0)
                arYMin = ctypes.c_int(0)
                arYMax = ctypes.c_int(0)            
                dspy_plugin.GetActiveRegion(ctypes.c_size_t(image_num), ctypes.byref(arXMin), ctypes.byref(arXMax), ctypes.byref(arYMin), ctypes.byref(arYMax))
                if ( (arXMin.value + arXMax.value + arYMin.value + arYMax.value) > 0):
                    yMin = height-1 - arYMin.value
                    yMax = height-1 - arYMax.value
                    xMin = arXMin.value
                    xMax = arXMax.value
                    if self.rman_scene.viewport_render_res_mult != 1.0:
                        # render resolution multiplier is set, we need to re-scale the bucket markers
                        scaled_width = width * self.rman_scene.viewport_render_res_mult
                        xMin = int(width * ((arXMin.value) / (scaled_width)))
                        xMax = int(width * ((arXMax.value) / (scaled_width)))

                        scaled_height = height * self.rman_scene.viewport_render_res_mult
                        yMin = height-1 - int(height * ((arYMin.value) / (scaled_height)))
                        yMax = height-1 - int(height * ((arYMax.value) / (scaled_height)))
                    
                    vertices = []
                    c1 = (xMin, yMin)
                    c2 = (xMax, yMin)
                    c3 = (xMax, yMax)
                    c4 = (xMin, yMax)
                    vertices.append(c1)
                    vertices.append(c2)
                    vertices.append(c3)
                    vertices.append(c4)
                    indices = [(0, 1), (1, 2), (2,3), (3, 0)]

                    # we've reach our max buckets, pop the oldest one off the list
                    if len(self.viewport_buckets) > RFB_VIEWPORT_MAX_BUCKETS:
                        self.viewport_buckets.pop()
                    self.viewport_buckets.insert(0,[vertices, indices])
                    
                bucket_color = get_pref('rman_viewport_bucket_color', default=RMAN_RENDERMAN_BLUE)

                # draw from newest to oldest
                for v, i in (self.viewport_buckets):      
                    shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
                    shader.uniform_float("color", bucket_color)                                  
                    batch = batch_for_shader(shader, 'LINES', {"pos": v}, indices=i)
                    shader.bind()
                    batch.draw(shader)   

            # draw progress bar at the bottom of the viewport
            if self.do_draw_progressbar():
                progress = self.stats_mgr._progress / 100.0 
                progress_color = get_pref('rman_viewport_progress_color', default=RMAN_RENDERMAN_BLUE) 
                shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
                shader.uniform_float("color", progress_color)                       
                vtx = [(0, 1), (width * progress, 1)]
                batch = batch_for_shader(shader, 'LINES', {"pos": vtx})
                shader.bind()
                batch.draw(shader)

    def get_numchannels(self, image_num):
        dspy_plugin = self.get_blender_dspy_plugin()
        num_channels = dspy_plugin.GetNumberOfChannels(ctypes.c_size_t(image_num))
        return num_channels

    def _get_buffer(self, width, height, image_num=0, num_channels=-1, back_fill=True, as_flat=True, render=None):
        dspy_plugin = self.get_blender_dspy_plugin()
        if num_channels == -1:
            num_channels = self.get_numchannels(image_num)
            if num_channels > 4 or num_channels < 0:
                rfb_log().debug("Could not get buffer. Incorrect number of channels: %d" % num_channels)
                return None

        ArrayType = ctypes.c_float * (width * height * num_channels)
        f = dspy_plugin.GetFloatFramebuffer
        f.restype = ctypes.POINTER(ArrayType)

        try:
            buffer = numpy.array(f(ctypes.c_size_t(image_num)).contents)

            if as_flat:
                if (num_channels == 4) or not back_fill:
                    return buffer
                else:
                    p_pos = 0
                    pixels = numpy.ones(width*height*4, dtype=numpy.float32)
                    for y in range(0, height):
                        i = (width * y * num_channels)
                        
                        for x in range(0, width):
                            j = i + (num_channels * x)
                            if num_channels == 3:
                                pixels[p_pos:p_pos+3] = buffer[j:j+3]
                            elif num_channels == 2:
                                pixels[p_pos:p_pos+2] = buffer[j:j+2]
                            elif num_channels == 1:
                                pixels[p_pos] = buffer[j]
                                pixels[p_pos+1] = buffer[j]
                                pixels[p_pos+2] = buffer[j]
                            p_pos += 4                                
                    return pixels
            else:
                if render and render.use_border:
                    start_x = 0
                    end_x = width
                    start_y = 0
                    end_y = height

                
                    if render.border_min_y > 0.0:
                        start_y = round(height * render.border_min_y)-1
                    if render.border_max_y > 0.0:                        
                        end_y = round(height * render.border_max_y)-1 
                    if render.border_min_x > 0.0:
                        start_x = round(width * render.border_min_x)-1
                    if render.border_max_x < 1.0:
                        end_x = round(width * render.border_max_x)-2

                    # return the buffer as a list of lists
                    if back_fill:
                        pixels = numpy.ones( ((end_x-start_x)*(end_y-start_y), 4), dtype=numpy.float32 )
                    else:
                        pixels = numpy.zeros( ((end_x-start_x)*(end_y-start_y), num_channels) )
                    p_pos = 0
                    for y in range(start_y, end_y):
                        i = (width * y * num_channels)

                        for x in range(start_x, end_x):
                            j = i + (num_channels * x)
                            if (num_channels==4) or not back_fill:
                                # just slice
                                pixels[p_pos] = buffer[j:j+num_channels]
                            else:
                                pixels[p_pos][0] = buffer[j]                             
                                if num_channels == 3:
                                    pixels[p_pos][1] = buffer[j+1]
                                    pixels[p_pos][2] = buffer[j+2]
                                elif num_channels == 2:
                                    pixels[p_pos][1] = buffer[j+1]
                                elif num_channels == 1:
                                    pixels[p_pos][1] = buffer[j]
                                    pixels[p_pos][2] = buffer[j]

                            p_pos += 1

                    return pixels
                else:
                    buffer.shape = (-1, num_channels)
                    return buffer
        except Exception as e:
            rfb_log().debug("Could not get buffer: %s" % str(e))
            return None                                     

    @time_this
    def save_viewport_snapshot(self, frame=1):
        if not self.rman_is_viewport_rendering:
            return

        res_mult = self.rman_scene.viewport_render_res_mult
        width = int(self.viewport_res_x * res_mult)
        height = int(self.viewport_res_y * res_mult)

        pixels = self._get_buffer(width, height)
        if pixels is None:
            rfb_log().error("Could not save snapshot.")
            return

        nm = 'rman_viewport_snapshot_<F4>_%d' % len(bpy.data.images)
        nm = string_utils.expand_string(nm, frame=frame)
        img = bpy.data.images.new(nm, width, height, float_buffer=True, alpha=True) 
        if isinstance(pixels, numpy.ndarray):
            pixels = pixels.tolist()               
        img.pixels.foreach_set(pixels)
        img.update()
       
    def update_scene(self, context, depsgraph):
        if self.rman_interactive_running:
            self.rman_scene_sync.update_scene(context, depsgraph)

    def update_view(self, context, depsgraph):
        if self.rman_interactive_running:
            self.rman_scene_sync.update_view(context, depsgraph)
