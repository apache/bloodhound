#
# LRU and LFU cache decorators - licensed under the PSF License
# Developed by Raymond Hettinger
# (http://code.activestate.com/recipes/498245-lru-and-lfu-cache-decorators/)
#
# March 13, 2013 updated by Olemis Lang
#    Added keymap arg to build custom keys out of actual args
# March 14, 2013 updated by Olemis Lang
#    Keep cache consistency on user function failure 

import collections
import functools
from itertools import ifilterfalse
from heapq import nsmallest
from operator import itemgetter

class Counter(dict):
    'Mapping where default values are zero'
    def __missing__(self, key):
        return 0

def lru_cache(maxsize=100, keymap=None):
    '''Least-recently-used cache decorator.

    Arguments to the cached function must be hashable.
    Cache performance statistics stored in f.hits and f.misses.
    Clear the cache with f.clear().
    http://en.wikipedia.org/wiki/Cache_algorithms#Least_Recently_Used

    :param keymap:    build custom keys out of actual arguments.
                      Its signature will be lambda (args, kwds, kwd_mark)
    '''
    maxqueue = maxsize * 10
    def decorating_function(user_function,
                            len=len, iter=iter, tuple=tuple, sorted=sorted, KeyError=KeyError):
        cache = {}                  # mapping of args to results
        queue = collections.deque() # order that keys have been used
        refcount = Counter()        # times each key is in the queue
        sentinel = object()         # marker for looping around the queue
        kwd_mark = object()         # separate positional and keyword args

        # lookup optimizations (ugly but fast)
        queue_append, queue_popleft = queue.append, queue.popleft
        queue_appendleft, queue_pop = queue.appendleft, queue.pop

        @functools.wraps(user_function)
        def wrapper(*args, **kwds):
            # cache key records both positional and keyword args
            if keymap is None:
                key = args
                if kwds:
                    key += (kwd_mark,) + tuple(sorted(kwds.items()))
            else:
                key = keymap(args, kwds, kwd_mark)

            # get cache entry or compute if not found
            try:
                result = cache[key]
                wrapper.hits += 1

                # record recent use of this key
                queue_append(key)
                refcount[key] += 1
            except KeyError:
                # Explicit exception handling for readability
                try:
                    result = user_function(*args, **kwds)
                except:
                    raise
                else:
                    # record recent use of this key
                    queue_append(key)
                    refcount[key] += 1

                cache[key] = result
                wrapper.misses += 1

                # purge least recently used cache entry
                if len(cache) > maxsize:
                    key = queue_popleft()
                    refcount[key] -= 1
                    while refcount[key]:
                        key = queue_popleft()
                        refcount[key] -= 1
                    del cache[key], refcount[key]

            # periodically compact the queue by eliminating duplicate keys
            # while preserving order of most recent access
            if len(queue) > maxqueue:
                refcount.clear()
                queue_appendleft(sentinel)
                for key in ifilterfalse(refcount.__contains__,
                    iter(queue_pop, sentinel)):
                    queue_appendleft(key)
                    refcount[key] = 1


            return result

        def clear():
            cache.clear()
            queue.clear()
            refcount.clear()
            wrapper.hits = wrapper.misses = 0

        wrapper.hits = wrapper.misses = 0
        wrapper.clear = clear
        return wrapper
    return decorating_function


def lfu_cache(maxsize=100, keymap=None):
    '''Least-frequenty-used cache decorator.

    Arguments to the cached function must be hashable.
    Cache performance statistics stored in f.hits and f.misses.
    Clear the cache with f.clear().
    http://en.wikipedia.org/wiki/Least_Frequently_Used

    :param keymap:    build custom keys out of actual arguments.
                      Its signature will be lambda (args, kwds, kwd_mark)
    '''
    def decorating_function(user_function):
        cache = {}                      # mapping of args to results
        use_count = Counter()           # times each key has been accessed
        kwd_mark = object()             # separate positional and keyword args

        @functools.wraps(user_function)
        def wrapper(*args, **kwds):
            if keymap is None:
                key = args
                if kwds:
                    key += (kwd_mark,) + tuple(sorted(kwds.items()))
            else:
                key = keymap(args, kwds, kwd_mark)
            use_count[key] += 1

            # get cache entry or compute if not found
            try:
                result = cache[key]
                wrapper.hits += 1
            except KeyError:
                result = user_function(*args, **kwds)
                cache[key] = result
                wrapper.misses += 1

                # purge least frequently used cache entry
                if len(cache) > maxsize:
                    for key, _ in nsmallest(maxsize // 10,
                        use_count.iteritems(),
                        key=itemgetter(1)):
                        del cache[key], use_count[key]

            return result

        def clear():
            cache.clear()
            use_count.clear()
            wrapper.hits = wrapper.misses = 0

        wrapper.hits = wrapper.misses = 0
        wrapper.clear = clear
        return wrapper
    return decorating_function

#----------------------
# Helper functions
#----------------------

def default_keymap(args, kwds, kwd_mark):
    key = args
    if kwds:
        key += (kwd_mark,) + tuple(sorted(kwds.items()))
    return key
