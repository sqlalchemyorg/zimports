import argparse
import ast
import pyflakes.checker
import pyflakes.messages
import sys
import os
import distutils
import glob
import pkgutil
import re


def _do_thing(filename, source_lines, local_module):

    # parse the code.  get the imports and a collection of line numbers
    # we definitely don't want to discard
    imports, _, lines_with_code = _parse_toplevel_imports(
        filename, source_lines)

    # get line numbers that represent parts of a multiline import statement,
    # based on the gaps between the import nodes and the lines_with_code
    import_gap_lines = _get_import_discard_lines(
        filename, source_lines, imports, lines_with_code)

    imports = list(_as_single_imports(imports))

    on_singleline = _write_imports(
        filename, source_lines, [imports], import_gap_lines)

    imports, warnings, lines_with_code = _parse_toplevel_imports(
        filename, on_singleline)

    imports = list(_as_single_imports(imports, assert_=True))

    remove_imports = {
        (warning.message_args[0], warning.lineno)
        for warning in warnings.messages
        if isinstance(warning, pyflakes.messages.UnusedImport)
    }

    for import_node in imports:
        import_node.names[:] = [
            name for name in import_node.names
            if (name, import_node.lineno) not in remove_imports
        ]

    stdlib, package, locals_ = _get_import_groups(imports, local_module)

    done = _write_imports(
        filename, source_lines, [stdlib, package, locals_], import_gap_lines)

    print "\n".join(done)


def _get_import_discard_lines(
        filename, source_lines, imports, lines_with_code):
    """get extra lines that are part of imports but not in the AST.

    E.g.::

    1
    2
    3 from foo.bar import (
    4  x,
    5  y,
    6  z)
    7

    The parse for the above will only give us "3", but 4, 5, and 6 need
    to be discarded before we rewrite.


    """
    import_gap_lines = {node.lineno for node in imports}

    prev = None
    for lineno in [node.lineno for node in imports] + [len(source_lines)]:
        if prev is not None:
            for gap in range(prev + 1, lineno):
                if gap in lines_with_code:
                    # a codeline is here, so we definitely
                    # are not in an import anymore, go to the next one
                    break
                elif not _is_whitespace_or_comment(source_lines[gap - 1]):
                    import_gap_lines.add(gap)
        prev = lineno

    return import_gap_lines


def _is_whitespace_or_comment(line):
    return bool(
        re.match(r"^\s*$", line) or
        re.match(r"^\s*#", line)
    )


def _write_imports(filename, source_lines, grouped_imports, import_gap_lines):
    imports_start_on = min(
        import_node.lineno
        for group in grouped_imports for import_node in group)

    buf = []
    for lineno, line in enumerate(source_lines, 1):
        if lineno == imports_start_on:
            for imports in grouped_imports:
                buf.extend(
                    _write_singlename_import(import_node)
                    for import_node in imports
                )
                buf.append("")

        if lineno not in import_gap_lines:
            buf.append(line.rstrip())
    return buf


def _write_singlename_import(import_node):
    name = import_node.names[0]
    if isinstance(import_node, ast.Import):
        return "import %s" % (
            "%s as %s" % (name.name, name.asname)
            if name.asname else name.name)
    else:
        return "from %s%s import %s" % (
            "." * import_node.level,
            import_node.module or '',
            "%s as %s" % (name.name, name.asname)
            if name.asname else name.name)


def _parse_toplevel_imports(filename, source_lines):
    source = "\n".join(source_lines)

    tree = ast.parse(source, filename)

    lines_with_code = set(
        node.lineno for node in ast.walk(tree)
        if hasattr(node, 'lineno')
    )
    # running the Checker also creates the "node.parent"
    # attribute which is helpful
    warnings = pyflakes.checker.Checker(tree, filename)
    imports = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom)) and
        isinstance(node.parent, ast.Module)
    ]
    return imports, warnings, lines_with_code


def _as_single_imports(import_nodes, assert_=False):
    for import_node in import_nodes:
        if isinstance(import_node, ast.Import):
            if assert_:
                assert len(import_node.names) == 1
            for name in import_node.names:
                yield ast.Import(
                    parent=import_node.parent,
                    depth=import_node.depth,
                    names=[name],
                    col_offset=import_node.col_offset,
                    lineno=import_node.lineno,
                    _sort_key=(name.name, )
                )
        elif isinstance(import_node, ast.ImportFrom):
            if assert_:
                assert len(import_node.names) == 1
            for name in import_node.names:
                yield ast.ImportFrom(
                    parent=import_node.parent,
                    depth=import_node.depth,
                    module=import_node.module,
                    level=import_node.level,
                    names=[name],
                    col_offset=import_node.col_offset,
                    lineno=import_node.lineno,
                    _sort_key=(
                        tuple(import_node.module.split("."))
                        if import_node.module else ()
                    ) + (name.name, )
                )


def _get_import_groups(imports, local_module):
    stdlib = set()
    package = set()
    locals_ = set()

    for import_node in imports:
        if isinstance(import_node, ast.ImportFrom) and (
            import_node.module is None or
            local_module and import_node.module.startswith(local_module)
        ):
            locals_.add(import_node)
        elif isinstance(import_node, ast.Import) and (

            local_module and import_node.names[0].name.startswith(local_module)
        ):
            locals_.add(import_node)

        elif isinstance(import_node, ast.ImportFrom) and \
                _is_std_lib(import_node.module):
            stdlib.add(import_node)
        elif isinstance(import_node, ast.Import) and \
                _is_std_lib(import_node.names[0].name):
            stdlib.add(import_node)
        else:
            package.add(import_node)

    stdlib = sorted(stdlib, key=lambda n: n._sort_key)
    package = sorted(package, key=lambda n: n._sort_key)
    locals_ = sorted(locals_, key=lambda n: n._sort_key)

    return stdlib, package, locals_


STDLIB = None


def _is_std_lib(module):
    global STDLIB
    if STDLIB is None:
        STDLIB = _get_stdlib_names()

    token = module.split(".")[0]
    return token in STDLIB


def _get_stdlib_names():
    # https://stackoverflow.com/a/37243423/34549
    # Get list of the loaded source modules on sys.path.
    modules = {module
               for _, module, package in list(pkgutil.iter_modules())
               if package is False}

    # Glob all the 'top_level.txt' files installed under site-packages.
    site_packages = glob.iglob(os.path.join(
        os.path.dirname(os.__file__) + '/site-packages',
        '*-info', 'top_level.txt'))

    # Read the files for the import names and remove them from the
    # modules list.
    modules -= {open(txt).read().strip() for txt in site_packages}

    # Get the system packages.
    system_modules = set(sys.builtin_module_names)

    # Get the just the top-level packages from the python install.
    python_root = distutils.sysconfig.get_python_lib(standard_lib=True)
    _, top_level_libs, _ = list(os.walk(python_root))[0]

    return set(top_level_libs + list(modules | system_modules))


def main(argv=None):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-m", "--module", type=str,
        help="module prefix indicating local import")
    parser.add_argument('filename', nargs="+")

    options = parser.parse_args(argv)

    _get_stdlib_names()
    for filename in options.filename:
        with open(filename) as file_:
            source_lines = [line.rstrip() for line in file_]
        _do_thing(filename, source_lines, options.module)

if __name__ == '__main__':
    main()