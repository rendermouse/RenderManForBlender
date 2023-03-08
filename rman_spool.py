import subprocess
import os
import getpass
import socket
import bpy
from .rfb_utils import filepath_utils
from .rfb_utils import string_utils
from .rfb_utils.envconfig_utils import envconfig
from .rfb_utils import display_utils
from .rfb_utils import scene_utils
from .rfb_utils.prefs_utils import get_pref
from .rman_config import __RFB_CONFIG_DICT__ as rfb_config
from .rfb_logger import rfb_log

import tractor.api.author as author

class RmanSpool(object):

    def __init__(self, rman_render, rman_scene, depsgraph):
        self.rman_render = rman_render
        self.rman_scene = rman_scene
        self.is_localqueue = True
        self.is_tractor = False
        self.any_denoise = False
        if depsgraph:
            self.bl_scene = depsgraph.scene_eval
            self.depsgraph = depsgraph
            self.is_localqueue = (self.bl_scene.renderman.queuing_system == 'lq')
            self.is_tractor = (self.bl_scene.renderman.queuing_system == 'tractor')

    def add_job_level_attrs(self, job):
        for k in rfb_config['dirmaps']:
            dirmap = rfb_config['dirmaps'][k]
            job.newDirMap(src=str(dirmap['from']),
                        dst=str(dirmap['to']),
                        zone=str(dirmap['zone']))

        rman_vers = envconfig().build_info.version()
        if self.is_localqueue:
            job.envkey = ['rmantree=%s' % envconfig().rmantree]
        else:
            job.envkey = ['prman-%s' % rman_vers]     

    def _add_additional_prman_args(self, args):
        rm = self.bl_scene.renderman
        if rm.custom_cmd != '':
            tokens = rm.custom_cmd.split(' ')
            for tok in tokens:
                args.append(tok)

        if rm.recover:
            args.append('-recover')
            args.append('1')
        else:
            args.append('-recover')
            args.append('%r')

        scene_utils.set_render_variant_spool(self.bl_scene, args, self.is_tractor)
            
    def add_prman_render_task(self, parentTask, title, threads, rib, img):
        rm = self.bl_scene.renderman
        out_dir = '<OUT>'

        task = author.Task()
        task.title = title
        if img:
            task.preview = 'sho %s' % str(img)

        command = author.Command(local=False, service="PixarRender")
        command.argv = ["prman"]
        self._add_additional_prman_args(command.argv)

        proj = string_utils.expand_string(out_dir, asFilePath=True) 
        
        command.argv.append('-Progress')
        command.argv.append('-t:%d' % threads)
        command.argv.append('-cwd')
        command.argv.append("%%D(%s)" % proj)

        # rib file
        command.argv.append("%%D(%s)" % rib)

        task.addCommand(command)
        parentTask.addChild(task)            

    def add_blender_render_task(self, frame, parentTask, title, bl_filename, img, chunk=None):
        rm = self.bl_scene.renderman

        task = author.Task()
        task.title = title
        if img:        
            img_expanded = string_utils.expand_string(img, frame=frame, asFilePath=True)
            task.preview = 'sho %s' % img_expanded

        command = author.Command(local=False, service="PixarRender")
        bl_blender_path = bpy.app.binary_path
        command.argv = [bl_blender_path]

        command.argv.append('-b')
        command.argv.append('%%D(%s)' % bl_filename)
        if chunk:
            command.argv.append('-f')
            command.argv.append('%s..%s' % (str(frame), str(frame+(chunk))))
        else:
            command.argv.append('-f')
            command.argv.append(str(frame))            

        task.addCommand(command)
        parentTask.addChild(task)

    def generate_blender_batch_tasks(self, anim, parent_task, tasktitle,
                                start, last, by, chunk, bl_filename): 

        self.any_denoise = display_utils.any_dspys_denoise(self.rman_scene.bl_view_layer)
        img = None
        if not self.any_denoise:
            dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)  
            img = dspys_dict['displays']['beauty']['filePath']
        
        if anim is False:
     
            frametasktitle = ("%s Frame: %d " %
                            (tasktitle, int(start)))
            frametask = author.Task()
            frametask.title = frametasktitle
            frametask.serialsubtasks = True

            prmantasktitle = "%s (render)" % frametasktitle

            self.add_blender_render_task(start, frametask, prmantasktitle,
                                bl_filename, img)

            parent_task.addChild(frametask)

        else:
            parent_task.serialsubtasks = True

            renderframestask = author.Task()
            renderframestask.serialsubtasks = False
            renderframestasktitle = ("Render Layer: %s "%
                                    (str(self.depsgraph.view_layer.name)))
            renderframestask.title = renderframestasktitle

            if (chunk+1) > 1 and by < 2 and (start+chunk < last+1):               
                iframe = start
                while (iframe < last+1):
                    diff = chunk
                    if ((iframe + chunk) > last+1):
                        diff = (last) - iframe
                    prmantasktitle = ("%s Frames: (%d-%d) (blender)" %
                                    (tasktitle, iframe, iframe+diff))

                    self.add_blender_render_task(iframe, renderframestask, prmantasktitle,
                                        bl_filename, None, chunk=diff) 
                    iframe += diff+1
            else:
                for iframe in range(start, last + 1, by):
                    prmantasktitle = ("%s Frame: %d (blender)" %
                                    (tasktitle, int(iframe)))

                    self.add_blender_render_task(iframe, renderframestask, prmantasktitle,
                                        bl_filename, img)

            parent_task.addChild(renderframestask)                                 

    def generate_rib_render_tasks(self, anim, parent_task, tasktitle,
                                start, last, by, threads):

        rm = self.bl_scene.renderman

        if anim is False:

            rib_expanded = string_utils.expand_string(rm.path_rib_output, 
                                                    frame=start, 
                                                    asFilePath=True)

            dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)    
            img_expanded = ''
            if not self.rman_scene.rman_bake:        
                img_expanded = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                    frame=start,
                                                    asFilePath=True)                                                          
                                                    
            frametasktitle = ("%s Frame: %d " %
                            (tasktitle, int(start)))
            frametask = author.Task()
            frametask.title = frametasktitle
            frametask.serialsubtasks = True

            prmantasktitle = "%s (render)" % frametasktitle

            self.add_prman_render_task(frametask, prmantasktitle, threads,
                                rib_expanded, img_expanded)
            
            parent_task.addChild(frametask)

        else:
            parent_task.serialsubtasks = True

            renderframestask = author.Task()
            renderframestask.serialsubtasks = False
            renderframestasktitle = ("Render Layer: %s "%
                                    (str(self.depsgraph.view_layer.name)))
            renderframestask.title = renderframestasktitle

            dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)                  

            for iframe in range(int(start), int(last + 1), int(by)):
                rib_expanded = string_utils.expand_string(rm.path_rib_output, 
                                                        frame=iframe, 
                                                        asFilePath=True)
                img_expanded = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                        frame=iframe,
                                                        asFilePath=True)         

                prmantasktitle = ("%s Frame: %d (prman)" %
                                (tasktitle, int(iframe)))

                self.add_prman_render_task(renderframestask, prmantasktitle, threads,
                                      rib_expanded, img_expanded)

            parent_task.addChild(renderframestask)

    def generate_aidenoise_tasks(self, start, last, by):
        tasktitle = "Denoiser Renders"
        parent_task = author.Task()
        parent_task.title = tasktitle          
        rm = self.bl_scene.renderman   
        dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)  
        
        img_files = list()
        have_variance = False
        for frame_num in range(start, last + 1, by):
            self.rman_render.bl_frame_current = frame_num
        
            variance_file = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                frame=frame_num,
                                                asFilePath=True)  

            for dspy,params in dspys_dict['displays'].items():
                if not params['denoise']:
                    continue
                if dspy == 'beauty':
                    if not have_variance:
                        have_variance = True
                    img_files.append(variance_file)
                else:
                    token_dict = {'aov': dspy}
                    aov_file = string_utils.expand_string(params['filePath'], 
                                            frame=frame_num,
                                            token_dict=token_dict,
                                            asFilePath=True)    
                    img_files.append(aov_file)      

        if not have_variance or len(img_files) < 1:
            return None

        do_cross_frame = (rm.ai_denoiser_mode == 'crossframe')
        

        if start == last:
            do_cross_frame = False

        cur_frame = self.rman_scene.bl_frame_current
        task = author.Task()
        if do_cross_frame:
            task.title = 'Denoise Frames %d - %d (Cross Frame)' % (start, last)
        else:
            task.title = 'Denoise Frames (%d - %d)' % (start, last)
        
        command = author.Command(local=False, service="PixarRender")                

        command.argv = ["denoise_batch"]        

        if do_cross_frame:
            command.argv.append('--crossframe')
        variance_file = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                            frame=1,
                                            asFilePath=True)              
        
        if rm.ai_denoiser_verbose:
            command.argv.append('-v')
        command.argv.append('-a')
        command.argv.append('%.3f' % rm.ai_denoiser_asymmetry)
        command.argv.append('-o')
        path = filepath_utils.get_real_path(rm.ai_denoiser_output_dir)
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(variance_file), 'denoised')
        command.argv.append(path)
        if rm.ai_denoiser_flow:
            command.argv.append('-f')
        command.argv.extend(img_files)
                                                         
        task.addCommand(command)
        parent_task.addChild(task) 

        self.rman_render.bl_frame_current = cur_frame
        return parent_task

    def generate_denoise_tasks(self, start, last, by):

        tasktitle = "Denoiser (Legacy) Renders"
        parent_task = author.Task()
        parent_task.title = tasktitle          
        rm = self.bl_scene.renderman           
        denoise_options = []
        if rm.denoise_cmd != '':
            denoise_options.append(rm.denoise_cmd)  
        if rm.denoise_gpu:
            denoise_options.append('--override')
            denoise_options.append('gpuIndex')
            denoise_options.append('0')
            denoise_options.append('--')     

        # any cross frame?
        do_cross_frame = False
        dspys_dict = display_utils.get_dspy_dict(self.rman_scene, expandTokens=False)  
        for dspy,params in dspys_dict['displays'].items():
                if not params['denoise']:
                    continue        
                if params['denoise_mode'] == 'crossframe':
                    do_cross_frame = True
                    break

        if start == last:
            do_cross_frame = False

        if do_cross_frame:
            # for crossframe, do it all in one task
            cur_frame = self.rman_scene.bl_frame_current
            task = author.Task()
            task.title = 'Denoise (Legacy) Cross Frame'
            command = author.Command(local=False, service="PixarRender")                

            command.argv = ["denoise_legacy"]
            for opt in denoise_options:
                command.argv.append(opt)                
            command.argv.append('--crossframe')  
            command.argv.append('-v')
            command.argv.append('variance')     
                                             
            for frame_num in range(start, last + 1, by):
                self.rman_render.bl_frame_current = frame_num
         
                variance_file = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                    frame=frame_num,
                                                    asFilePath=True)  

                f,ext = os.path.splitext(variance_file)  
                if not f.endswith('_variance'):
                    # check the variance filename for "_variance"
                    variance_file = f + '_variance' + ext

                for dspy,params in dspys_dict['displays'].items():
                    if not params['denoise']:
                        continue
                    
                    if dspy == 'beauty':
                        command.argv.append(variance_file)
                    else:
                        command.argv.append(variance_file)
                        token_dict = {'aov': dspy}
                        aov_file = string_utils.expand_string(params['filePath'], 
                                                frame=frame_num,
                                                token_dict=token_dict,
                                                asFilePath=True)    
                        command.argv.append(aov_file)
    
            task.addCommand(command)
            parent_task.addChild(task) 

        else:
            # singlframe
            cur_frame = self.rman_scene.bl_frame_current
            for frame_num in range(start, last + 1, by):
                self.rman_render.bl_frame_current = frame_num
         
                variance_file = string_utils.expand_string(dspys_dict['displays']['beauty']['filePath'], 
                                                    frame=frame_num,
                                                    asFilePath=True)    

                f,ext = os.path.splitext(variance_file)  
                if not f.endswith('_variance'):
                    # check the variance filename for "_variance"
                    variance_file = f + '_variance' + ext                                                                               

                for dspy,params in dspys_dict['displays'].items():
                    if not params['denoise']:
                        continue
                    
                    if params['denoise_mode'] != 'singleframe':
                        continue

                    task = author.Task()
                    task.title = 'Denoise (Legacy) Frame %d' % frame_num
                    command = author.Command(local=False, service="PixarRender")                

                    command.argv = ["denoise_legacy"]
                    for opt in denoise_options:
                        command.argv.append(opt)
                    if dspy == 'beauty':
                        command.argv.append(variance_file)
                    else:
                        command.argv.append(variance_file)
                        token_dict = {'aov': dspy}
                        aov_file = string_utils.expand_string(params['filePath'], 
                                                frame=frame_num,
                                                token_dict=token_dict,
                                                asFilePath=True)    
                        command.argv.append(aov_file)
    
                    task.addCommand(command)
                    parent_task.addChild(task) 

        self.rman_render.bl_frame_current = cur_frame
        return parent_task
                        
    def blender_batch_render(self, bl_filename):

        scene = self.bl_scene 
        rm = scene.renderman
        frame_begin = self.bl_scene.frame_start
        frame_end = self.bl_scene.frame_end
        frame_current = self.bl_scene.frame_current
        by = self.bl_scene.frame_step     
        chunk = min(rm.bl_batch_frame_chunk, frame_end)-1

        # update variables
        string_utils.set_var('scene', self.bl_scene.name.replace(' ', '_'))
        string_utils.set_var('layer', self.rman_scene.bl_view_layer.name.replace(' ', '_'))      

        if not rm.external_animation:
            frame_begin = self.bl_scene.frame_current
            frame_end = frame_begin

        job = author.Job()
        
        scene_name = self.bl_scene.name
        bl_view_layer = self.depsgraph.view_layer.name
        job_title = 'untitled' if not bpy.data.filepath else \
            os.path.splitext(os.path.split(bpy.data.filepath)[1])[0]
        job_title += ' %s ' % bl_view_layer
        job_title += " frames %d-%d" % (frame_begin, frame_end) if frame_end \
            else " frame %d" % frame_begin


        job.title = str(job_title)
        job.serialsubtasks = True
        job.service = 'PixarRender'
        self.add_job_level_attrs(job)

        frame_begin = self.bl_scene.frame_start
        frame_end = self.bl_scene.frame_end
        if not rm.external_animation:
            frame_begin = self.bl_scene.frame_current
            frame_end = frame_begin        

        tasktitle = "Render %s" % (str(scene_name))
        parent_task = author.Task()
        parent_task.title = tasktitle
        anim = (frame_begin != frame_end)

        self.generate_blender_batch_tasks(anim, parent_task, tasktitle,
                                frame_begin, frame_end, by, chunk, bl_filename)

        job.addChild(parent_task)                                

        # Don't generate denoise tasks if we're baking
        # or using the Blender compositor
        if rm.hider_type == 'RAYTRACE' and (not rm.use_bl_compositor or not scene.use_nodes):
            if rm.use_legacy_denoiser:
                parent_task = self.generate_denoise_tasks(frame_begin, frame_end, by)                               
            else:
                parent_task = self.generate_aidenoise_tasks(frame_begin, frame_end, by)                               
                
            if parent_task:
                job.addChild(parent_task)
        
        scene_filename = bpy.data.filepath
        if scene_filename == '':
            jobfile = string_utils.expand_string('<OUT>/<scene>.<layer>.alf', 
                                                asFilePath=True)            
        else:
            jobfile = os.path.splitext(scene_filename)[0] + '.%s.alf' % bl_view_layer.replace(' ', '_')

        stashFileCleanup = author.Command(local=False)
        stashFileCleanup.argv = ["TractorBuiltIn", "File", "delete",
                                 "%%D(%s)" % bl_filename]
        job.addCleanup(stashFileCleanup)

        jobFileCleanup = author.Command(local=False)
        jobFileCleanup.argv = ["TractorBuiltIn", "File", "delete",
                                 "%%D(%s)" % jobfile]
        job.addCleanup(jobFileCleanup)


        try:
            f = open(jobfile, 'w')
            as_tcl = job.asTcl()
            f.write(as_tcl)
            f.close()
        except IOError as ioe:
            rfb_log().error('IO Exception when writing job file %s: %s' % (jobfile, str(ioe)))
            return
        except Exception as e:
            rfb_log().error('Could not write job file %s: %s' % (jobfile, str(e)))
            return

        self.spool(job, jobfile)
        string_utils.update_frame_token(frame_current)

    
    def batch_render(self):

        scene = self.bl_scene 
        rm = scene.renderman
        frame_begin = self.bl_scene.frame_start
        frame_end = self.bl_scene.frame_end
        frame_current = self.bl_scene.frame_current        
        by = self.bl_scene.frame_step        

        if not rm.external_animation:
            frame_begin = self.bl_scene.frame_current
            frame_end = frame_begin

        job = author.Job()
        
        scene_name = self.bl_scene.name
        bl_view_layer = self.depsgraph.view_layer.name
        job_title = 'untitled' if not bpy.data.filepath else \
            os.path.splitext(os.path.split(bpy.data.filepath)[1])[0]
        job_title += ' %s ' % bl_view_layer
        job_title += " frames %d-%d" % (frame_begin, frame_end) if frame_end \
            else " frame %d" % frame_begin


        job.title = str(job_title)
        
        job.serialsubtasks = True
        job.service = 'PixarRender'
        self.add_job_level_attrs(job)

        threads = self.bl_scene.renderman.batch_threads
        anim = (frame_begin != frame_end)

        tasktitle = "Render %s" % (str(scene_name))
        parent_task = author.Task()
        parent_task.title = tasktitle

        self.generate_rib_render_tasks(anim, parent_task, tasktitle,
                                frame_begin, frame_end, by, threads)
        job.addChild(parent_task)

        # Don't denoise if we're baking
        if rm.hider_type == 'RAYTRACE':
            if rm.use_legacy_denoiser:
                parent_task = self.generate_denoise_tasks(frame_begin, frame_end, by)                               
            else:
                parent_task = self.generate_aidenoise_tasks(frame_begin, frame_end, by)
                
            if parent_task:
                job.addChild(parent_task)

        bl_filename = bpy.data.filepath
        if bl_filename == '':
            jobfile = string_utils.expand_string('<OUT>/<scene>.<layer>.alf', 
                                                asFilePath=True)            
        else:
            jobfile = os.path.splitext(bl_filename)[0] + '.%s.alf' % bl_view_layer.replace(' ', '_')        

        jobFileCleanup = author.Command(local=False)
        jobFileCleanup.argv = ["TractorBuiltIn", "File", "delete",
                                 "%%D(%s)" % jobfile]
        job.addCleanup(jobFileCleanup)

        try:
            f = open(jobfile, 'w')
            as_tcl = job.asTcl()
            f.write(as_tcl)
            f.close()
        except IOError as ioe:
            rfb_log().error('IO Exception when writing job file %s: %s' % (jobfile, str(ioe)))
            return
        except Exception as e:
            rfb_log().error('Could not write job file %s: %s' % (jobfile, str(e)))
            return

        self.spool(job, jobfile)
        string_utils.update_frame_token(frame_current)

    def spool(self, job, jobfile):

        env = dict(os.environ)
        # if $OCIO is undefined, use filmic blender config
        if not env.get('OCIO', None):
            env['OCIO'] = os.path.join(os.environ['RMANTREE'], 'lib', 'ocio', 'filmic-blender', 'config.ocio')

        for i in env:
            if not isinstance(env[i], str):
                env[i] = str(env[i])        

        args = list()

        if self.is_localqueue:
            lq = envconfig().rman_lq_path
            args.append(lq)
            args.append(jobfile)
            rfb_log().info('Spooling job to LocalQueue: %s.', jobfile)
            subprocess.Popen(args, env=env)
        else:
            # spool to tractor
            tractor_engine ='tractor-engine'
            tractor_port = '80'
            owner = getpass.getuser()

            tractor_cfg = rfb_config['tractor_cfg']
            tractor_engine = tractor_cfg.get('engine', tractor_engine)
            tractor_port = str(tractor_cfg.get('port', tractor_port))
            owner = tractor_cfg.get('user', owner)            

            # env var trumps rfb.json
            tractor_env = envconfig().getenv('TRACTOR_ENGINE')
            if tractor_env:
                tractor_env = tractor_env.split(':')
                tractor_engine = tractor_env[0]
                if len(tractor_env) > 1:
                    tractor_port = tractor_env[1]

            owner = envconfig().getenv('TRACTOR_USER', owner)            

            try:
                spoolhost = socket.gethostname()
                job.spool(block=True, spoolfile=jobfile, spoolhost=spoolhost,
                        owner=owner, hostname=tractor_engine,
                        port=int(tractor_port))
                rfb_log().info('Spooling to Tractor Engine: %s:%s, Job File: %s', tractor_engine,
                            tractor_port, jobfile)
            except author.SpoolError as spoolError:
                rfb_log().error("Cannot spool to Tractor: %s" % str(spoolError))

            except Exception as e:
                rfb_log().error("Cannot spool to Tractor: %s" % str(e))
                