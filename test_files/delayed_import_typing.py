import typing

if typing.TYPE_CHECKING:
    import bmemcached  # noqa
    import memcache
    import pylibmc
    import pymemcache
else:  # noqa
    # delayed import
    bmemcached = None
    memcache = None
    pylibmc = None
    pymemcache = None
