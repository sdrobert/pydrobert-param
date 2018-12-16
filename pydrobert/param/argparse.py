"""Hooks for command-line interface with params"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import abc

import param
import pydrobert.param.serialization as serialization

from future.utils import with_metaclass

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2018 Sean Robertson"


class ParameterizedFileReadAction(
        with_metaclass(abc.ABCMeta, argparse.Action)):
    '''Base class for deserializing files into a param.Parameterized object

    Subclasses of this class can be added as the 'action' keyword to an
    `argparse.ArgumentParser.add_argument()` call. The action will read the
    file path passed as an argument via command line and use the contents
    of the file to populate `param.Parameterized` instances. The subclass
    deserializes the contents of the file according to the
    ``pydrobert.param.serialization.deserializing_from_filetype`` function,
    where ``filetype`` is replaced with the subclass' file type.

    There are three ways to specify parameterized objects to populate. They
    are mutually exclusive:
    1. Set the keyword `type` with the subclass of `param.Parameterized` you
       want to deserialize into. A new instance of that subclass will be
       created with a name matching `dest`. The instance will be returned in
       the parsed namespace's attribute whose name matches `dest` as well.
    2. Set the keyword `parameterized` with an instance of
       `param.Parameterized`. That instance will be populated and also
       returned in the parsed namespace's attribute whose name matches `dest`.
    3. Set the keyword `parameterized` as a hierarchical dictionary of
       ``param.Parameterized`` instances. The leaves of the dictionary will
       be populated according to the "hierarchical mode" specified in the
       documentation of ``pydrobert.param.serialization.serialize_from_dict``.
       The same dictionary will be returned in the parsed namespace's attribute
       whose name matches `dest`.

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
            required=False, help=None, metavar=None):
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
        )

    @abc.abstractmethod
    def deserialize(self, fp):
        '''Read the file pointer into parameterized objects

        Called during the callable section of this class. Implemented by
        subclasses.
        '''
        raise NotImplementedError()

    def __call__(self, parser, namespace, values, option_string=None):
        self.deserialize(values)


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
            required=False, help=None, metavar=None,
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
            metavar=metavar,
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
