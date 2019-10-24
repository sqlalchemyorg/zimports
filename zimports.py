from __future__ import print_function

import argparse
import ast
import collections
import configparser
import difflib
import importlib
import os
import re
import sys
import time

import flake8_import_order as f8io
from flake8_import_order.styles import lookup_entry_point
import pyflakes.checker
import pyflakes.messages


def _rewrite_source(options, filename, source_lines):

    keep_threshhold = options.heuristic_unused
    expand_stars = options.expand_stars
    style_entry_point = lookup_entry_point(options.style)
    style = style_entry_point.load()

    stats = {
        "starttime": time.time(),
        "names_from_star": 0,
        "star_imports_removed": 0,
        "removed_imports": 0,
    }

    # parse the code.  get the imports and a collection of line numbers
    # we definitely don't want to discard
    imports, _, lines_with_code = _parse_toplevel_imports(
        options, filename, source_lines
    )

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
        filename, source_lines, imports, lines_with_code
    )

    # flatten imports into single import per line and rewrite
    # full source
    if options.force_single_line:
        imports = list(
            _dedupe_single_imports(
                _as_single_imports(imports, stats, expand_stars=expand_stars),
                stats,
            )
        )

    on_source_lines = _write_source(
        source_lines, imports, [],
        import_gap_lines, imports_start_on,
        style
    )
    # now parse again.  Because pyflakes won't tell us about unused
    # imports that are not the first import, we had to flatten first.
    imports, warnings, lines_with_code = _parse_toplevel_imports(
        options, filename, on_source_lines, drill_for_warnings=True
    )

    # now remove unused names from the imports
    # if number of imports is greater than keep_threshold% of the total
    # lines of code, don't remove names, assume this is like a
    # package file
    if not lines_with_code:
        stats["import_proportion"] = import_proportion = 0
    else:
        stats["import_proportion"] = import_proportion = (
            (
                len(imports)
                + stats["star_imports_removed"]
                - stats["names_from_star"]
            )
            / float(len(lines_with_code))
        ) * 100

    if keep_threshhold is None or import_proportion < keep_threshhold:
        _remove_unused_names(imports, warnings, stats)

    stats["import_line_delta"] = len(imports) - original_imports

    sorted_imports, nosort_imports = sort_imports(style, imports, options)

    rewritten = _write_source(
        source_lines,
        sorted_imports,
        nosort_imports,
        import_gap_lines,
        imports_start_on,
        style
    )

    differ = list(difflib.Differ().compare(source_lines, rewritten))

    stats["added"] = len([l for l in differ if l.startswith("+ ")])
    stats["removed"] = len([l for l in differ if l.startswith("- ")])
    stats["is_changed"] = bool(stats["added"] or stats["removed"])
    stats["totaltime"] = time.time() - stats["starttime"]
    return rewritten, stats


def _get_import_discard_lines(
    filename, source_lines, imports, lines_with_code
):
    """Get line numbers that are part of imports but not in the AST."""

    import_gap_lines = {node.lineno for node in imports}

    intermediary_whitespace_lines = []

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

    # now search for whitespace intermingled in the imports that does
    # not include any non-import code
    sorted_gap_lines = list(sorted(import_gap_lines))
    for index, gap_line in enumerate(sorted_gap_lines[0:-1]):
        for lineno in range(gap_line + 1, sorted_gap_lines[index + 1]):
            if not source_lines[lineno - 1].rstrip():
                intermediary_whitespace_lines.append(lineno)
            else:
                intermediary_whitespace_lines[:] = []
        if intermediary_whitespace_lines:
            import_gap_lines = import_gap_lines.union(
                intermediary_whitespace_lines
            )
            intermediary_whitespace_lines[:] = []

    return import_gap_lines


def _is_whitespace_or_comment(line):
    return bool(
        re.match(r"^\s*$", line)
        or re.match(r"^\s*#", line)
        or re.match(r"^\s*'''", line)
        or re.match(r'^\s*"""', line)
    )


def _write_source(
    source_lines,
    imports,
    nosort_imports,
    import_gap_lines,
    imports_start_on,
    style,
):
    buf = []
    previous_import = None
    for lineno, line in enumerate(source_lines, 1):
        if lineno == imports_start_on:
            for import_node in imports:
                if (
                    previous_import is not None
                    and not style.same_section(
                        previous_import, import_node
                    )
                ):
                    buf.append("")
                previous_import = import_node
                buf.append(_write_import(import_node))

            for import_node in nosort_imports:
                if previous_import is not None:
                    buf.append("")
                    previous_import = None
                buf.append(_write_import(import_node))

        if lineno not in import_gap_lines:
            buf.append(line.rstrip())
    return buf


