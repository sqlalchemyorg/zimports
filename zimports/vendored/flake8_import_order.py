import sys

if sys.version_info >= (3, 10):
    import importlib.metadata as importlib_metadata
else:
    import importlib_metadata


def lookup_entry_point(name):
    try:
        (ep,) = importlib_metadata.entry_points(
            name=name, group="flake8_import_order.styles"
        )
        return ep
    except ValueError:
        raise LookupError("Unknown style {}".format(name))
