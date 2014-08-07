from trac.web.api import ITemplateStreamFilter
from genshi.filters import Transformer
import re
from trac.core import Component, implements, TracError
from genshi.input import HTML

class BloodhoundSolrTemplate(Component):
  implements (ITemplateStreamFilter)

  def filter_stream(self, req, method, filename, stream, data):
    html = HTML(u'''<br></br><a href="porc" class="btn" style="margin: 10px 10px 10px 0px;">More like this</a>''')

    if re.match(r'/bhsearch', req.path_info):
      filter = Transformer('//dl[@id="results"]/dd/span[@class="date"]')
      stream |= filter.append(html)

    return stream
