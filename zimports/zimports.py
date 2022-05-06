import ast
from ast import parse
import codecs
import dataclasses as dc
import difflib
import enum
from functools import partial
import importlib
import io
from multiprocessing import Pool
import os
import re
import sys
import time
from typing import Any
from typing import Iterable
from typing import Iterator
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Set
from typing import Tuple

import flake8_import_order as f8io
from flake8_import_order.styles import lookup_entry_point
import pyflakes.checker
import pyflakes.messages

from .vendored.flake8 import matches_filename
from .vendored.flake8 import normalize_path


class RewritePass(enum.Enum):
    PLAIN = 0
    TYPE_CHECK = 1
    ANTI_TYPE_CHECK = 2


@dc.dataclass
class Rewriter:
    options: Any
    filename: str
    source_lines: List[str]

    def __post_init__(self):
        self.keep_threshhold: float = self.options.heuristic_unused
        self.expand_stars: bool = self.options.expand_stars
        style_entry_point = lookup_entry_point(self.options.style)
        self.style = style_entry_point.load()

        self.stats = {
            "starttime": time.time(),
            "names_from_star": 0,
            "star_imports_removed": 0,
            "removed_imports": 0,
        }

    def _do_rewrite(
        self, source_lines: List[str], type_check_pass: RewritePass
    ):
        if type_check_pass in (
            RewritePass.TYPE_CHECK,
            RewritePass.ANTI_TYPE_CHECK,
        ):
            # Stats are collected only on the non type check pass.
            stats = self.stats.copy()
            type_checking_blocks = TypeCheckingBlocks(
                source_lines, type_check_pass
            )
        else:
            stats = self.stats
            type_checking_blocks = None
        # parse the code.  get the imports and a collection of line numbers
        # we definitely don't want to discard
        imports, _, lines_with_code = _parse_toplevel_imports(
            self.options, self.filename, source_lines, type_checking_blocks
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
        import_gap_lines: Set[int] = _get_import_discard_lines(
            source_lines, imports, lines_with_code
        )

        # flatten imports into single import per line and rewrite
        # full source
        if not self.options.multi_imports:
            imports = list(
                _dedupe_single_imports(
                    _as_single_imports(
                        imports, stats, expand_stars=self.expand_stars
                    ),
                    stats,
                )
            )
        on_source_lines = _write_source(
            source_lines,
            imports,
            [],
            import_gap_lines,
            imports_start_on,
            self.style,
        )
        if type_check_pass is not RewritePass.PLAIN:
            TypeCheckingBlocks(
                on_source_lines, type_check_pass
            ).remove_empty_blocks(on_source_lines)
            type_checking_blocks = TypeCheckingBlocks(
                on_source_lines, type_check_pass
            )
        # now parse again.  Because pyflakes won't tell us about unused
        # imports that are not the first import, we had to flatten first.
        imports, warnings, lines_with_code = _parse_toplevel_imports(
            self.options,
            self.filename,
            on_source_lines,
            type_checking_blocks,
            drill_for_warnings=True,
        )

        if type_check_pass is not RewritePass.PLAIN:
            # now remove unused names from the imports if keep unused was not
            # specified in the arguments
            if self.options.keep_unused_type_checking is False:
                _remove_unused_names(imports, warnings, stats)
        else:
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

            if (
                self.keep_threshhold is None
                or import_proportion < self.keep_threshhold
            ):
                _remove_unused_names(imports, warnings, stats)

        stats["import_line_delta"] = len(imports) - original_imports

        sorted_imports, nosort_imports = sort_imports(
            self.style, imports, self.options
        )

        rewritten = _write_source(
            source_lines,
            sorted_imports,
            nosort_imports,
            import_gap_lines,
            imports_start_on,
            self.style,
        )
        if type_check_pass is not RewritePass.PLAIN:
            TypeCheckingBlocks(rewritten, type_check_pass).remove_empty_blocks(
                rewritten
            )
        return rewritten

    def rewrite(self):
        # pass for each distinct block we want to write
        rewritten = self._do_rewrite(
            self.source_lines,
            type_check_pass=RewritePass.TYPE_CHECK,
        )
        rewritten = self._do_rewrite(
            rewritten,
            type_check_pass=RewritePass.ANTI_TYPE_CHECK,
        )
        rewritten = self._do_rewrite(
            rewritten, type_check_pass=RewritePass.PLAIN
        )

        if self.options.black_line_length:
            rewritten = list(
                _mini_black_format(rewritten, self.options.black_line_length)
            )

        differ = list(difflib.Differ().compare(self.source_lines, rewritten))

        self.stats["added"] = len([l for l in differ if l.startswith("+ ")])
        self.stats["removed"] = len([l for l in differ if l.startswith("- ")])
        self.stats["is_changed"] = bool(
            self.stats["added"] or self.stats["removed"]
        )
        self.stats["totaltime"] = time.time() - self.stats["starttime"]
        return rewritten, self.stats


class TypeCheckingBlocks:
    def __init__(self, source_lines, type_):
        self.type_checking_blocks = []
        self.anti_type_checking_blocks = []
        self.type = type_

        in_type_checking_block = False
        in_anti_type_checking_block = False

        for lineno, line in enumerate(source_lines, 1):
            if re.match(r"^if [\w+\.]*TYPE_CHECKING:", line):
                # we are inside an "if TYPE_CHECKING:" block
                in_type_checking_block = True
                self.type_checking_blocks.append((lineno, set(), -1))
            elif in_type_checking_block:
                if line and re.match(r"^(?:else|elif)", line):
                    # it's an else.  new typing block
                    in_anti_type_checking_block = True
                    self.anti_type_checking_blocks.append(
                        (lineno, set(), self.type_checking_blocks[-1][0])
                    )
                elif line and re.match(r"^[a-zA-Z0-9_]", line):
                    # line is a non-indented, non empty line starting
                    # with a letter, so it's code
                    in_type_checking_block = (
                        in_anti_type_checking_block
                    ) = False
                elif in_anti_type_checking_block:
                    self.anti_type_checking_blocks[-1][1].add(lineno)
                else:
                    self.type_checking_blocks[-1][1].add(lineno)

    def __contains__(self, lineno):
        if self.type is RewritePass.TYPE_CHECK:
            return any(
                lineno in lines for _, lines, _ in self.type_checking_blocks
            )
        elif self.type is RewritePass.ANTI_TYPE_CHECK:
            return any(
                lineno in lines
                for _, lines, _ in self.anti_type_checking_blocks
            )
        else:
            assert False

    def remove_empty_blocks(self, source_lines):
        if self.type is RewritePass.TYPE_CHECK:
            removed_type_check = set()
            for block, lines, _ in self.type_checking_blocks:
                if all(not source_lines[line - 1] for line in lines):
                    removed_type_check.add(block)
                    source_lines[block - 1] = ""

            if self.anti_type_checking_blocks:
                for block, lines, typcheck in self.anti_type_checking_blocks:
                    if typcheck in removed_type_check:
                        source_lines[block - 1 : block - 1] = [
                            "if TYPE_CHECKING:",
                            "    pass",
                        ]

        elif self.type is RewritePass.ANTI_TYPE_CHECK:
            for block, lines, typcheck_line in self.anti_type_checking_blocks:
                if all(not source_lines[line - 1] for line in lines):
                    source_lines[block - 1] = ""
                    if source_lines[typcheck_line - 1 : typcheck_line + 1] == [
                        "if TYPE_CHECKING:",
                        "    pass",
                    ]:
                        source_lines[
                            typcheck_line - 1 : typcheck_line + 1
                        ] = []
        else:
            assert False


def _get_import_discard_lines(
    source_lines: List[str],
    imports: List["ClassifiedImport"],
    lines_with_code: Set[str],
):
    """Get line numbers that are part of imports but not in the AST."""

    import_gap_lines: Set[int] = {node.lineno for node in imports}

    intermediary_whitespace_lines = []

    prev = None
    for lineno in [node.lineno for node in imports] + [len(source_lines) + 1]:
        if prev is not None:
            for gap in range(prev + 1, lineno):
                if gap in lines_with_code:
                    # a codeline is here, so we definitely
                    # are not in an import anymore, go to the next one
                    break
                elif not _is_whitespace_or_comment_or_else(
                    source_lines[gap - 1]
                ):
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


def _is_whitespace_or_comment_or_else(line):
    return bool(
        re.match(r"^\s*$", line)
        or re.match(r"^\s*#", line)
        or re.match(r"^\s*'''", line)
        or re.match(r'^\s*"""', line)
        # the `else:` is not in lines_with_code since it's not present
        # in the ast.
        or re.match(r"^\s*else:", line)
    )


def _write_source(
    source_lines: List[str],
    imports: List["ClassifiedImport"],
    nosort_imports,
    import_gap_lines: Set[int],
    imports_start_on: int,
    style: Any,
):
    buf: List[str] = []
    previous_import = None
    for lineno, line in enumerate(source_lines, 1):
        if lineno == imports_start_on:
            for import_node in imports:
                if previous_import is not None and not style.same_section(
                    previous_import, import_node
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
        return "%simport %s%s" % (
            " " * import_node.col_offset,
            modules,
            import_node.noqa_comment if import_node.noqa else "",
        )
    else:
        return "%sfrom %s%s import %s%s" % (
            " " * import_node.col_offset,
            "." * import_node.level,
            import_node.modules[0] or "",
            modules,
            import_node.noqa_comment if import_node.noqa else "",
        )


class ClassifiedImport(NamedTuple):
    type: f8io.ImportType
    is_from: bool
    modules: list
    names: list
    lineno: int
    col_offset: int
    level: int
    package: str
    ast_names: Optional[str]
    render_ast_names: list
    noqa: bool
    nosort: bool
    noqa_comment: Optional[str]

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
        self,
        source_lines,
        application_import_names,
        application_package_names,
        type_checking_blocks,
    ):
        self.imports: List[ClassifiedImport] = []
        self.source_lines = source_lines
        self.application_import_names = frozenset(application_import_names)
        self.application_package_names = frozenset(application_package_names)
        self.type_checking_blocks = type_checking_blocks
        self.top_level = type_checking_blocks is None

    def _get_flags(self, lineno):
        line = self.source_lines[lineno - 1].rstrip()
        symbols = re.match(
            r".*?( +(?:# type: ignore +)?"
            r"# noqa\:?(?: +(?:[A-Z]\d\d\d,? ?)+)?( *nosort)?.*)",
            line,
        )
        noqa = nosort = False
        noqa_comment = None
        if symbols:
            noqa = True
            noqa_comment = symbols.group(1)
            if symbols.group(2):
                nosort = True
        return noqa, nosort, noqa_comment

    def _check_node(self, node):
        return (self.top_level and node.col_offset == 0) or (
            not self.top_level and node.lineno in self.type_checking_blocks
        )

    def visit_Import(self, node):  # noqa: N802
        if self._check_node(node):
            modules = [alias.name for alias in node.names]
            types_ = {self._classify_type(module) for module in modules}
            if len(types_) == 1:
                type_ = types_.pop()
            else:
                type_ = f8io.ImportType.MIXED
            noqa, nosort, noqa_comment = self._get_flags(node.lineno)
            classified_import = ClassifiedImport(
                type_,
                False,
                modules,
                [],
                node.lineno,
                node.col_offset,
                0,
                f8io.root_package_name(modules[0]),
                node.names,
                list(node.names),
                noqa,
                nosort,
                noqa_comment,
            )
            self.imports.append(classified_import)

    def visit_ImportFrom(self, node):  # noqa: N802
        if self._check_node(node):
            module = node.module or ""
            if node.level > 0:
                type_ = f8io.ImportType.APPLICATION_RELATIVE
            else:
                type_ = self._classify_type(module)
            names = [alias.name for alias in node.names]
            noqa, nosort, noqa_comment = self._get_flags(node.lineno)
            classified_import = ClassifiedImport(
                type_,
                True,
                [module],
                names,
                node.lineno,
                node.col_offset,
                node.level,
                f8io.root_package_name(module),
                node.names,
                list(node.names),
                noqa,
                nosort,
                noqa_comment,
            )
            self.imports.append(classified_import)


def _parse_toplevel_imports(
    options: Any,
    filename: str,
    source_lines: List[str],
    type_checking_blocks: Optional[TypeCheckingBlocks],
    drill_for_warnings: bool = False,
):
    source = "\n".join(source_lines)

    tree = ast.parse(source, filename)

    # NOTE: the line `else:` does not appear in the ast tree, since it's
    # considered inside the `if` block. It's ignored by the function
    # _is_whitespace_or_comment_or_else
    lines_with_code = set(
        node.lineno
        for node in ast.walk(tree)
        if hasattr(node, "lineno") and not isinstance(node, ast.alias)
    )

    warnings = pyflakes.checker.Checker(tree, filename)

    if drill_for_warnings:
        warnings_set = _drill_for_warnings(
            options, filename, source_lines, warnings, type_checking_blocks
        )
    else:
        warnings_set = None

    f8io_visitor = ImportVisitor(
        source_lines,
        options.application_import_names.split(","),
        options.application_package_names.split(","),
        type_checking_blocks,
    )
    f8io_visitor.visit(tree)
    imports = f8io_visitor.imports
    return imports, warnings_set, lines_with_code


def _drill_for_warnings(
    options: Any,
    filename: str,
    source_lines: List[str],
    warnings: pyflakes.checker.Checker,
    type_checking_blocks: Optional[TypeCheckingBlocks],
):
    # pyflakes doesn't warn for all occurrences of an unused import
    # if that same symbol is repeated, so run over and over again
    # until we find every possible warning.  assumes single-line
    # imports

    ignore_errors = set()
    if options.per_file_ignores:
        abs_filename = normalize_path(filename)
        for pattern, codes in options.per_file_ignores:
            if matches_filename(abs_filename, [normalize_path(pattern)]):
                ignore_errors.update(codes)

    source_lines = list(source_lines)
    warnings_set: Set[Tuple[str, int]] = set()
    seen_lineno = set()
    top_level = type_checking_blocks is None
    while True:
        has_warnings = False
        for warning in warnings.messages:
            if (
                not isinstance(warning, pyflakes.messages.UnusedImport)
                or warning.lineno in seen_lineno
            ):
                continue

            if "F401" in ignore_errors:
                continue

            line = source_lines[warning.lineno - 1]
            if top_level:
                # when dealing with "top level" imports, imports
                # inside of conditionals or in defs aren't counted.
                if re.match(r"^\s*", line).group(0):
                    continue
            else:
                if warning.lineno not in type_checking_blocks:
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

        if type_checking_blocks:
            type_checking_blocks.remove_empty_blocks(source_lines)
        source = "\n".join(source_lines)
        tree = ast.parse(source, filename)
        warnings = pyflakes.checker.Checker(tree, filename)

    return warnings_set


def _remove_unused_names(
    imports: List[ClassifiedImport],
    warnings: Set[Tuple[str, int]],
    stats: dict,
):
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


def _dedupe_single_imports(
    import_nodes: Iterable[ClassifiedImport], stats: dict
):

    seen = {}
    orig_order: List[Tuple[ClassifiedImport, Any]] = []

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


def _as_single_imports(
    import_nodes: List[ClassifiedImport],
    stats: dict,
    expand_stars: bool = False,
):

    for import_node in import_nodes:
        if not import_node.is_from:
            for ast_name in import_node.ast_names:
                yield ClassifiedImport(
                    import_node.type,
                    import_node.is_from,
                    [ast_name.name],
                    [],
                    import_node.lineno,
                    import_node.col_offset,
                    import_node.level,
                    import_node.package,
                    [ast_name],
                    [ast_name],
                    import_node.noqa,
                    import_node.nosort,
                    import_node.noqa_comment,
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
                            import_node.col_offset,
                            import_node.level,
                            import_node.package,
                            [ast_cls(star_name, asname=None)],
                            [ast_cls(star_name, asname=None)],
                            import_node.noqa,
                            import_node.nosort,
                            import_node.noqa_comment,
                        )
                else:
                    yield ClassifiedImport(
                        import_node.type,
                        import_node.is_from,
                        import_node.modules,
                        [ast_name.name],
                        import_node.lineno,
                        import_node.col_offset,
                        import_node.level,
                        import_node.package,
                        [ast_name],
                        [ast_name],
                        import_node.noqa,
                        import_node.nosort,
                        import_node.noqa_comment,
                    )


def sort_imports(style: Any, imports: List[ClassifiedImport], options: Any):
    tosort = []
    nosort = []

    for import_node in imports:
        assert options.multi_imports or len(import_node.ast_names) == 1

        if import_node.nosort:
            nosort.append(import_node)
        else:
            tosort.append(import_node)

    sorted_ = sorted(tosort, key=lambda n: style.import_key(n))
    return sorted_, nosort


def _lines_with_newlines(lines) -> Iterator[str]:
    for line in lines[0:-1]:
        yield line + "\n"
    yield lines[-1]


def _mini_black_format(lines: List[str], line_length) -> Iterator[str]:
    for line in lines:
        if len(line) >= line_length:
            from_imp_match = re.match(r"^(\s*)from (.+?) import (.+)", line)
            if not from_imp_match:
                yield line
            else:
                leading_whitespace = from_imp_match.group(1)
                module = from_imp_match.group(2)
                names = re.split(r", ", from_imp_match.group(3))
                yield f"{leading_whitespace}from {module} import ("
                for name in names:
                    yield f"{leading_whitespace}    {name},"
                yield ")"
        else:
            yield line


def _read_python_source(filename):
    if filename == "-":
        file_content = sys.stdin.buffer.read()
    else:
        with open(filename, "rb") as file_:
            file_content = file_.read()

    # ensure the filehandle is seekable, which is not the
    # case if a stdin stream was sent, see #17
    with io.BytesIO(file_content) as file_:
        encoding_comment = _parse_magic_encoding_comment(file_)
        text = importlib.util.decode_source(file_.read())
        return text.split("\n"), encoding_comment


# Regexp to match python magic encoding line
_PYTHON_MAGIC_COMMENT_re = re.compile(
    r"[ \t\f]* \# .* coding[=:][ \t]*([-\w.]+)", re.VERBOSE
)


def _parse_magic_encoding_comment(fp):
    """Deduce the encoding of a Python source file (binary mode) from magic
    comment.

    It does this in the same way as the `Python interpreter`__

    .. __: http://docs.python.org/ref/encodings.html

    The ``fp`` argument should be a seekable file object in binary mode.

    """
    pos = fp.tell()
    fp.seek(0)
    try:
        line1 = fp.readline()
        has_bom = line1.startswith(codecs.BOM_UTF8)
        if has_bom:
            line1 = line1[len(codecs.BOM_UTF8) :]

        m = _PYTHON_MAGIC_COMMENT_re.match(line1.decode("ascii", "ignore"))
        if not m:
            try:
                parse(line1.decode("ascii", "ignore"))
            except (ImportError, SyntaxError):
                # Either it's a real syntax error, in which case the source
                # is not valid python source, or line2 is a continuation of
                # line1, in which case we don't want to scan line2 for a magic
                # comment.
                pass
            else:
                line2 = fp.readline()
                m = _PYTHON_MAGIC_COMMENT_re.match(
                    line2.decode("ascii", "ignore")
                )

        if has_bom:
            if m:
                raise SyntaxError(
                    "python refuses to compile code with both a UTF8"
                    " byte-order-mark and a magic encoding comment"
                )
            return "utf_8"
        elif m:
            return m.group(1)
        else:
            return None
    finally:
        fp.seek(pos)


def _run_file(options, filename):

    lines, encoding_comment = _read_python_source(filename)
    source_lines = [line.rstrip() for line in lines]

    if options.keep_unused:
        if options.heuristic_unused:
            raise Exception(
                "keep-unused and heuristic-unused are mutually exclusive"
            )
        options.heuristic_unused = 0
        options.keep_unused_type_checking = True
    result, stats = Rewriter(options, filename, source_lines).rewrite()
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

        if options.diff:
            sys.stdout.writelines(
                difflib.unified_diff(
                    list(_lines_with_newlines(source_lines)),
                    list(_lines_with_newlines(result)),
                    fromfile=filename,
                    tofile=filename,
                )
            )
        elif options.stdout or filename == "-":
            sys.stdout.writelines(_lines_with_newlines(result))
        else:
            if stats["is_changed"]:
                with open(
                    filename,
                    "w",
                    encoding=encoding_comment if encoding_comment else "utf-8",
                ) as file_:
                    file_.writelines(_lines_with_newlines(result))


def run_with_options(options):
    for filename in options.filename:
        if os.path.isdir(filename):

            def iter_files():
                for root, dirs, files in os.walk(filename):
                    for file in files:
                        if file.endswith(".py") or file.endswith(".pyi"):
                            yield os.path.join(root, file)

            if options.workers is None or options.workers <= 1:
                for file in iter_files():
                    _run_file(options, file)
            else:
                func = partial(_run_file, options)
                with Pool(options.workers) as pool:
                    pool.map(func, iter_files())
        else:
            _run_file(options, filename)
