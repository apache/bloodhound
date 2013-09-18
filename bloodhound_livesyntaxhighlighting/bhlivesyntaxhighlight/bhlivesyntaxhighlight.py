import pkg_resources
import re

from trac.core import *
from trac.util.html import html
from trac.web.api import IRequestFilter
from trac.web.chrome import ITemplateProvider, add_stylesheet,add_script

class LiveSyntaxHighlightingPlugin(Component):
    implements (IRequestFilter, ITemplateProvider)

    ### IRequestFilter methods

    ### Future implementation ###
    # def match_request(self, req):
    #     if re.match(r'.*?(/wiki/)', req.path_info) or re.match(r'/wiki/', 
    #         req.path_info):
    #         if req.args['action'] == "edit":
    #             return True

    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, content_type):
        flag = ""
        if re.match(r'.*?(/wiki/)', req.path_info) or re.match(r'/wiki/', 
            req.path_info):
            flag = req.args.get('action')

        if flag == "edit":

            ### Future implementation ###
            # defaults = {}
            # prefs = dict((key, req.session.get('wiki_%s' % key,
            # defaults.get(key)))
            #     for key in ('editrows','sidebyside','livesyntaxhighlight'))
            # if 'from_editor' in req.args:
            #     livesyntaxhighlight = req.args.get('livesyntaxhighlight') 
            # or None
            #     if livesyntaxhighlight != prefs['livesyntaxhighlight']:
            #         req.session.set('wiki_livesyntaxhighlight', 
            #             int(bool(livesyntaxhighlight)), 1)
            # else:
            #     livesyntaxhighlight = prefs['livesyntaxhighlight']
            # if livesyntaxhighlight:
            add_script(req, 'livesyntaxhighlight/js/codemirror.js')
            add_script(req, 'livesyntaxhighlight/js/wikimarkup.js')
            add_stylesheet(req, 'livesyntaxhighlight/css/codemirror.css')
            add_stylesheet(req, 'livesyntaxhighlight/css/wikimarkup.css')
            add_script(req, "livesyntaxhighlight/js/livesyntaxhighlight.js")

            ### Future implementation ###
            # data.update({'livesyntaxhighlight', livesyntaxhighlight})
            # self.env.log(data)
            # self.env.log(template)
            return template, data, content_type 
        else:
            self.log.debug("Condition not satisfied ")
            return template, data, content_type


    ### ITemplateProvider methods
    def get_templates_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [resource_filename('bhlivesyntaxhighlight', 'templates')]    

    def get_htdocs_dirs(self):
        resource_filename = pkg_resources.resource_filename
        return [('livesyntaxhighlight', 
            resource_filename('bhlivesyntaxhighlight', 'htdocs'))]