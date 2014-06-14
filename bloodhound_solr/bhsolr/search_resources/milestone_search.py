from bhsearch.search_resources.base import BaseIndexer
from trac.ticket import Milestone
from bhsearch.search_resources.milestone_search import MilestoneIndexer

class MilestoneSearchModel(BaseIndexer):

  def get_entries_for_index(self):
    for milestone in Milestone.select(self.env, include_completed=True):
      yield MilestoneIndexer(self.env).build_doc(milestone)
