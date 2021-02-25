"""Vendored code from other packages"""
import collections
import fnmatch as _fnmatch
import os
import re

# ## flake8 code ##


class ExecutionError(Exception):
    """Exception raised during execution of Flake8."""


string_types = (str, type(u""))
_Token = collections.namedtuple("Token", ("tp", "src"))
_CODE, _FILE, _COLON, _COMMA, _WS = "code", "file", "colon", "comma", "ws"
_EOF = "eof"
_FILE_LIST_TOKEN_TYPES = [
    (re.compile(r"[A-Z]+[0-9]*(?=$|\s|,)"), _CODE),
    (re.compile(r"[^\s:,]+"), _FILE),
    (re.compile(r"\s*:\s*"), _COLON),
    (re.compile(r"\s*,\s*"), _COMMA),
    (re.compile(r"\s+"), _WS),
]


def _tokenize_files_to_codes_mapping(value):
    tokens = []
    i = 0
    while i < len(value):
        for token_re, token_name in _FILE_LIST_TOKEN_TYPES:
            match = token_re.match(value, i)
            if match:
                tokens.append(_Token(token_name, match.group().strip()))
                i = match.end()
                break
        else:
            raise AssertionError("unreachable", value, i)
    tokens.append(_Token(_EOF, ""))

    return tokens


def parse_files_to_codes_mapping(value_):
    """Parse a files-to-codes maping.

    A files-to-codes mapping a sequence of values specified as
    `filenames list:codes list ...`.  Each of the lists may be separated by
    either comma or whitespace tokens.

    :param value: String to be parsed and normalized.
    :type value: str
    """
    if not isinstance(value_, string_types):
        value = "\n".join(value_)
    else:
        value = value_

    ret = []
    if not value.strip():
        return ret

    class State:
        seen_sep = True
        seen_colon = False
        filenames = []
        codes = []

    def _reset():
        if State.codes:
            for filename in State.filenames:
                ret.append((filename, State.codes))
        State.seen_sep = True
        State.seen_colon = False
        State.filenames = []
        State.codes = []

    def _unexpected_token():
        def _indent(s):
            return "    " + s.strip().replace("\n", "\n    ")

        return ExecutionError(
            "Expected `per-file-ignores` to be a mapping from file exclude "
            "patterns to ignore codes.\n\n"
            "Configured `per-file-ignores` setting:\n\n{}".format(
                _indent(value)
            )
        )

    for token in _tokenize_files_to_codes_mapping(value):
        # legal in any state: separator sets the sep bit
        if token.tp in {_COMMA, _WS}:
            State.seen_sep = True
        # looking for filenames
        elif not State.seen_colon:
            if token.tp == _COLON:
                State.seen_colon = True
                State.seen_sep = True
            elif State.seen_sep and token.tp == _FILE:
                State.filenames.append(token.src)
                State.seen_sep = False
            else:
                raise _unexpected_token()
        # looking for codes
        else:
            if token.tp == _EOF:
                _reset()
            elif State.seen_sep and token.tp == _CODE:
                State.codes.append(token.src)
                State.seen_sep = False
            elif State.seen_sep and token.tp == _FILE:
                _reset()
                State.filenames.append(token.src)
                State.seen_sep = False
            else:
                raise _unexpected_token()

    return ret


def fnmatch(filename, patterns):
    """Wrap :func:`fnmatch.fnmatch` to add some functionality.

    :param str filename:
        Name of the file we're trying to match.
    :param list patterns:
        Patterns we're using to try to match the filename.
    :param bool default:
        The default value if patterns is empty
    :returns:
        True if a pattern matches the filename, False if it doesn't.
        ``default`` if patterns is empty.
    """
    if not patterns:
        return True
    return any(_fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def matches_filename(path, patterns):
    """Use fnmatch to discern if a path exists in patterns.

    :param str path:
        The path to the file under question
    :param patterns:
        The patterns to match the path against.
    :type patterns:
        list[str]
    :returns:
        True if path matches patterns, False otherwise
    :rtype:
        bool
    """
    # NOTE: log_message and logger was removed
    if not patterns:
        return False
    basename = os.path.basename(path)
    if basename not in {".", ".."} and fnmatch(basename, patterns):
        return True

    absolute_path = os.path.abspath(path)
    match = fnmatch(absolute_path, patterns)
    return match


def normalize_path(path, parent=os.curdir):
    """Normalize a single-path.

    :returns:
        The normalized path.
    :rtype:
        str
    """
    # NOTE(sigmavirus24): Using os.path.sep and os.path.altsep allow for
    # Windows compatibility with both Windows-style paths (c:\\foo\bar) and
    # Unix style paths (/foo/bar).
    separator = os.path.sep
    # NOTE(sigmavirus24): os.path.altsep may be None
    alternate_separator = os.path.altsep or ""
    if separator in path or (
        alternate_separator and alternate_separator in path
    ):
        path = os.path.abspath(os.path.join(parent, path))
    return path.rstrip(separator + alternate_separator)
