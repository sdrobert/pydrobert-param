# Copyright 2022 Sean Robertson
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


from __future__ import annotations


import argparse
import abc
import sys
from typing import List, Optional, Sequence, TextIO, Tuple, Type, Union, Collection
from xml.etree.ElementInclude import include

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

import param

from ._classic_serialization import (
    deserialize_from_ini,
    deserialize_from_json,
    deserialize_from_yaml,
    serialize_to_ini,
    serialize_to_json,
    serialize_to_yaml,
)
from ._file_serialization import yaml_is_available
from . import config


class ParameterizedFileReadAction(argparse.Action, metaclass=abc.ABCMeta):
    """Base class for deserializing files into a Parameterized object

    Subclasses of this class can be added as the 'action' keyword to an
    :func:`argparse.ArgumentParser.add_argument` call. The action will read the file
    path passed as an argument via command line and use the contents of the file to
    populate :class:`param.parameterized.Parameterized` instances. The subclass
    deserializes the contents of the file according to the
    :func:`pydrobert.param.serialization.deserialize_from_filetype` function, where
    ``filetype`` is replaced with the subclass' file type.

    There are three ways to specify parameterized objects to populate. They are mutually
    exclusive:

    1. Set the keyword `type` with the subclass of
       :class:`param.parameterized.Parameterized` you want to deserialize into. A new
       instance of that subclass will be created with the name ``type.__name__``. The
       instance will be returned in the parsed namespace's attribute whose name matches
       `dest` as well.

    2. Set the keyword `parameterized` with an instance of
       :class:`param.parameterized.Parameterized`. That instance will be populated and
       also returned in the parsed namespace's attribute whose name matches `dest`.

    3. Set the keyword `parameterized` as a hierarchical dictionary of
       :class:`param.parameterized.Parameterized` instances. The leaves of the
       dictionary will be populated according to the "hierarchical mode" specified in
       the documentation of :func:`pydrobert.param.serialization.deserialize_from_dict`.
       The same dictionary will be returned in the parsed namespace's attribute whose
       name matches `dest`.

    Parameters
    ----------
    option_strings
        A list of command-line option strings which should be associated with this
        action.
    dest
        The name of the attribute to hold the created object.
    parameterized
    type
    deserializer_name_dict
        Use specific deserializers for parameters with specific names.
    deserializer_type_dict
        Use specific deserializers for parameters with exactly matching types.
    on_missing
        What to do if the parameterized instance does not have a parameter listed in the
        config file.
    required
        :obj:`True` if the action must always be specified at the command line. This is
        only meaningful for optional command-line arguments.
    help
        The help string describing the argument.
    metavar
        The name to be used for the option's argument with the help string. If
        :obj:`None`, the `dest` value will be used as the name.
    nargs
        The number of command line arguments to be consumed. When more than one argument
        is specified, each will be deserialized in the order that they were presented on
        the command line. Thus, later config values will clobber earlier ones
    const
        If `nargs` is :obj:`'?'` but the flag is present on the command line, this value
        will be supplied as the missing argument

    See Also
    --------
    pydrobert.param.serialization.deserialize_from_dict
        For more information on how values are deserialized from the config
    
    """

    parameterized: Union[param.Parameterized, dict]
    deserializer_name_dict: Optional[dict]
    deserializer_type_dict: Optional[dict]
    on_missing: Literal["ignore", "warn", "raise"]

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        parameterized: Optional[Union[param.Parameterized, dict]] = None,
        type: Optional[Type[param.Parameterized]] = None,
        deserializer_name_dict: Optional[dict] = None,
        deserializer_type_dict: Optional[dict] = None,
        on_missing: Literal["ignore", "warn", "raise"] = "warn",
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[str] = None,
        nargs: Optional[Union[str, int]] = None,
        const: Optional[str] = None,
    ):
        if parameterized is None and type is None:
            raise TypeError("one of parameterized or type must be set")
        if parameterized is not None and type is not None:
            raise TypeError("only one of parameterized or type can be set")
        if parameterized is None:
            self.parameterized = type(name=type.__name__)
        else:
            self.parameterized = parameterized
        self.deserializer_name_dict = deserializer_name_dict
        self.deserializer_type_dict = deserializer_type_dict
        self.on_missing = on_missing
        super(ParameterizedFileReadAction, self).__init__(
            option_strings,
            dest,
            type=argparse.FileType("r"),
            default=self.parameterized,
            required=required,
            help=help,
            metavar=metavar,
            nargs=nargs,
            const=const,
        )

    @abc.abstractmethod
    def deserialize(self, fp: Union[TextIO, str]) -> None:
        """Read the file pointer into parameterized objects

        Called during the callable section of this class. Implemented by
        subclasses.
        """
        raise NotImplementedError()

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values,
        option_string: Optional[str] = None,
    ) -> None:
        # the latter occurs with, for example, nargs='*' and empty args
        if values is None or values == self.parameterized:
            return
        if not isinstance(values, list):
            values = [values]
        for fp in values:
            self.deserialize(fp)


