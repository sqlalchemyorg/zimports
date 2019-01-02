from __future__ import print_function
import argparse
import ast
import pyflakes.checker
import pyflakes.messages
import sys
import os
import distutils
import difflib
import glob
import importlib
import pkgutil
import re
import time


def _rewrite_source(filename, source_lines, local_modules,
                    keep_threshhold=None, expand_stars=False):

    stats = {
        "starttime": time.time(),
        "names_from_star": 0, "star_imports_removed": 0}

    # parse the code.  get the imports and a collection of line numbers
    # we definitely don't want to discard
    imports, _, lines_with_code = _parse_toplevel_imports(
        filename, source_lines)

    original_imports = len(imports)
    if imports:
        imports_start_on = imports[0].lineno
    else:
        imports_start_on = 0

    # assemble a set of line numbers that will not be copied to the
    # output.  E.g. lines where import statements occurred, or the
    # extra lines they take up which we figure out by looking at the
    # "gap" between statements
    import_gap_lines = _get_import_discard_lines(
        filename, source_lines, imports, lines_with_code)

    # flatten imports into single import per line and rewrite
    # full source
    imports = list(
        _as_single_imports(imports, stats, expand_stars=expand_stars))
    on_singleline = _write_source(
        filename, source_lines, [imports], import_gap_lines, imports_start_on)

    # now parse again.  Because pyflakes won't tell us about unused
    # imports that are not the first import, we had to flatten first.
    imports, warnings, lines_with_code = _parse_toplevel_imports(
        filename, on_singleline)

    # now remove unused names from the imports
    # if number of imports is greater than keep_threshold% of the total
    # lines of code, don't remove names, assume this is like a
    # package file
    if not lines_with_code:
        stats['import_proportion'] = import_proportion = 0
    else:
        stats['import_proportion'] = import_proportion = (
            (
                (
                    len(imports) + stats['star_imports_removed'] -
                    stats['names_from_star']
                ) / float(len(lines_with_code))
            ) * 100)

    if (
        keep_threshhold is None or
            import_proportion < keep_threshhold
    ):
        _remove_unused_names(imports, warnings, stats)
    else:
        stats['removed_imports'] = 0

    stats['import_line_delta'] = len(imports) - original_imports

    future, stdlib, package, locals_ = _get_import_groups(
        imports, local_modules)

    rewritten = _write_source(
        filename, source_lines, [future, stdlib, package, locals_],
        import_gap_lines, imports_start_on)

    differ = list(difflib.Differ().compare(source_lines, rewritten))

    stats['added'] = len([l for l in differ if l.startswith('+ ')])
    stats['removed'] = len([l for l in differ if l.startswith('- ')])
    stats['is_changed'] = bool(stats["added"] or stats["removed"])
    stats['totaltime'] = time.time() - stats["starttime"]
    return rewritten, stats


def _get_import_discard_lines(
        filename, source_lines, imports, lines_with_code):
    """get line numbers that are part of imports but not in the AST."""

    import_gap_lines = {node.lineno for node in imports}

    prev = None
    for lineno in [node.lineno for node in imports] + [len(source_lines) + 1]:
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
        re.match(r"^\s*#", line) or
        re.match(r"^\s*'''", line) or
        re.match(r'^\s*"""', line)
    )


def _write_source(
        filename, source_lines, grouped_imports,
        import_gap_lines, imports_start_on):

    buf = []
    added_imports = False
    for lineno, line in enumerate(source_lines, 1):
        if lineno == imports_start_on:
            for j, imports in enumerate(grouped_imports):
                buf.extend(
                    _write_singlename_import(import_node)
                    for import_node in imports
                )
                if imports:
                    added_imports = True
                    buf.append("")

        if lineno not in import_gap_lines:
            # if we just added imports, suppress whitespace
            # until we get to a line
            if added_imports:
                if not line.rstrip():
                    continue
                else:
                    added_imports = False

            buf.append(line.rstrip())
    return buf


