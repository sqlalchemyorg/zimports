import argparse
import configparser
import os

import tomli

from .vendored.flake8 import parse_files_to_codes_mapping
from .zimports import run_with_options


def _load_config(config_file="setup.cfg"):
    config = configparser.ConfigParser()
    config["flake8"] = {
        "application-import-names": "",
        "application-package-names": "",
        "import-order-style": "google",
    }
    config.read(config_file)
    return config


def _load_toml(config_file="pyproject.toml"):

    if os.path.exists(config_file):
        with open(config_file, "rb") as f:
            toml_dict = tomli.load(f)  # type: ignore
    else:
        toml_dict = {}

    return toml_dict.get("tool", {}).get("zimports", {})


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zimports")

    config = _load_config()

    NOT_SET = object()

    parser.add_argument(
        "--toml-config",
        type=str,
        default="pyproject.toml",
        help="name / path of pyproject.toml file",
    )
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
        "--black-line-length",
        type=int,
        default=NOT_SET,
        help="Format long imports past given line length using Black-style "
        "formatting",
    )
    parser.add_argument(
        "--multi-imports",
        action="store_true",
        default=NOT_SET,
        help="If set, multiple imports can exist on one line",
    )
    parser.add_argument(
        "-k",
        "--keep-unused",
        action="store_true",
        default=NOT_SET,
        help="keep unused imports even though detected as unused. "
        "Implies keep-unused-type-checking",
    )
    parser.add_argument(
        "-kt",
        "--keep-unused-type-checking",
        action="store_true",
        default=NOT_SET,
        help="keep unused imports even though detected as unused "
        "in type checking blocks. zimports does not detect type usage "
        "in comments or when used as string",
    )
    parser.add_argument(
        "--heuristic-unused",
        type=int,
        default=NOT_SET,
        help="Remove unused imports only if number of imports is "
        "less than <HEURISTIC_UNUSED> percent of the total lines of code. "
        "Ignored in type checking blocks",
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
        "filename", nargs="+", help="Python filename(s) or directories"
    )
    cpu = os.cpu_count()
    parser.add_argument(
        "-W",
        "--workers",
        type=int,
        default=cpu,
        help=f"Number of parallel workers  [default: {cpu};x>=1]",
    )

    options = parser.parse_args(argv)

    toml = _load_toml(options.toml_config)
    if options.black_line_length is NOT_SET:
        options.black_line_length = toml.get("black-line-length", None)
    if options.multi_imports is NOT_SET:
        options.multi_imports = toml.get("multi-imports", False)
    if options.keep_unused is NOT_SET:
        options.keep_unused = toml.get("keep-unused", False)
    if options.keep_unused_type_checking is NOT_SET:
        options.keep_unused_type_checking = toml.get(
            "keep-unused-type-checking", False
        )
    if options.heuristic_unused is NOT_SET:
        options.heuristic_unused = toml.get("heuristic-unused", None)

    if "per-file-ignores" in config["flake8"]:
        options.per_file_ignores = parse_files_to_codes_mapping(
            config["flake8"]["per-file-ignores"]
        )
    else:
        options.per_file_ignores = []

    run_with_options(options)