class ParameterizedIniReadAction(ParameterizedFileReadAction):
    """Deserialize an INI file into a parameterized object

    Parameters
    ----------
    option_strings
    dest
    parameterized
    type
    deserializer_name_dict
    deserializer_type_dict
    on_missing
    required
    help
    metavar
    nargs
    const
    defaults
    comment_prefixes
    inline_comment_prefixes
    one_param_section

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    pydrobert.param.serialization.deserialize_from_ini
        A description of the deserialization process and of the additional
        parameters.
    """

    defaults: Optional[dict]
    comment_prefixes: Tuple[str, ...]
    inline_comment_prefixes: Tuple[str, ...]
    one_param_section: Optional[str]

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        parameterized: Optional[Union[param.Parameterized, dict]] = None,
        type: Optional[Type[param.Parameterized]] = None,
        deserializer_name_dict: Optional[dict] = None,
        deserializer_type_dict: Optional[dict] = None,
        on_missing: Literal["ignore", "warn", "raise"] = "warn",
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[str] = None,
        nargs: Optional[Union[str, int]] = None,
        const: Optional[str] = None,
        defaults: Optional[dict] = None,
        comment_prefixes: Sequence[str] = ("#", ";"),
        inline_comment_prefixes: Sequence[str] = (";",),
        one_param_section: Optional[str] = None,
    ):
        self.defaults = defaults
        self.comment_prefixes = tuple(comment_prefixes)
        self.inline_comment_prefixes = tuple(inline_comment_prefixes)
        self.one_param_section = one_param_section
        super().__init__(
            option_strings,
            dest,
            parameterized=parameterized,
            type=type,
            deserializer_name_dict=deserializer_name_dict,
            deserializer_type_dict=deserializer_type_dict,
            on_missing=on_missing,
            required=required,
            help=help,
            metavar=metavar,
            nargs=nargs,
            const=const,
        )

    def deserialize(self, fp: Union[TextIO, str]) -> None:
        deserialize_from_ini(
            fp,
            self.parameterized,
            deserializer_name_dict=self.deserializer_name_dict,
            deserializer_type_dict=self.deserializer_type_dict,
            on_missing=self.on_missing,
            defaults=self.defaults,
            comment_prefixes=self.comment_prefixes,
            inline_comment_prefixes=self.inline_comment_prefixes,
            one_param_section=self.one_param_section,
        )


class ParameterizedYamlReadAction(ParameterizedFileReadAction):
    """Deserialize a YAML file into a parameterized object

    Parameters
    ----------
    option_strings
    dest
    parameterized
    type
    deserializer_name_dict
    deserializer_type_dict
    on_missing
    required
    help
    metavar
    nargs
    const

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions
    pydrobert.param.serialization.deserialize_from_yaml
        A description of the deserialization process.
    """

    def deserialize(self, fp: Union[TextIO, str]) -> None:
        deserialize_from_yaml(
            fp,
            self.parameterized,
            deserializer_name_dict=self.deserializer_name_dict,
            deserializer_type_dict=self.deserializer_type_dict,
            on_missing=self.on_missing,
        )


