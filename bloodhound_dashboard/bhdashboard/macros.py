from genshi.builder import tag
from trac.util.translation import _, cleandoc_
from trac.wiki.api import WikiSystem
from trac.wiki.macros import WikiMacroBase

from bhdashboard.admin import GUIDE_NAME

class UserGuideTocMacro(WikiMacroBase):
    _description = cleandoc_("""Display a Guide table of contents
    
    This macro provides the table-of-contents specific to the user Guide
    """
    )
    TOC = [('%(guide)s/Index',                    'Index'),
           ('%(guide)s/Install',                  'Installation'),
           ('%(guide)s/InterfaceCustomization',   'Customization'),
           ('%(guide)s/Plugins',                  'Plugins'),
           ('%(guide)s/Upgrade',                  'Upgrading'),
           ('%(guide)s/Ini',                      'Configuration'),
           ('%(guide)s/Admin',                    'Administration'),
           ('%(guide)s/Backup',                   'Backup'),
           ('%(guide)s/Logging',                  'Logging'),
           ('%(guide)s/Permissions' ,             'Permissions'),
           ('%(guide)s/Wiki',                     'The Wiki'),
           ('WikiFormatting',               'Wiki Formatting'),
           ('%(guide)s/Timeline',                 'Timeline'),
           ('%(guide)s/Browser',                  'Repository Browser'),
           ('%(guide)s/RevisionLog',              'Revision Log'),
           ('%(guide)s/Changeset',                'Changesets'),
           ('%(guide)s/Tickets',                  'Tickets'),
           ('%(guide)s/Workflow',                 'Workflow'),
           ('%(guide)s/Roadmap',                  'Roadmap'),
           ('%(guide)s/Query',                    'Ticket Queries'),
           ('%(guide)s/BatchModify',              'Batch Modify'),
           ('%(guide)s/Reports',                  'Reports'),
           ('%(guide)s/Rss',                      'RSS Support'),
           ('%(guide)s/Notification',             'Notification'),
          ]

    def expand_macro(self, formatter, name, args):
        curpage = formatter.resource.id

        # scoped TOC (e.g. TranslateRu/Guide or 0.X/Guide ...)
        prefix = ''
        guideprefix =  GUIDE_NAME + '/'
        data = {'guide': GUIDE_NAME,}
        idx = curpage.find('/')
        if idx > 0:
            prefix = curpage[:idx+1]
        if prefix.endswith(guideprefix):
            prefix = prefix[:len(prefix)-len(guideprefix)]
        ws = WikiSystem(self.env)
        return tag.div(
            tag.h4(_('Table of Contents')),
            tag.ul([tag.li(tag.a(title,
                                 href=formatter.href.wiki(prefix+ref % data),
                                 class_=(not ws.has_page(prefix+ref % data) and
                                         'missing')),
                           class_=(prefix+ref % data== curpage and 'active'))
                    for ref, title in self.TOC]),
            class_='wiki-toc')
