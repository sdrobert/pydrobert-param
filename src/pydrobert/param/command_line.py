# Copyright 2021 Sean Robertson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Command line utilities"""


import argparse
import json
import warnings

from collections import OrderedDict
from itertools import chain
from configparser import ConfigParser

from pydrobert.param.serialization import _serialize_to_yaml
from pydrobert.param.serialization import _deserialize_from_yaml

__all__ = [
    "combine_ini_files",
    "combine_json_files",
    "combine_yaml_files",
]


def _combine_ini_files_parse_args(args):
    parser = argparse.ArgumentParser(
        description=combine_ini_files.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "sources", nargs="+", type=argparse.FileType("r"), help="Paths to read from"
    )
    parser.add_argument("dest", type=argparse.FileType("w"), help="Path to write to")
    return parser.parse_args(args)


def combine_ini_files(args=None):
    """Combine INI files

    This command provides a content-agnostic way of combining INI files
    (https://en.wikipedia.org/wiki/INI_file).

    All but the last positional argument consist of input files. Earlier values are
    clobbered by later values.

    Comments (anything after a '#' or ';') are ignored
    """
    try:
        options = _combine_ini_files_parse_args(args)
    except SystemExit as ex:
        return ex.code
    parser = ConfigParser(
        comment_prefixes=("#", ";"),
        inline_comment_prefixes=("#", ";"),
        allow_no_value=True,
    )
    for fp in options.sources:
        try:
            parser.read_file(fp)
        except AttributeError:
            parser.readfp(fp)
    parser.write(options.dest)
    return 0


def _combine_clobber_dict(dicts, warn):
    dict_ = OrderedDict()
    for dict_2 in dicts:
        if warn:
            for key, value in list(dict_2.items()):
                if (
                    key in dict_
                    and not isinstance(value, type(dict_[key]))
                    and not isinstance(dict_[key], type(value))
                ):
                    warnings.warn(
                        "clobbered value at key={} not the same type" "".format(key)
                    )
                dict_[key] = value
        else:
            dict_.update(dict_2)
    return dict_


def _combine_nested_dicts(dicts, warn, multiindex=tuple()):
    dict_ = type(dicts[0])()
    for dict_2 in dicts:
        for key, value in list(dict_2.items()):
            if key in dict_:
                orig = dict_[key]
                if isinstance(value, dict) and isinstance(orig, dict):
                    value = _combine_nested_dicts(
                        [orig, value], warn, multiindex + (key,)
                    )
                elif warn and (
                    not isinstance(value, type(orig))
                    or not isinstance(orig, type(value))
                ):
                    warnings.warn(
                        "clobbered value at multiindex={} not the same type"
                        "".format(multiindex)
                    )
            dict_[key] = value
    return dict_


def _combine_container_vals(vals, warn, nested):
    if len(vals) == 1:
        ret = vals[0]
    elif all(isinstance(x, list) for x in vals):
        if warn:
            warnings.warn(
                "Source files are all lists. Source files will merely "
                "be appended together"
            )
        ret = list(chain(*vals))
    elif all(isinstance(x, dict) for x in vals):
        if nested:
            ret = _combine_nested_dicts(vals, warn)
        else:
            ret = _combine_clobber_dict(vals, warn)
    else:
        raise ValueError(
            "More than one source and sources encode neither a "
            "dict or list, or some encode dicts and some encode lists. Unable "
            "to merge"
        )
    return ret


def _combine_json_files_parse_args(args):
    parser = argparse.ArgumentParser(description=combine_json_files.__doc__)
    parser.add_argument(
        "sources", nargs="+", type=argparse.FileType("r"), help="Paths to read from"
    )
    parser.add_argument("dest", type=argparse.FileType("w"), help="Path to write to")
    parser.add_argument("--quiet", action="store_true", default=False)
    parser.add_argument(
        "--compact",
        action="store_true",
        default=False,
        help="By default, JSON dicts will have newlines and 2-space indentation. If "
        "set, will encode structures in the most compact way possible",
    )
    parser.add_argument(
        "--nested",
        action="store_true",
        default=False,
        help="Resolve dict collisions by descending into children. See command "
        "documentation for more info",
    )
    return parser.parse_args(args)


def combine_json_files(args=None):
    """Combine JSON files

    This command provides a content-agnostic way of combining JSON files
    (https://en.wikipedia.org/wiki/JSON).

    If all source files are lists, we merely append the lists together.

    If all documents' root data types are dictionaries, the default behaviour, given a
    collision of keys, is to clobber the old value with the new one. If the "--nested"
    flag is set, and both values are dictionaries, the values of the old dictionary will
    be updated with the values of the new one, but old keys not present in the new
    dictionary will persist. For example, without the "--nested" flag

        {"a": {"b": {"c": null}, "d": true}} +
        {"a": {"b": {"e": 1}}, "f": "g"} =
        {"a": {"b": {"e": 1}}, "f": "g"}

    but with the nested flag

        {"a": {"b": {"c": null}, "d": true}} +
        {"a": {"b": {"e": 1}}, "f": "g"} =
        {"a": {"b": {"c": null, "e": 1}, "d": true}, "f": "g"}

    Mixing root data types of sources or specifying more than one source for a root type
    that is not a dict or list will result in an error.
    """
    try:
        options = _combine_json_files_parse_args(args)
    except SystemExit as ex:
        return ex.code
    vals = []
    for fp in options.sources:
        vals.append(json.load(fp, object_pairs_hook=OrderedDict))
    v = _combine_container_vals(vals, not options.quiet, options.nested)
    if options.compact:
        json.dump(v, options.dest)
    else:
        json.dump(v, options.dest, indent=2, separators=(",", ": "))
    return 0


def _combine_yaml_files_parse_args(args):
    parser = argparse.ArgumentParser(description=combine_yaml_files.__doc__,)
    parser.add_argument(
        "sources", nargs="+", type=argparse.FileType("r"), help="Paths to read from"
    )
    parser.add_argument("dest", type=argparse.FileType("w"), help="Path to write to")
    parser.add_argument("--quiet", action="store_true", default=False)
    parser.add_argument(
        "--nested",
        action="store_true",
        default=False,
        help="Resolve dict collisions by descending into children. See command "
        "documentation for more info",
    )
    return parser.parse_args(args)


def combine_yaml_files(args=None):
    """Combine YAML files

    This command provides a content-agnostic way of combining YAML files
    (https://en.wikipedia.org/wiki/YAML).

    All but the last positional argument consist of input files. Earlier values are
    clobbered by later values.

    If all source files are lists, we merely append the lists together.

    If all documents' root data types are dictionaries, the default behaviour, given a
    collision of keys, is to clobber the old value with the new one. If the "--nested"
    flag is set, and both values are dictionaries, the values of the old dictionary will
    be updated with the values of the new one, but old keys not present in the new
    dictionary will persist. See the "combine-json-files" command for an example

    Whether comments are ignored depends on the parsing backend.
    """
    try:
        options = _combine_yaml_files_parse_args(args)
    except SystemExit as ex:
        return ex.code
    vals = []
    for fp in options.sources:
        vals.append(_deserialize_from_yaml(fp))
    v = _combine_container_vals(vals, not options.quiet, options.nested)
    _serialize_to_yaml(options.dest, v)
    return 0