class ParameterizedJsonReadAction(ParameterizedFileReadAction):
    """Deserialize a JSON file into a parameterized object

    Parameters
    ----------
    option_strings
    dest
    parameterized
    type
    deserializer_name_dict
    deserializer_type_dict
    on_missing
    required
    help
    metavar
    nargs
    const

    See Also
    --------
    ParameterizedFileReadAction
        A full description of the parameters and behaviour of like actions.
    pydrobert.param.serialization.deserialize_from_json
        A description of the deserialization process.
    """

    def deserialize(self, fp: Union[TextIO, str]) -> None:
        deserialize_from_json(
            fp,
            self.parameterized,
            deserializer_name_dict=self.deserializer_name_dict,
            deserializer_type_dict=self.deserializer_type_dict,
            on_missing=self.on_missing,
        )


def add_parameterized_read_group(
    parser: argparse.ArgumentParser,
    parameterized: Optional[Union[param.Parameterized, dict]] = None,
    type: Optional[Type[param.Parameterized]] = None,
    include_yaml: Optional[bool] = None,
    ini_option_strings: Sequence[str] = ("--read-ini",),
    json_option_strings: Sequence[str] = ("--read-json",),
    yaml_option_strings: Sequence[str] = ("--read-yaml",),
    dest: str = "params",
    ini_kwargs: dict = dict(),
    json_kwargs: dict = dict(),
    yaml_kwargs: dict = dict(),
):
    r'''Add flags to read configs from INI, JSON, or YAML sources

    This convenience function adds a mutually exclusive group of read actions
    to `parser` to read in parameters from 3 file types: INI, JSON, or YAML.

    What to read into is determined by the keyword args `type` or
    `parameterized`.

    1. If `type` is specified, it will be instantiated and populated. Its name will
       match ``type.__name__``

    2. If `parameterized` is specified and is a
       :class:`param.parameterized.Parameterized` instance, it will be populated
       directly.

    3. If `parameterized` is a dictionary whose leaves are
       :class:`param.parameterized.Parameterized`, sections of the config whose keys
       match the keys of the dictionary will populate the corresponding
       :class:`param.parameterized.Parameterized` instances. `parameterized` can nest
       those instances repeatedly, but only a shallow dict will be able to be parsed
       from an INI file

    Parameters
    ----------
    parser
    type
    parametrized
    include_yaml
        Whether to include the YAML config flags. YAML requires one of
        :mod:`ruamel.yaml` or :mod:`yaml` to be installed. If unset, we will include the
        flags if it is possible to import a YAML module.
    ini_option_strings
        Zero or more option strings specifying that the next argument is an INI file to
        be read. If no option strings are specified, INI reading is disabled
    json_option_strings
        Zero or more option strings specifying that the next argument is an JSON file to
        be read. If no option strings are specified, JSON reading is disabled
    yaml_option_strings
        Zero or more option strings specifying that the next argument is an YAML file to
        be read. If no option strings are specified, YAML reading is disabled
    dest
        Under what name to store parameters in the returned namespace of
        ``parser.parse_args(...)``
    ini_kwargs
        Additional keyword arguments to use when creating the INI flag. See
        :class:`ParameterizedIniReadAction` for more info
    json_kwargs
        Additional keyword arguments to use when creating the JSON flag. See
        :class`ParameterizedJsonReadAction` for more info
    yaml_kwargs
        Additional keyword arguments to use when creating the YAML flag. See
        :class`ParameterizedYamlReadAction` for more info

    Returns
    -------
    group : obj
        The mutually exclusive group containing the flags

    Examples
    --------

    >>> # write some configs
    >>> with open('config.ini', 'w') as f:
    >>>     f.write('[DEFAULT]\nfoo = a\n')
    >>> with open('config.json', 'w') as f:
    >>>     f.write('{"foo": "b"}\n')
    >>> # make our Parameterized type
    >>> import param, argparse
    >>> class MyParams(param.Parameterized):
    >>>     foo = param.String(None)
    >>> # make our parser
    >>> parser = argparse.ArgumentParser()
    >>> add_parameterized_read_group(parser, type=MyParams)
    >>> # parse an INI
    >>> options = parser.parse_args(['--read-ini', 'config.ini'])
    >>> assert options.params.foo == "a"
    >>> # parse a JSON
    >>> options = parser.parse_args(['--read-json', 'config.json'])
    >>> assert options.params.foo == "b"

    >>> # write a hierarchical config
    >>> with open('config.yaml', 'w') as f:
    >>>     f.write("""
    ... A:
    ...   foo: bar
    ...   baz: 1
    ... B:
    ...   B.1:
    ...     me: I may
    ...   B.2:
    ...     me: me me mee
    ... """)
    >>> # make our Parameterized types
    >>> class A(param.Parameterized):
    >>>     foo = param.String(None)
    >>>     bar = param.Integer(None)
    >>> class B(param.Parameterized):
    >>>     me = param.String(None)
    >>> parameterized = {'A': A(), 'B': {'B.1': B(), 'B.2': B()}}
    >>> # make our parser
    >>> parser = argparse.ArgumentParser()
    >>> add_parameterized_read_group(parser, parameterized=parameterized)
    >>> # parse YAML (requires package ruamel.yaml/ruamel_yaml or pyyaml)
    >>> parser.parse_args(['--read-yaml', 'config.yaml'])
    >>> assert parameterized['A'].baz == 1
    >>> assert parameterized['B']['B.2'].me == 'me me mee'
    '''
    if parameterized is None and type is None:
        raise TypeError("one of parameterized or type must be set")
    if parameterized is not None and type is not None:
        raise TypeError("only one of parameterized or type can be set")
    for name, dict_ in (
        ("ini", ini_kwargs),
        ("json", json_kwargs),
        ("yaml", yaml_kwargs),
    ):
        keys = set(dict_) & {"dest", "type", "parameterized"}
        if keys:
            raise TypeError(
                "{}_kwargs contains unexpected keyword arguments: {}"
                "".format(name, ", ".join(sorted(keys)))
            )
    if parameterized is None:
        parameterized = type(name=type.__name__)
    group = parser.add_mutually_exclusive_group()
    if ini_option_strings:
        group.add_argument(
            *ini_option_strings,
            action=ParameterizedIniReadAction,
            dest=dest,
            parameterized=parameterized,
            **ini_kwargs
        )
    if json_option_strings:
        group.add_argument(
            *json_option_strings,
            action=ParameterizedJsonReadAction,
            dest=dest,
            parameterized=parameterized,
            **json_kwargs
        )
    if include_yaml is None:
        include_yaml = yaml_is_available()
    if include_yaml and len(yaml_option_strings):
        group.add_argument(
            *yaml_option_strings,
            action=ParameterizedYamlReadAction,
            dest=dest,
            parameterized=parameterized,
            **yaml_kwargs
        )
    return group


