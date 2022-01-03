from ..rfb_logger import rfb_log
from ..rfb_utils.prefs_utils import get_pref
from ..rfb_utils import filepath_utils
from ..rfb_utils.envconfig_utils import envconfig
import bpy
import os
import json

__RFB_TRANSLATIONS_DICT__ = dict()

def load_locale_file(jsonfile):
    global __RFB_TRANSLATIONS_DICT__
    jdata = json.load(open(jsonfile))

    locale_nm = jdata['locale']
    translation_dict = dict()
    for nm in jdata["translations"]:
        translation_data = jdata["translations"][nm]
        ctxt = translation_data['context']
        translation = translation_data['translation']
        translation_dict[(ctxt, nm)] = translation
    
    __RFB_TRANSLATIONS_DICT__[locale_nm] = translation_dict

def get_user_locales():
    paths = list()

    prefs_path = get_pref('rman_config_dir', default='')
    if prefs_path:
        prefs_path = filepath_utils.get_real_path(prefs_path)
        locale_path = os.path.join(prefs_path, 'locales')
        if os.path.exists(locale_path):
            paths.append(locale_path)

    # first, RFB_SITE_PATH
    RFB_SITE_PATH = envconfig().getenv('RFB_SITE_PATH')
    if RFB_SITE_PATH:
        for path in RFB_SITE_PATH.split(os.path.pathsep):
            locale_path = os.path.join(path, 'locales')
            if os.path.exists(locale_path):
                paths.append(locale_path)

    # next, RFB_SHOW_PATH
    RFB_SHOW_PATH = envconfig().getenv('RFB_SHOW_PATH')
    if RFB_SHOW_PATH:
        for path in RFB_SHOW_PATH.split(os.path.pathsep):
            locale_path = os.path.join(path, 'locales')
            if os.path.exists(locale_path):
                paths.append(locale_path)

    # finally, RFB_USER_PATH
    RFB_USER_PATH = envconfig().getenv('RFB_USER_PATH')
    if RFB_USER_PATH:
        for path in RFB_USER_PATH.split(os.path.pathsep):
            locale_path = os.path.join(path, 'locales')
            if os.path.exists(locale_path):
                paths.append(locale_path) 

    return paths

def register_locale_translations():
    rfb_log().debug("Loading factory translations:")
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    locales_dir = os.path.join(cur_dir, 'locales')    
    if os.path.exists(locales_dir):
        for f in os.listdir(locales_dir):
            if not f.endswith('.json'):
                continue  
            jsonfile = os.path.join(locales_dir, f)
            rfb_log().debug("\t%s" % f)
            load_locale_file(jsonfile)

    # load user translations
    for p in get_user_locales():
        if not os.path.exists(p):        
            continue
        rfb_log().debug("Loading user translations from: %s" % p)
        for f in os.listdir(p):
            if not f.endswith('.json'):
                continue  
            jsonfile = os.path.join(p, f)
            rfb_log().debug("\t%s" % f)
            load_locale_file(jsonfile)        

def register():
    register_locale_translations()
    bpy.app.translations.register(__name__, __RFB_TRANSLATIONS_DICT__)


def unregister():
    bpy.app.translations.unregister(__name__)