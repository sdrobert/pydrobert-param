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

import argparse

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2019 Sean Robertson"
__all__ = [
    'combine_ini_files',
]


def _combine_ini_parse_args(args):
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
        options = _combine_ini_parse_args(args)
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