class ParameterizedPrintAction(argparse.Action, metaclass=abc.ABCMeta):
    """Base class for printing parameters to stdout and exiting

    Subclasses of this class can be added as the 'action' keyword to an
    :func:`argparse.ArgumentParser.add_argument` call. Like the ``--help`` flag, after
    this action is called, the program will try to exit, but not before printing out
    parameters.

    There are three ways to specify what parameters to print, analogous to how they are
    specified in :class:`ParameterizedFileReadAction`:

    1. Set the keyword `type` with a subclass of
       :class:`param.parameterized.Parameterized`. A new instance of that type will be
       created to be printed. Its name will be ``type.__name__``

    2. Set the keyword `parameterized` with an instance of
       :class:`param.parameterized.Parameterized`. That instance will be printed.

    3. Set the keyword `parameterized` as a hierarchical dictionary of
       :class:`param.parameterized.Parameterized` instances. The leaves of the
       dictionary will be populated according to the "hierarchical mode" specified in
       the documentation of :func:`pydrobert.param.serialization.serialize_to_dict`

    Note that if a :class:`ParameterizedFileReadAction` has been called on the command
    line prior to the print that shares the same `parameterized` value as in 2. or 3.,
    `parameterized` will be populated by that file's contents.

    Parameters
    ----------
    option_strings
        A list of command-line option strings which should be associated with this
        action.
    dest
        Ignored
    parameterized
    type
    serializer_name_dict
        Use specific serializers for parameters with specific names
    serializer_type_dict
        Use specific serializers for parameters with exactly matching types
    only
        If specified, only the parameters with their names in this set will be printed
    on_missing
        What to do if the parameterized instance does not have a parameter listed in
        `only`
    include_help
        Whether to print parameter help when printing parameters
    help
        The help string describing the argument
    out_stream
        Where to print the parameters to
    """

    parameterized: Union[param.Parameterized, dict]
    serializer_name_dict: Optional[dict]
    serializer_type_dict: Optional[dict]
    only: Collection[str]
    on_missing: Literal["ignore", "warn", "raise"]
    include_help: bool
    out_stream: TextIO

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        parameterized: Optional[Union[dict, param.Parameterized]] = None,
        type: Optional[Type[param.Parameterized]] = None,
        serializer_name_dict: Optional[dict] = None,
        serializer_type_dict: Optional[dict] = None,
        only: Optional[Collection[str]] = None,
        on_missing: Literal["ignore", "warn", "raise"] = "raise",
        include_help: bool = True,
        help: Optional[str] = None,
        out_stream: TextIO = sys.stdout,
    ):
        if parameterized is None and type is None:
            raise TypeError("one of parameterized or type must be set")
        if parameterized is not None and type is not None:
            raise TypeError("only one of parameterized or type can be set")
        if parameterized is None:
            self.parameterized = type(name=type.__name__)
        else:
            self.parameterized = parameterized
        self.serializer_name_dict = serializer_name_dict
        self.serializer_type_dict = serializer_type_dict
        self.only = only
        self.on_missing = on_missing
        self.include_help = include_help
        self.out_stream = out_stream
        super(ParameterizedPrintAction, self).__init__(
            option_strings, dest, help=help, nargs=0
        )

    @abc.abstractmethod
    def print_parameters(self) -> None:
        """Print the parameters

        Called during the callable section of this class. Should print to the
        attribute `out_stream`
        """
        raise NotImplementedError()

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values,
        option_string: Optional[str] = None,
    ) -> None:
        self.print_parameters()
        parser.exit()


