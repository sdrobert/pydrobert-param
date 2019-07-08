# Copyright 2019 Sean Robertson
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

'''Command line utilities'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import argparse
import json
import warnings

from collections import OrderedDict
from itertools import chain

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2019 Sean Robertson"
__all__ = [
    'combine_ini_files',
    'combine_json_files',
]


def _combine_ini_files_parse_args(args):
    parser = argparse.ArgumentParser(
        description=combine_ini_files.__doc__
    )
    parser.add_argument(
        'sources', nargs='+', type=argparse.FileType('r'),
        help='Paths to read from'
    )
    parser.add_argument(
        'dest', type=argparse.FileType('w'),
        help='Path to write to'
    )
    return parser.parse_args(args)


def combine_ini_files(args=None):
    '''Combine INI files

    This command provides a content-agnostic way of combining
    `INI files <https://en.wikipedia.org/wiki/INI_file>`__.

    All but the last positional argument consist of input files. Earlier values
    are clobbered by later values.

    Comments (anything after a '#' or ';') are ignored
    '''
    try:
        options = _combine_ini_files_parse_args(args)
    except SystemExit as ex:
        return ex.code
    try:
        from ConfigParser import SafeConfigParser
        parser = SafeConfigParser()
    except ImportError:
        from configparser import ConfigParser
        parser = ConfigParser(
            comment_prefixes=('#', ';'),
            inline_comment_prefixes=('#', ';'),
        )
    for fp in options.sources:
        try:
            parser.read_file(fp)
        except AttributeError:
            parser.readfp(fp)
    parser.write(options.dest)
    return 0


def _combine_json_files_parse_args(args):
    parser = argparse.ArgumentParser(
        description=combine_json_files.__doc__
    )
    parser.add_argument(
        'sources', nargs='+', type=argparse.FileType('r'),
        help='Paths to read from'
    )
    parser.add_argument(
        'dest', type=argparse.FileType('w'),
        help='Path to write to'
    )
    parser.add_argument(
        '--quiet', action='store_true', default=False,
        help='If set, will not warn when ``sources`` are all lists'
    )
    parser.add_argument(
        '--compact', action='store_true', default=False,
        help='By default, JSON dicts will have newlines and tab indentation. '
        'If set, will encode structures in the most compact way possible'
    )
    return parser.parse_args(args)


def combine_json_files(args=None):
    '''Combine JSON files

    This command provides a content-agnostic way of combining
    `JSON files <https://en.wikipedia.org/wiki/JSON>`__.

    This command is intended to be used with JSON files whose root data type is
    a dictionary, at which point the combination is ambiguous: later source
    files clobber the values of earlier ones. If all source files are lists,
    we merely append the lists together. Mixing root data types of sources or
    specifying more than one source for a root type that is not a dict or list
    will result in an error
    '''
    try:
        options = _combine_json_files_parse_args(args)
    except SystemExit as ex:
        return ex.code
    vals = []
    names = []
    for fp in options.sources:
        names.append(fp.name)
        vals.append(json.load(fp, object_pairs_hook=OrderedDict))
    if len(vals) == 1:
        v = vals[0]
    elif all(isinstance(x, list) for x in vals):
        if not options.quiet:
            warnings.warn(
                'Source files are all JSON lists. Source files will merely '
                'be appended together')
        v = list(chain(*vals))
    elif all(isinstance(x, OrderedDict) for x in vals):
        v = OrderedDict()
        for x in vals:
            v.update(x)
    else:
        print(
            'More than one source and either JSON files encode neither a '
            'dict or list, or some encode dicts and some encode lists. Unable '
            'to merge', file=sys.stderr)
        return 1
    if options.compact:
        json.dump(v, options.dest)
    else:
        json.dump(v, options.dest, indent="\t")
    return 0