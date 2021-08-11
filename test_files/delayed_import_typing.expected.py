import typing

if typing.TYPE_CHECKING:
    import bmemcached
    import memcache
    import pylibmc
    import pymemcache
else:
    # delayed import
    bmemcached = None
    memcache = None
    pylibmc = None
    pymemcache = None