class ParameterizedIniPrintAction(ParameterizedPrintAction):
    """Print parameters as INI and exit

    Parameters
    ----------
    option_strings
    dest
    parameterized
    type
    serializer_name_dict
    serializer_type_dict
    only
    on_missing
    include_help
    help
    out_stream
    help_prefix
    one_param_section

    See Also
    --------
    ParameterizedPrintAction
        A full description of the parameters and behaviour of like actions
    pydrobert.param.serialization.serialize_to_ini
        A description of the serialization process and of the additional parameters
    """

    help_prefix: str
    one_param_section: Optional[str]

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        parameterized: Optional[Union[param.Parameterized, dict]] = None,
        type: Optional[Type[param.Parameterized]] = None,
        serializer_name_dict: Optional[dict] = None,
        serializer_type_dict: Optional[dict] = None,
        only: Optional[Collection[str]] = None,
        on_missing: Literal["ignore", "warn", "raise"] = "raise",
        include_help: bool = True,
        help: Optional[str] = None,
        out_stream: TextIO = sys.stdout,
        help_prefix: str = "#",
        one_param_section: Optional[str] = None,
    ):
        self.help_prefix = help_prefix
        self.one_param_section = one_param_section
        super(ParameterizedIniPrintAction, self).__init__(
            option_strings,
            dest,
            parameterized=parameterized,
            type=type,
            serializer_name_dict=serializer_name_dict,
            serializer_type_dict=serializer_type_dict,
            only=only,
            on_missing=on_missing,
            include_help=include_help,
            help=help,
            out_stream=out_stream,
        )

    def print_parameters(self):
        serialize_to_ini(
            self.out_stream,
            self.parameterized,
            only=self.only,
            serializer_name_dict=self.serializer_name_dict,
            serializer_type_dict=self.serializer_type_dict,
            on_missing=self.on_missing,
            include_help=self.include_help,
            help_prefix=self.help_prefix,
            one_param_section=self.one_param_section,
        )


