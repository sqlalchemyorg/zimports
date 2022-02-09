import argparse
import configparser

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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zimports")

    config = _load_config()

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
        help="Format long imports past given line length using Black-style "
        "formatting"
    )
    parser.add_argument(
        "--multi-imports",
        action="store_true",
        help="If set, multiple imports can exist on one line",
    )
    parser.add_argument(
        "-k",
        "--keep-unused",
        action="store_true",
        help="keep unused imports even though detected as unused. "
        "Implies keep-unused-type-checking",
    )
    parser.add_argument(
        "-kt",
        "--keep-unused-type-checking",
        action="store_true",
        help="keep unused imports even though detected as unused "
        "in type checking blocks. zimports does not detect type usage "
        "in comments or when used as string",
    )
    parser.add_argument(
        "--heuristic-unused",
        type=int,
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

    options = parser.parse_args(argv)

    if "per-file-ignores" in config["flake8"]:
        options.per_file_ignores = parse_files_to_codes_mapping(
            config["flake8"]["per-file-ignores"]
        )
    else:
        options.per_file_ignores = []

    run_with_options(options)