def _write_import(import_node):
    names = import_node.render_ast_names
    modules = []
    for name in names:
        if name.asname:
            modules.append("%s as %s" % (name.name, name.asname))
        else:
            modules.append(name.name)
    modules.sort(key=lambda x: x.lower())
    modules = ", ".join(modules)
    if not import_node.is_from:
        return "import %s%s%s" % (
            modules,
            "  # noqa" if import_node.noqa else "",
            " nosort" if import_node.nosort else "",
        )
    else:
        return "from %s%s import %s%s%s" % (
            "." * import_node.level,
            import_node.modules[0] or "",
            modules,
            "  # noqa" if import_node.noqa else "",
            " nosort" if import_node.nosort else "",
        )


class ClassifiedImport(
    collections.namedtuple(
        "ClassifiedImport",
        [
            "type",
            "is_from",
            "modules",
            "names",
            "lineno",
            "level",
            "package",
            "ast_names",
            "render_ast_names",
            "noqa",
            "nosort",
        ],
    )
):
    def __hash__(self):
        return hash((self.type, self.is_from, self.lineno))

    def __eq__(self, other):
        return (
            self.type == other.type
            and self.is_from == other.is_from
            and self.lineno == other.lineno
        )

    @property
    def pyflakes_warning_keys(self):
        # generate keys that match what pyflakes reports in its
        # warning messages in order to match dupes found
        if not self.is_from:
            return [(ast_name.name, ast_name) for ast_name in self.ast_names]
        else:
            return [
                (
                    (
                        ("." * self.level)
                        + (self.modules[0] + "." if self.modules[0] else "")
                        + (
                            "%s as %s" % (ast_name.name, ast_name.asname)
                            if ast_name.asname
                            else ast_name.name
                        )
                    ),
                    ast_name,
                )
                for ast_name in self.ast_names
            ]


class ImportVisitor(f8io.ImportVisitor):
    def __init__(
        self, source_lines, application_import_names, application_package_names
    ):
        self.imports = []
        self.source_lines = source_lines
        self.application_import_names = frozenset(application_import_names)
        self.application_package_names = frozenset(application_package_names)

    def _get_flags(self, lineno):
        line = self.source_lines[lineno - 1].rstrip()
        symbols = re.match(r".* # noqa( nosort)?", line)
        noqa = nosort = False
        if symbols:
            noqa = True
            if symbols.group(1):
                nosort = True
        return noqa, nosort

    def visit_Import(self, node):  # noqa: N802
        if node.col_offset == 0:
            modules = [alias.name for alias in node.names]
            types_ = {self._classify_type(module) for module in modules}
            if len(types_) == 1:
                type_ = types_.pop()
            else:
                type_ = f8io.ImportType.MIXED
            noqa, nosort = self._get_flags(node.lineno)
            classified_import = ClassifiedImport(
                type_,
                False,
                modules,
                [],
                node.lineno,
                0,
                f8io.root_package_name(modules[0]),
                node.names,
                list(node.names),
                noqa,
                nosort,
            )
            self.imports.append(classified_import)

    def visit_ImportFrom(self, node):  # noqa: N802
        if node.col_offset == 0:
            module = node.module or ""
            if node.level > 0:
                type_ = f8io.ImportType.APPLICATION_RELATIVE
            else:
                type_ = self._classify_type(module)
            names = [alias.name for alias in node.names]
            noqa, nosort = self._get_flags(node.lineno)
            classified_import = ClassifiedImport(
                type_,
                True,
                [module],
                names,
                node.lineno,
                node.level,
                f8io.root_package_name(module),
                node.names,
                list(node.names),
                noqa,
                nosort,
            )
            self.imports.append(classified_import)


def _parse_toplevel_imports(
    options, filename, source_lines, drill_for_warnings=False
):
    source = "\n".join(source_lines)

    tree = ast.parse(source, filename)

    lines_with_code = set(
        node.lineno for node in ast.walk(tree) if hasattr(node, "lineno")
    )

    warnings = pyflakes.checker.Checker(tree, filename)

    if drill_for_warnings:
        warnings_set = _drill_for_warnings(filename, source_lines, warnings)
    else:
        warnings_set = None

    f8io_visitor = ImportVisitor(
        source_lines,
        options.application_import_names.split(","),
        options.application_package_names.split(","),
    )
    f8io_visitor.visit(tree)
    imports = f8io_visitor.imports
    return imports, warnings_set, lines_with_code


