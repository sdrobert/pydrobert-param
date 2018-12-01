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
    of the file to populate a `param.Parameterized` instance. Note that
    the `dest` attribute of the parsed namespace will always be populated by
    a parameterized instance, whether or not the argument was specified on
    the command line.

    The `param.Parameterized` object to fill can be specified using either
    the keyword `parameterized` or `type` in the list of keywords. One,
    *and only one*, must always be specified. Two additional keywords for the
    main mechanism of deserialization,
    `pydrobert.param.serialization.deserialize_from_dict`, can be set.

    Parameters
    ----------
    option_strings : list
        A list of command-line option strings which should be associated with
        this action.
    dest : str
        The name of the attribute to hold the created object. In this case,
        the `param.Parameterized` instance.
    parameterized : param.Parameterized or dict, optional
        If set, `parameterized` will be directly stored in the `dest`
        attribute of the parsed namespace. If `parameterized` is a
        `param.Parameterized` instance, that instance will be populated
        directly. Othewise, `parameterized` is treated as a hierarchical
        dictionary. A non-dict value in the `parameterized` dict is assumed to
        be a `param.Parameterized` instance. The path of keys through the
        `parameterized` dict is taken through the config file as well, allowing
        more than one `param.Parameterized` instance to be populated with one
        file.
    type : type, optional
        If set, an instance of a `param.Parameterized` object of this type
        with a name `dest` will be created, populated, and stored in the
        `dest` attribute.
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


    See Also
    --------
    pydrobert.param.serialization.deserialize_from_dict
        For more information on how values are deserialized from the config
    '''

    def __init__(
            self, option_strings, dest,
            parameterized=None, type=None, deserializer_name_dict=None,
            deserializer_type_dict=None, on_missing='warn', section=None,
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
    def fp_to_dict(self, fp):
        '''Convert the file pointer to a dictionary of values to deserialize'''
        raise NotImplementedError()

    def __call__(self, parser, namespace, values, option_string=None):
        dict_ = self.fp_to_dict(values)
        dict_stack = [dict_]
        param_stack = [self.parameterized]
        while len(dict_stack):
            dict_ = dict_stack.pop()
            parameterized = param_stack.pop()
            if isinstance(parameterized, param.Parameterized):
                serialization.deserialize_from_dict(
                    dict_, parameterized,
                    deserializer_name_dict=self.deserializer_name_dict,
                    deserializer_type_dict=self.deserializer_type_dict,
                    on_missing=self.on_missing,
                )
            else:
                for key, value in parameterized.items():
                    dict_stack.append(dict_[key])
                    param_stack.append(value)


class ParameterizedIniReadAction(ParameterizedFileReadAction):
    '''Deserialize a .INI file into a parameterized object

    `.INI syntax <https://en.wikipedia.org/wiki/INI_file>`, also including
    interpolation. .INI files are broken up into sections; all key-value
    pairs must belong to a section. If a section has not been specified
    through the `parameterized` keyword, the action will try to deserialize
    the default section

    Additional Parameters
    ---------------------
    defaults : dict, optional
        Intrinsic defaults used in interpolation
    comment_prefixes : tuple, optional
        In Python 3.x, this controls which characters indicate an inline
        comment. Ignored in 2.7
    inline_comment_prefixes : tuple, optional
        In Python 3.x, this controls which characters indicate an inline
        comment. Ignored in 2.7

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    configparser.ConfigParser
        Description of .INI file parsing and interpolation
    '''

    def __init__(
            self, option_strings, dest,
            defaults=None,
            comment_prefixes=('#', ';'),
            inline_comment_prefixes=(';',),
            **kwargs):
        self.defaults = defaults
        self.comment_prefixes = comment_prefixes
        self.inline_comment_prefixes = inline_comment_prefixes
        super(ParameterizedIniReadAction, self).__init__(
            option_strings, dest, **kwargs)

    def fp_to_dict(self, fp):
        from configparser import ConfigParser
        try:
            parser = ConfigParser(
                defaults=self.defaults,
                comment_prefixes=self.comment_prefixes,
                inline_comment_prefixes=self.inline_comment_prefixes,
            )
        except TypeError:  # probably py2.7
            parser = ConfigParser(defaults=self.defaults)
        parser.read_file(fp)
        if isinstance(self.parameterized, param.Parameterized):
            parser = parser[parser.default_section]
        return parser


class ParameterizedYamlReadAction(ParameterizedFileReadAction):
    '''Deserialize a .yaml file into a parameterized object

    `YAML syntax <https://en.wikipedia.org/wiki/YAML>`. This action tries
    to load the python module `ruamel.yaml` to parse the file. If that
    cannot be loaded, `yaml` is attempted.

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    '''

    def fp_to_dict(self, fp):
        yaml = None
        try:
            from ruamel.yaml import YAML
            yaml = YAML()
        except ImportError:
            pass
        if yaml is None:
            try:
                # conda?
                from ruamel_yaml import YAML
                yaml = YAML()
            except ImportError:
                pass
        if yaml is None:
            try:
                import yaml
            except ImportError:
                pass
        if yaml is None:
            raise ImportError(
                "One of ruamel.yaml, ruamel_yaml or pyyaml is needed to "
                "parse a YAML config")
        return yaml.load(fp)


class ParameterizedJsonReadAction(ParameterizedFileReadAction):
    '''Deserialize a .JSON file into a parameterized object

    `JSON syntax <https://en.wikipedia.org/wiki/JSON>`

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    json
        The module used in json reading.
    '''

    def fp_to_dict(self, fp):
        import json
        return json.load(fp)
