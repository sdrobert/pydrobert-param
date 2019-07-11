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

"""Hooks for command-line interface with params"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import abc
import sys

import param
import pydrobert.param.serialization as serialization

from future.utils import with_metaclass

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2019 Sean Robertson"
__all__ = [
    'ParameterizedFileReadAction',
    'ParameterizedIniReadAction',
    'ParameterizedJsonReadAction',
    'ParameterizedYamlReadAction',
    'ParameterizedPrintAction',
]


class ParameterizedFileReadAction(
        with_metaclass(abc.ABCMeta, argparse.Action)):
    '''Base class for deserializing files into a param.Parameterized object

    Subclasses of this class can be added as the 'action' keyword to an
    ``argparse.ArgumentParser.add_argument()`` call. The action will read the
    file path passed as an argument via command line and use the contents
    of the file to populate ``param.Parameterized`` instances. The subclass
    deserializes the contents of the file according to the
    ``pydrobert.param.serialization.deserialize_from_filetype`` function,
    where ``filetype`` is replaced with the subclass' file type.

    There are three ways to specify parameterized objects to populate. They
    are mutually exclusive:

    1. Set the keyword `type` with the subclass of ``param.Parameterized`` you
       want to deserialize into. A new instance of that subclass will be
       created with a name matching `dest`. The instance will be returned in
       the parsed namespace's attribute whose name matches `dest` as well.

    2. Set the keyword `parameterized` with an instance of
       ``param.Parameterized``. That instance will be populated and also
       returned in the parsed namespace's attribute whose name matches `dest`.

    3. Set the keyword `parameterized` as a hierarchical dictionary of
       ``param.Parameterized`` instances. The leaves of the dictionary will
       be populated according to the "hierarchical mode" specified in the
       documentation of
       ``pydrobert.param.serialization.deserialize_from_dict``. The same
       dictionary will be returned in the parsed namespace's attribute whose
       name matches `dest`.

    Parameters
    ----------
    option_strings : list
        A list of command-line option strings which should be associated with
        this action.
    dest : str
        The name of the attribute to hold the created object.
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    deserializer_name_dict : dict, optional
        Use specific deserializers for parameters with specific names.
    deserializer_type_dict : dict, optional
        Use specific deserializers for parameters with exactly matching types.
    on_missing: {'ignore', 'warn', 'raise'}, optional
        What to do if the parameterized instance does not have a parameter
        listed in the config file.
    required : bool, optional
        ``True`` if the action must always be specified at the command line.
        This is only meaningful for optional command-line arguments.
    help : str, optional
        The help string describing the argument.
    metavar : str, optional
        The name to be used for the option's argument with the help string.
        If ``None``, the `dest` value will be used as the name.
    nargs : str or int, optional
        The number of command line arguments to be consumed. When more than
        one argument is specified, each will be deserialized in the order that
        they were presented on the command line. Thus, later config values
        will clobber earlier ones
    const : str, optional
        If `nargs` is ``'?'`` but the flag is present on the command line,
        this value will be supplied as the missing argument

    Attributes
    ----------
    parameterized : param.Parameterized or dict
        The object that populates the `dest` attribute of the parsed namespace
    deserializer_name_dict : dict or None
    deserializer_type_dict : dict or None
    on_missing : {'ignore', 'warn', 'raise'}

    See Also
    --------
    pydrobert.param.serialization.deserialize_from_dict
        For more information on how values are deserialized from the config
    '''

    def __init__(
            self, option_strings, dest,
            parameterized=None, type=None, deserializer_name_dict=None,
            deserializer_type_dict=None, on_missing='warn',
            required=False, help=None, metavar=None, nargs=None,
            const=None):
        if parameterized is None and type is None:
            raise TypeError('one of parameterized or type must be set')
        if parameterized is not None and type is not None:
            raise TypeError('only one of parameterized or type can be set')
        if parameterized is None:
            self.parameterized = type(name=dest)
        else:
            self.parameterized = parameterized
        self.deserializer_name_dict = deserializer_name_dict
        self.deserializer_type_dict = deserializer_type_dict
        self.on_missing = on_missing
        super(ParameterizedFileReadAction, self).__init__(
            option_strings, dest,
            type=argparse.FileType('r'), default=self.parameterized,
            required=required, help=help, metavar=metavar,
            nargs=nargs, const=const,
        )

    @abc.abstractmethod
    def deserialize(self, fp):
        '''Read the file pointer into parameterized objects

        Called during the callable section of this class. Implemented by
        subclasses.
        '''
        raise NotImplementedError()

    def __call__(self, parser, namespace, values, option_string=None):
        # the latter occurs with, for example, nargs='*' and empty args
        if values is None or values == self.parameterized:
            return
        if not isinstance(values, list):
            values = [values]
        for fp in values:
            self.deserialize(fp)


class ParameterizedIniReadAction(ParameterizedFileReadAction):
    '''Deserialize an INI file into a parameterized object

    Parameters
    ----------
    option_strings : list
    dest : str
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing: {'ignore', 'warn', 'raise'}, optional
    required : bool, optional
    help : str, optional
    metavar : str, optional
    nargs : str or int, optional
    const : str, optional
    defaults : dict, optional
    comment_prefixes : tuple, optional
    inline_comment_prefixes : sequence, optional
    one_param_section : str or None, optional

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    pydrobert.param.serialization.deserialize_from_ini
        A description of the deserialization process and of the additional
        parameters.
    '''

    def __init__(
            self, option_strings, dest,
            parameterized=None, type=None, deserializer_name_dict=None,
            deserializer_type_dict=None, on_missing='warn',
            required=False, help=None, metavar=None, nargs=None, const=None,
            defaults=None, comment_prefixes=('#', ';'),
            inline_comment_prefixes=(';',), one_param_section=None):
        self.defaults = defaults
        self.comment_prefixes = comment_prefixes
        self.inline_comment_prefixes = inline_comment_prefixes
        self.one_param_section = one_param_section
        super(ParameterizedIniReadAction, self).__init__(
            option_strings, dest,
            parameterized=parameterized, type=type,
            deserializer_name_dict=deserializer_name_dict,
            deserializer_type_dict=deserializer_type_dict,
            on_missing=on_missing, required=required, help=help,
            metavar=metavar, nargs=nargs, const=const,
        )

    def deserialize(self, fp):
        serialization.deserialize_from_ini(
            fp, self.parameterized,
            deserializer_name_dict=self.deserializer_name_dict,
            deserializer_type_dict=self.deserializer_type_dict,
            on_missing=self.on_missing,
            comment_prefixes=self.comment_prefixes,
            inline_comment_prefixes=self.inline_comment_prefixes,
            one_param_section=self.one_param_section,
        )


class ParameterizedYamlReadAction(ParameterizedFileReadAction):
    '''Deserialize a YAML file into a parameterized object

    Parameters
    ----------
    option_strings : list
    dest : str
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing: {'ignore', 'warn', 'raise'}, optional
    required : bool, optional
    help : str, optional
    metavar : str, optional
    nargs : int or str, optional
    const : str, optional


    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    pydrobert.param.serialization.deserialize_from_yaml
        A description of the deserialization process.
    '''

    def deserialize(self, fp):
        serialization.deserialize_from_yaml(
            fp, self.parameterized,
            deserializer_name_dict=self.deserializer_name_dict,
            deserializer_type_dict=self.deserializer_type_dict,
            on_missing=self.on_missing,
        )


class ParameterizedJsonReadAction(ParameterizedFileReadAction):
    '''Deserialize a JSON file into a parameterized object

    Parameters
    ----------
    option_strings : list
    dest : str
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing: {'ignore', 'warn', 'raise'}, optional
    required : bool, optional
    help : str, optional
    metavar : str, optional
    nargs : str, optional
    const : str, optional

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    pydrobert.param.serialization.deserialize_from_json
        A description of the deserialization process.
    '''

    def deserialize(self, fp):
        serialization.deserialize_from_json(
            fp, self.parameterized,
            deserializer_name_dict=self.deserializer_name_dict,
            deserializer_type_dict=self.deserializer_type_dict,
            on_missing=self.on_missing,
        )


class ParameterizedPrintAction(with_metaclass(abc.ABCMeta, argparse.Action)):
    '''Base class for printing parameters to stdout and exiting

    Subclasses of this class can be added as the 'action' keyword to an
    ``argparse.ArgumentParser.add_argument()`` call. Like the ``--help`` flag,
    after this action is called, the program will try to exit, but not before
    printing out parameters.

    There are three ways to specify what parameters to print, analogous to how
    they are specified in ``ParameterizedFileReadAction``:

    1. Set the keyword `type` with a subclass of ``param.Parameterized``. A
       new instance of that type will be created to be printed

    2. Set the keyword `parameterized` with an instance of
       ``param.Parameterized``. That instance will be printed.

    3.  Set the keyword `parameterized` as a hierarchical dictionary of
       ``param.Parameterized`` instances. The leaves of the dictionary will
       be populated according to the "hierarchical mode" specified in the
       documentation of ``pydrobert.param.serialization.serialize_to_dict``.

    Note that if a ``ParameterizedFileReadAction`` has been called on the
    command line prior to the print that shares the same `parameterized` value
    as in 2. or 3., `parameterized` will be populated by that file's contents.

    Parameters
    ----------
    option_strings : list
        A list of command-line option strings which should be associated with
        this action.
    dest : str
        Will specify the 'name' attribute when `type` is specified. Otherwise
        ignored
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    serializer_name_dict : dict, optional
        Use specific serializers for parameters with specific names
    serializer_type_dict : dict, optional
        Use specific serializers for parameters with exactly matching types
    only : set or dict, optional
        If specified, only the parameters with their names in this set will
        be printed
    on_missing : {'ignore', 'warn', 'raise'}, optional
        What to do if the parameterized instance does not have a parameter
        listed in `only`
    include_help : bool, optional
        Whether to print parameter help when printing parameters
    help : str, optional
        The help string describing the argument
    out_stream : file_ptr, optional
        Where to print the parameters to

    Attributes
    ----------
    parameterized : param.Parameterized or dict
        The parameters to be printed
    serializer_name_dict : dict
    serializer_type_dict : dict
    only : set or dict
    on_missing : {'ignore', 'warn', 'raise'}
    include_help : boolean
    out_stream : file_ptr
    '''

    def __init__(
            self, option_strings, dest,
            parameterized=None, type=None, serializer_name_dict=None,
            serializer_type_dict=None, only=None, on_missing='raise',
            include_help=True, help=None, out_stream=sys.stdout):
        if parameterized is None and type is None:
            raise TypeError('one of parameterized or type must be set')
        if parameterized is not None and type is not None:
            raise TypeError('only one of parameterized or type can be set')
        if parameterized is None:
            self.parameterized = type(name=dest)
        else:
            self.parameterized = parameterized
        self.serializer_name_dict = serializer_name_dict
        self.serializer_type_dict = serializer_type_dict
        self.only = only
        self.on_missing = on_missing
        self.include_help = include_help
        self.out_stream = out_stream
        super(ParameterizedPrintAction, self).__init__(
            option_strings, dest, help=help, nargs=0)

    @abc.abstractmethod
    def print_parameters(self):
        '''Print the parameters

        Called during the callable section of this class. Should print to the
        attribute `out_stream`
        '''
        raise NotImplementedError()

    def __call__(self, parser, namespace, values, option_string=None):
        self.print_parameters()
        parser.exit()


class ParameterizedIniPrintAction(ParameterizedPrintAction):
    '''Print parameters as INI and exit

    Parameters
    ----------
    option_strings : list
    dest : str
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    serializer_name_dict : dict, optional
    serializer_type_dict : dict, optional
    only : set or dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
    include_help : bool, optional
    help : str, optional
    out_stream : file_ptr, optional
    help_prefix : str, optional
    one_param_section : str, optional

    Attributes
    ----------
    parameterized : param.Parameterized or dict
    serializer_name_dict : dict
    serializer_type_dict : dict
    only : set or dict
    on_missing : {'ignore', 'warn', 'raise'}
    include_help : boolean
    out_stream : file_ptr
    help_prefix : str
    one_param_section : str

    See Also
    --------
    ParameterizedPrintAction
        A full description of the parameters and behaviour of like actions
    pydrobert.param.serialization.serialize_to_ini
        A description of the serialization process and of the additional
        parameters
    '''

    def __init__(
            self, option_strings, dest,
            parameterized=None, type=None, serializer_name_dict=None,
            serializer_type_dict=None, only=None, on_missing='raise',
            include_help=True, help=None, out_stream=sys.stdout,
            help_prefix='#', one_param_section=None):
        self.help_prefix = help_prefix
        self.one_param_section = one_param_section
        super(ParameterizedIniPrintAction, self).__init__(
            option_strings, dest,
            parameterized=parameterized, type=type,
            serializer_name_dict=serializer_name_dict,
            serializer_type_dict=serializer_type_dict, only=only,
            on_missing=on_missing, include_help=include_help, help=help,
            out_stream=out_stream,
        )

    def print_parameters(self):
        serialization.serialize_to_ini(
            self.out_stream, self.parameterized, only=self.only,
            serializer_name_dict=self.serializer_name_dict,
            serializer_type_dict=self.serializer_type_dict,
            on_missing=self.on_missing, include_help=self.include_help,
            help_prefix=self.help_prefix,
            one_param_section=self.one_param_section,
        )


class ParameterizedJsonPrintAction(ParameterizedPrintAction):
    '''Print parameters as JSON and exit

    Parameters
    ----------
    option_strings : list
    dest : str
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    serializer_name_dict : dict, optional
    serializer_type_dict : dict, optional
    only : set or dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
    out_stream : file_ptr, optional
    indent : int, optional

    Attributes
    ----------
    parameterized : param.Parameterized or dict
    serializer_name_dict : dict
    serializer_type_dict : dict
    only : set or dict
    on_missing : {'ignore', 'warn', 'raise'}
    include_help : False
        Ignored. JSON can't print help
    out_stream : file_ptr
    indent : int

    See Also
    --------
    ParameterizedPrintAction
        A full description of the parameters and behaviour of like actions
    pydrobert.param.serialization.serialize_to_json
        A description of the serialization process and of the additional
        parameters
    '''

    def __init__(
            self, option_strings, dest,
            parameterized=None, type=None, serializer_name_dict=None,
            serializer_type_dict=None, only=None, on_missing='raise',
            help=None, out_stream=sys.stdout, indent=2):
        self.indent = indent
        super(ParameterizedJsonPrintAction, self).__init__(
            option_strings, dest,
            parameterized=parameterized, type=type,
            serializer_name_dict=serializer_name_dict,
            serializer_type_dict=serializer_type_dict, only=only,
            on_missing=on_missing, include_help=False, help=help,
            out_stream=out_stream,
        )

    def print_parameters(self):
        serialization.serialize_to_json(
            self.out_stream, self.parameterized, only=self.only,
            serializer_name_dict=self.serializer_name_dict,
            serializer_type_dict=self.serializer_type_dict,
            on_missing=self.on_missing, indent=self.indent,
        )


class ParameterizedYamlPrintAction(ParameterizedPrintAction):
    '''Print parameters as YAML and exit

    Parameters
    ----------
    option_strings : list
    dest : str
    parameterized : param.Parameterized or dict, optional
    type : type, optional
    serializer_name_dict : dict, optional
    serializer_type_dict : dict, optional
    only : set or dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
    include_help : bool, optional
    help : str, optional
    out_stream : file_ptr, optional

    Attributes
    ----------
    parameterized : param.Parameterized or dict
    serializer_name_dict : dict
    serializer_type_dict : dict
    only : set or dict
    on_missing : {'ignore', 'warn', 'raise'}
    include_help : boolean
    out_stream : file_ptr
    '''

    def print_parameters(self):
        serialization.serialize_to_yaml(
            self.out_stream, self.parameterized, only=self.only,
            serializer_name_dict=self.serializer_name_dict,
            serializer_type_dict=self.serializer_type_dict,
            on_missing=self.on_missing, include_help=self.include_help,
        )