def _drill_for_warnings(filename, source_lines, warnings):
    # pyflakes doesn't warn for all occurrences of an unused import
    # if that same symbol is repeated, so run over and over again
    # until we find every possible warning.  assumes single-line
    # imports

    source_lines = list(source_lines)
    warnings_set = set()
    seen_lineno = set()
    while True:
        has_warnings = False
        for warning in warnings.messages:
            if (
                not isinstance(warning, pyflakes.messages.UnusedImport)
                or warning.lineno in seen_lineno
            ):
                continue

            # we only deal with "top level" imports for now. imports
            # inside of conditionals or in defs aren't counted.
            whitespace = re.match(
                r"^\s*", source_lines[warning.lineno - 1]
            ).group(0)
            if whitespace:
                continue
            has_warnings = True
            warnings_set.add((warning.message_args[0], warning.lineno))

            # replace the line with nothing so that we approach no more
            # warnings generated. note this would be much trickier if we are
            # trying to deal with imports inside conditionals/defs
            source_lines[warning.lineno - 1] = ""
            seen_lineno.add(warning.lineno)

        if not has_warnings:
            break

        source = "\n".join(source_lines)
        tree = ast.parse(source, filename)
        warnings = pyflakes.checker.Checker(tree, filename)

    return warnings_set


def _remove_unused_names(imports, warnings, stats):
    noqa_lines = set(
        import_node.lineno for import_node in imports if import_node.noqa
    )

    remove_imports = {
        (name, lineno) for name, lineno in warnings if lineno not in noqa_lines
    }

    removed_import_count = 0
    for import_node in imports:
        # generate a key that matches the key we get from
        # pyflakes to match up
        new = [
            ast_name
            for warning_key, ast_name in import_node.pyflakes_warning_keys
            if (warning_key, import_node.lineno) not in remove_imports
        ]
        removed_import_count += len(import_node.ast_names) - len(new)
        import_node.render_ast_names[:] = new
    new_imports = [node for node in imports if node.render_ast_names]

    stats["removed_imports"] += (
        removed_import_count
        - stats["names_from_star"]
        + stats["star_imports_removed"]
    )

    imports[:] = new_imports


def _dedupe_single_imports(import_nodes, stats):

    seen = {}
    orig_order = []

    for import_node in import_nodes:
        if not import_node.is_from:
            assert len(import_node.ast_names) == 1
            hash_key = (
                import_node.ast_names[0].name,
                import_node.ast_names[0].asname,
            )
        else:
            assert len(import_node.ast_names) == 1
            hash_key = (
                import_node.modules[0],
                import_node.level,
                import_node.ast_names[0].name,
                import_node.ast_names[0].asname,
            )

        orig_order.append((import_node, hash_key))

        if hash_key in seen:
            if import_node.noqa and not seen[hash_key].noqa:
                seen[hash_key] = import_node
        else:
            seen[hash_key] = import_node

    for import_node, hash_key in orig_order:
        if seen[hash_key] is import_node:
            yield import_node
        else:
            stats["removed_imports"] += 1


def _as_single_imports(import_nodes, stats, expand_stars=False):

    for import_node in import_nodes:
        if not import_node.is_from:
            for ast_name in import_node.ast_names:
                yield ClassifiedImport(
                    import_node.type,
                    import_node.is_from,
                    [ast_name.name],
                    [],
                    import_node.lineno,
                    import_node.level,
                    import_node.package,
                    [ast_name],
                    [ast_name],
                    import_node.noqa,
                    import_node.nosort,
                )
        else:
            for ast_name in import_node.ast_names:
                if ast_name.name == "*" and expand_stars:
                    stats["star_imports_removed"] += 1
                    ast_cls = type(ast_name)
                    module = importlib.import_module(import_node.modules[0])
                    for star_name in getattr(module, "__all__", dir(module)):
                        stats["names_from_star"] += 1
                        yield ClassifiedImport(
                            import_node.type,
                            import_node.is_from,
                            import_node.modules,
                            [star_name],
                            import_node.lineno,
                            import_node.level,
                            import_node.package,
                            [ast_cls(star_name, asname=None)],
                            [ast_cls(star_name, asname=None)],
                            import_node.noqa,
                            import_node.nosort,
                        )
                else:
                    yield ClassifiedImport(
                        import_node.type,
                        import_node.is_from,
                        import_node.modules,
                        [ast_name.name],
                        import_node.lineno,
                        import_node.level,
                        import_node.package,
                        [ast_name],
                        [ast_name],
                        import_node.noqa,
                        import_node.nosort,
                    )