def _write_singlename_import(import_node):
    name = import_node.names[0]
    if isinstance(import_node, ast.Import):
        return "import %s%s" % (
            "%s as %s" % (name.name, name.asname)
            if name.asname else name.name,
            "  # noqa" if import_node.noqa else "")
    else:
        return "from %s%s import %s%s" % (
            "." * import_node.level,
            import_node.module or '',
            "%s as %s" % (name.name, name.asname)
            if name.asname else name.name,
            "  # noqa" if import_node.noqa else "")


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

    for import_node in imports:
        import_node.noqa = source_lines[import_node.lineno - 1].\
            rstrip().endswith("# noqa")

    return imports, warnings, lines_with_code


def _remove_unused_names(imports, warnings, stats):
    noqa_lines = set(
        import_node.lineno for import_node in imports if import_node.noqa
    )

    remove_imports = {
        (warning.message_args[0], warning.lineno)
        for warning in warnings.messages
        if isinstance(warning, pyflakes.messages.UnusedImport) and
        warning.lineno not in noqa_lines
    }

    removed_import_count = 0
    for import_node in imports:
        if isinstance(import_node, ast.ImportFrom):
            warning_key = (
                '.' * import_node.level
                if isinstance(import_node, ast.ImportFrom)
                else ''
            ) + (import_node.module + "." if import_node.module else '') + \
                ".".join(name.name for name in import_node.names)

            if (warning_key, import_node.lineno) in remove_imports:
                import_node.names = []
                removed_import_count += 1
        else:
            new = [
                name for name in import_node.names
                if (name.name, import_node.lineno) not in remove_imports
            ]

            removed_import_count += (len(import_node.names) - len(new))
            import_node.names[:] = new
    new_imports = [node for node in imports if node.names]

    stats['removed_imports'] = (
        removed_import_count - stats['names_from_star'] +
        stats['star_imports_removed']
    )

    imports[:] = new_imports


def _as_single_imports(import_nodes, stats, expand_stars=False):
    for import_node in import_nodes:
        if isinstance(import_node, ast.Import):
            for name in import_node.names:
                yield ast.Import(
                    parent=import_node.parent,
                    depth=import_node.depth,
                    names=[name],
                    col_offset=import_node.col_offset,
                    lineno=import_node.lineno,
                    noqa=import_node.noqa,
                )
        elif isinstance(import_node, ast.ImportFrom):
            for name in import_node.names:
                if name.name == '*' and expand_stars:
                    stats["star_imports_removed"] += 1
                    ast_cls = type(name)
                    module = importlib.import_module(import_node.module)
                    for star_name in getattr(module, '__all__', dir(module)):
                        stats['names_from_star'] += 1
                        yield ast.ImportFrom(
                            parent=import_node.parent,
                            depth=import_node.depth,
                            module=import_node.module,
                            level=import_node.level,
                            names=[ast_cls(star_name, asname=None)],
                            col_offset=import_node.col_offset,
                            lineno=import_node.lineno,
                            noqa=import_node.noqa,
                        )
                else:
                    yield ast.ImportFrom(
                        parent=import_node.parent,
                        depth=import_node.depth,
                        module=import_node.module,
                        level=import_node.level,
                        names=[name],
                        col_offset=import_node.col_offset,
                        lineno=import_node.lineno,
                        noqa=import_node.noqa,
                    )