class ParameterizedJsonPrintAction(ParameterizedPrintAction):
    """Print parameters as JSON and exit

    Parameters
    ----------
    option_strings
    dest
    parameterized
    type
    serializer_name_dict
    serializer_type_dict
    only
    on_missing
    out_stream
    indent

    See Also
    --------
    ParameterizedPrintAction
        A full description of the parameters and behaviour of like actions
    pydrobert.param.serialization.serialize_to_json
        A description of the serialization process and of the additional parameters
    """

    indent: int

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        parameterized: Optional[Union[param.Parameterized, dict]] = None,
        type: Optional[Type[param.Parameterized]] = None,
        serializer_name_dict: Optional[dict] = None,
        serializer_type_dict: Optional[dict] = None,
        only: Optional[Collection[str]] = None,
        on_missing: Literal["ignore", "warn", "raise"] = "raise",
        help: Optional[str] = None,
        out_stream: TextIO = sys.stdout,
        indent: int = 2,
    ):
        self.indent = indent
        super(ParameterizedJsonPrintAction, self).__init__(
            option_strings,
            dest,
            parameterized=parameterized,
            type=type,
            serializer_name_dict=serializer_name_dict,
            serializer_type_dict=serializer_type_dict,
            only=only,
            on_missing=on_missing,
            include_help=False,
            help=help,
            out_stream=out_stream,
        )

    def print_parameters(self) -> None:
        serialize_to_json(
            self.out_stream,
            self.parameterized,
            only=self.only,
            serializer_name_dict=self.serializer_name_dict,
            serializer_type_dict=self.serializer_type_dict,
            on_missing=self.on_missing,
            indent=self.indent,
        )


class ParameterizedYamlPrintAction(ParameterizedPrintAction):
    """Print parameters as YAML and exit

    Parameters
    ----------
    option_strings
    dest
    parameterized
    type
    serializer_name_dict
    serializer_type_dict
    only
    on_missing
    include_help
    help
    out_stream

    See Also
    --------
    ParameterizedPrintAction
        A full description of the parameters and behaviour of like actions
    pydrobert.param.serialization.serialize_to_yaml
        A description of the serialization process and of the additional parameters
    """

    def print_parameters(self) -> None:
        serialize_to_yaml(
            self.out_stream,
            self.parameterized,
            only=self.only,
            serializer_name_dict=self.serializer_name_dict,
            serializer_type_dict=self.serializer_type_dict,
            on_missing=self.on_missing,
            include_help=self.include_help,
        )