def sort_imports(style, imports, options):
    tosort = []
    nosort = []

    for import_node in imports:
        if options.force_single_line:
            assert len(import_node.ast_names) == 1

        if import_node.nosort:
            nosort.append(import_node)
        else:
            tosort.append(import_node)

    sorted_ = sorted(tosort, key=lambda n: style.import_key(n))
    return sorted_, nosort


def _lines_with_newlines(lines):
    for line in lines:
        yield line + "\n"


def _run_file(options, filename):
    with open(filename) as file_:
        source_lines = [line.rstrip() for line in file_]
    if options.keep_unused:
        if options.heuristic_unused:
            raise Exception(
                "keep-unused and heuristic-unused are mutually exclusive"
            )
        options.heuristic_unused = 0
    result, stats = _rewrite_source(options, filename, source_lines)
    totaltime = stats["totaltime"]
    if not stats["is_changed"]:
        sys.stderr.write(
            "[Unchanged]     %s (in %.4f sec)\n" % (filename, totaltime)
        )
    else:
        sys.stderr.write(
            "%s    %s ([%d%% of lines are imports] "
            "[source +%dL/-%dL] [%d imports removed in %.4f sec])\n"
            % (
                "[Writing]   "
                if not options.diff
                and not options.statsonly
                and not options.stdout
                else "[Generating]",
                filename,
                stats["import_proportion"],
                stats["added"],
                stats["removed"],
                stats["removed_imports"],
                totaltime,
            )
        )

    if not options.statsonly:
        if options.stdout:
            sys.stdout.writelines(_lines_with_newlines(result))
        elif options.diff:
            sys.stdout.writelines(
                difflib.unified_diff(
                    list(_lines_with_newlines(source_lines)),
                    list(_lines_with_newlines(result)),
                    fromfile=filename,
                    tofile=filename,
                )
            )
        else:
            if stats["is_changed"]:
                with open(filename, "w") as file_:
                    file_.writelines(_lines_with_newlines(result))


def main(argv=None):
    parser = argparse.ArgumentParser()

    config = configparser.ConfigParser()
    config["flake8"] = {
        "application-import-names": "",
        "application-package-names": "",
        "import-order-style": "google",
    }
    config.read("setup.cfg")

    parser.add_argument(
        "-m",
        "--application-import-names",
        type=str,
        default=config["flake8"]["application-import-names"],
        help="comma separated list of names that should be considered local "
        "to the application.  reads from [flake8] application-import-names "
        "by default.",
    )
    parser.add_argument(
        "-p",
        "--application-package-names",
        type=str,
        default=config["flake8"]["application-package-names"],
        help="comma separated list of names that should be considered local "
        "to the organization.  reads from [flake8] application-package-names "
        "by default.",
    )
    parser.add_argument(
        "--style",
        type=str,
        default=config["flake8"]["import-order-style"],
        help="import order styling, reads from "
        "[flake8] import-order-style by default, or defaults to 'google'",
    )
    parser.add_argument(
        "-f",
        "--force-single-line",
        type=bool,
        default=True,
        help="If set to true - instead of wrapping multi-line from style imports, "
             "each import will be forced to display on its own line"
    )
    parser.add_argument(
        "-k",
        "--keep-unused",
        action="store_true",
        help="keep unused imports even though detected as unused",
    )
    parser.add_argument(
        "--heuristic-unused",
        type=int,
        help="Remove unused imports only if number of imports is "
        "less than <HEURISTIC_UNUSED> percent of the total lines of code",
    )
    parser.add_argument(
        "--statsonly",
        action="store_true",
        help="don't write or display anything except the file stats",
    )
    parser.add_argument(
        "-e",
        "--expand-stars",
        action="store_true",
        help="Expand star imports into the names in the actual module, which "
        "can then have unused names removed.  Requires modules can be "
        "imported",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="don't modify files, just dump out diffs",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="dump file output to stdout"
    )
    parser.add_argument(
         "filename", nargs="+", help="Python filename(s) or directories")

    options = parser.parse_args(argv)

    for filename in options.filename:
        if os.path.isdir(filename):
            for root, dirs, files in os.walk(filename):
                for file in files:
                    if file.endswith(".py"):
                        _run_file(options, os.path.join(root, file))

        else:
            _run_file(options, filename)


if __name__ == "__main__":
    main()
