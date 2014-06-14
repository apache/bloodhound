from bhsearch.search_resources.base import BaseIndexer
from trac.versioncontrol.api import RepositoryManager
from bhsearch.search_resources.changeset_search import ChangesetIndexer

class ChangesetSearchModel(BaseIndexer):

  def get_entries_for_index(self):
    repository_manager = RepositoryManager(self.env)
    for repository in repository_manager.get_real_repositories():
      rev = repository.oldest_rev
      stop = repository.youngest_rev
      while True:
        changeset = repository.get_changeset(rev)
        yield ChangesetIndexer(self.env).build_doc(changeset)
        if rev == stop:
          break
        rev = repository.next_rev(rev)