def _get_import_groups(imports, local_modules):
    future = set()
    stdlib = set()
    package = set()
    locals_ = set()

    LAST = chr(127)

    local_modules = set(local_modules.split(","))

    for import_node in imports:
        assert len(import_node.names) == 1
        name = import_node.names[0].name

        if isinstance(import_node, ast.ImportFrom):
            module = import_node.module
            if import_node.level > 0:   # relative import
                locals_.add(import_node)
            elif not module or (
                    local_modules and
                    True in {module.startswith(mod) for mod in local_modules}):
                locals_.add(import_node)
            elif module and _is_future(module):
                future.add(import_node)
            elif module and _is_std_lib(module):
                stdlib.add(import_node)
            else:
                package.add(import_node)

            relative_prefix = LAST * import_node.level
            mod_tokens = module.split(".") if module else ['']
            if mod_tokens:
                mod_tokens[0] = relative_prefix + mod_tokens[0]
            else:
                mod_tokens = [relative_prefix]
            import_node._sort_key = tuple([
                token.lower() for token in mod_tokens] +
                ['', name.lower(), name]
            )
        else:
            if local_modules and \
                    True in {name.startswith(mod) for mod in local_modules}:
                locals_.add(import_node)
            elif _is_std_lib(name):
                stdlib.add(import_node)
            else:
                package.add(import_node)

            import_node._sort_key = (name.lower(), name)

    future = sorted(future, key=lambda n: n._sort_key)
    stdlib = sorted(stdlib, key=lambda n: n._sort_key)
    package = sorted(package, key=lambda n: n._sort_key)
    locals_ = sorted(locals_, key=lambda n: n._sort_key)
    return future, stdlib, package, locals_


def _lines_as_buffer(lines):
    return "\n".join(lines) + "\n"

STDLIB = None


def _is_future(module):
    return module == '__future__'


def _is_std_lib(module):
    global STDLIB
    if STDLIB is None:
        STDLIB = _get_stdlib_names()

    token = module.split(".")[0]
    return token in STDLIB


def _get_stdlib_names():
    # zzzeek uses 'import test' in some test suites and it's some kind of
    # fake stdlib thing
    not_stdlib = {'test'}

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

    return set(top_level_libs + list(modules | system_modules)) - not_stdlib


def main(argv=None):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-m", "--module", type=str,
        help="module prefix indicating local import "
             "(can be multiple comma separated)")
    parser.add_argument(
        "-k", "--keep-unused", action="store_true",
        help="keep unused imports even though detected as unused"
    )
    parser.add_argument(
        "--heuristic-unused", type=int,
        help="Remove unused imports only if number of imports is "
        "less than <HEURISTIC_UNUSED> percent of the total lines of code"
    )
    parser.add_argument(
        "-s", "--statsonly", action="store_true",
        help="don't write or display anything except the file stats"
    )
    parser.add_argument(
        "-e", "--expand-stars", action="store_true",
        help="Expand star imports into the names in the actual module, which "
        "can then have unused names removed.  Requires modules can be imported"
    )
    parser.add_argument(
        "-i", "--inplace", action="store_true",
        help="modify file in place")
    parser.add_argument('filename', nargs="+")

    options = parser.parse_args(argv)

    _get_stdlib_names()
    for filename in options.filename:
        with open(filename) as file_:
            source_lines = [line.rstrip() for line in file_]
        if options.keep_unused:
            if options.heuristic_unused:
                raise Exception(
                    "keep-unused and heuristic-unused are mutually exclusive")
            options.heuristic_unused = 0
        result, stats = _rewrite_source(
            filename, source_lines, options.module,
            keep_threshhold=options.heuristic_unused,
            expand_stars=options.expand_stars)
        totaltime = stats["totaltime"]
        if not stats['is_changed']:
            sys.stderr.write(
                "[Unchanged]     %s (in %.4f sec)\n" %
                (filename, totaltime)
            )
        else:
            sys.stderr.write(
                "%s    %s ([%d%% of lines are imports] "
                "[source +%dL/-%dL] [%d imports removed in %.4f sec])\n" %
                ("[Writing]   " if options.inplace and not options.statsonly
                 else "[Generating]",
                 filename, stats['import_proportion'], stats['added'],
                 stats['removed'],
                 stats['removed_imports'], totaltime)
            )

        if not options.statsonly:
            if options.inplace:
                if stats['is_changed']:
                    with open(filename, "w") as file_:
                        file_.write(_lines_as_buffer(result))
            else:
                sys.stdout.write(_lines_as_buffer(result))


if __name__ == '__main__':
    main()