def add_parameterized_print_group(
    parser: argparse.ArgumentParser,
    type: Optional[Type[param.Parameterized]] = None,
    parameterized: Optional[Union[param.Parameterized, dict]] = None,
    include_yaml: Optional[bool] = None,
    ini_option_strings: Sequence[str] = ("--print-ini",),
    json_option_strings: Sequence[str] = ("--print-json",),
    yaml_option_strings: Sequence[str] = ("--print-yaml",),
    ini_kwargs: dict = dict(),
    json_kwargs: dict = dict(),
    yaml_kwargs: dict = dict(),
):
    """Add flags to print parameters as INI, JSON, or YAML

    This convenience function adds a group of print actions to `parser` to
    print parameters and exit in one of INI, JSON, or YAML format.

    What to print is determined by the keyword args `type` or `parameterized`.

    1. If `type` is specified, it will be instantiated and printed with
       whatever defaults it has. The instance will have the name
       ``type.__name__``

    2. If `parameterized` is a :class:`param.parameterized.Parameterized` instance, that
       instance will be printed

    3. If `parameterized` is a dictionary of :class:`param.parameterized.Parameterized`
       instances, those instances will be serialized to dictionaries, then the
       dictionary of dictionaries will be printed. `parameterized` can contain nested
       dictionaries of :class:`param.parameterized.Parameterized` instances, but it will
       be unable to be printed as an INI file, only JSON or YAML

    Parameters
    ----------
    parser
    type
    parametrized
    include_yaml
        Whether to include the YAML print flags. YAML requires one of :mod:`ruamel.yaml`
        or :mod:`yaml` to be installed. If unset, we will include the flags if it is
        possible to import a YAML module.
    ini_option_strings
        Zero or more option strings specifying that INI format should be printed. If no
        option strings are specified, INI printing is disabled
    json_option_strings
        Zero or more option strings specifying that JSON format should be printed. If no
        option strings are specified, JSON printing is disabled
    yaml_option_strings
        Zero or more option strings specifying that YAML format should be printed. If no
        option strings are specified, YAML printing is disabled
    ini_kwargs
        Additional keyword arguments to use when creating the INI flag. See
        :class:`ParameterizedIniPrintAction` for more info
    json_kwargs
        Additional keyword arguments to use when creating the JSON flag. See
        :class:`ParameterizedJsonPrintAction` for more info
    yaml_kwargs
        Additional keyword arguments to use when creating the YAML flag. See
        :class:`ParameterizedYamlPrintAction` for more info

    Returns
    -------
    group : obj
        The group containing the flags

    Examples
    --------

    >>> import param, argparse
    >>> class MyParams(param.Parameterized):
    ...     an_int = param.Integer(1)
    ...     a_bool = param.Boolean(True)
    >>> parser = argparse.ArgumentParser()
    >>> add_parameterized_print_group(parser, type=MyParams)
    >>> try:
    ...     parser.parse_args(['--print-ini'])
    ... except SystemExit:
    ...     pass
    [MyParams]
    a_bool = true
    an_int = 1
    >>> try:
    ...     # only works if ruamel.yaml/ruamel_yaml or pyyaml installed
    ...     parser.parse_args(['--print-yaml'])
    ... except SystemExit:
    ...     pass
    a_bool: true
    an_int: 1

    >>> import param, argparse
    >>> class A(param.Parameterized):
    ...     something = param.Integer(None)
    ...     else_ = param.List([1, 2])
    >>> class B(param.Parameterized):
    ...     float_ = param.Number(3.14)
    >>> parameterized = {'A': {'AA': A()}, 'B': B()}
    >>> parser = argparse.ArgumentParser()
    >>> add_parameterized_print_group(
    ...     parser, parameterized=parameterized, json_kwargs={'indent': None})
    >>> try:
    ...     parser.parse_args(['--print-json'])
    ... except SystemExit:
    ...     pass
    {"A": {"AA": {"else_": [1, 2], "something": null}}, "B": {"float_": 3.14}}

    Notes
    -----
    The returned `group` is technically mutally exclusive. However, since the print
    action ends with a :func:`sys.exit` call, mutual exclusivity will never be enforced
    """
    if parameterized is None and type is None:
        raise TypeError("one of parameterized or type must be set")
    if parameterized is not None and type is not None:
        raise TypeError("only one of parameterized or type can be set")
    for name, dict_ in (
        ("ini", ini_kwargs),
        ("json", json_kwargs),
        ("yaml", yaml_kwargs),
    ):
        keys = set(dict_) & {"type", "parameterized"}
        if keys:
            raise TypeError(
                "{}_kwargs contains unexpected keyword arguments: {}"
                "".format(name, ", ".join(sorted(keys)))
            )
    if type is not None:
        parameterized = type(name=type.__name__)
    group = parser.add_mutually_exclusive_group()
    if ini_option_strings:
        group.add_argument(
            *ini_option_strings,
            action=ParameterizedIniPrintAction,
            parameterized=parameterized,
            **ini_kwargs
        )
    if json_option_strings:
        group.add_argument(
            *json_option_strings,
            action=ParameterizedJsonPrintAction,
            parameterized=parameterized,
            **json_kwargs
        )
    if include_yaml is None:
        include_yaml = yaml_is_available()
    if include_yaml and len(yaml_option_strings):
        group.add_argument(
            *yaml_option_strings,
            action=ParameterizedYamlPrintAction,
            parameterized=parameterized,
            **yaml_kwargs
        )
    return group
