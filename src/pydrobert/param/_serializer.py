# Copyright 2022 Sean Robertson
#
# The Serialization subclasses are heavily inspired by the source code for
# JSONSerialization from the param package:
# https://github.com/holoviz/param/blob/76c7026346b73951dcf4308b6302f0742b0e83e7/param/serializer.py#L61
#
# param is BSD-3 licensed:
#
# Copyright (c) 2005-2022, HoloViz team.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are
# permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this list of
#    conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice, this list
#    of conditions and the following disclaimer in the documentation and/or other
#    materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of any contributors may be
#    used to endorse or promote products derived from this software without specific
#    prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT
# SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY
# WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.
#
# This code (Apache v2.0):
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this
# file except in compliance with the License. You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific language
# governing permissions and limitations under the License.

import abc
import argparse
import textwrap
import json
import sys

from typing import (
    Any,
    Collection,
    Dict,
    List,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    Type,
    Union,
)
from io import StringIO

try:
    from typing import Protocol, Literal
except ImportError:
    from typing_extensions import Protocol, Literal

import param

from param.serializer import Serialization

from ._file_serialization import (
    yaml_is_available,
    deserialize_from_yaml_to_obj,
    serialize_from_obj_to_yaml,
)


class Serializable(Protocol):
    @abc.abstractclassmethod
    def loads(cls, serialized: str) -> Any:
        """Read serialized string into an object"""
        ...

    @abc.abstractclassmethod
    def dumps(cls, obj: Any, help: Any = None) -> str:
        """Dump object (and optional help object) to string
        
        `help` should not impact the deserialization of `obj`. It can be ignored.
        """
        ...


class JsonSerializable(Serializable):
    @classmethod
    def loads(cls, serialized: str) -> Any:
        return json.loads(serialized)

    @classmethod
    def dumps(cls, obj: Any, help: Any = None) -> str:
        return json.dumps(obj)


class YamlSerializable(Serializable):
    @classmethod
    def loads(cls, serialized: str) -> Any:
        with StringIO(serialized) as s:
            return deserialize_from_yaml_to_obj(s)

    @classmethod
    def dumps(cls, obj: Any, help: Any = None) -> str:
        with StringIO() as s:
            serialize_from_obj_to_yaml(s, obj, help)
            s.seek(0)
            return s.read()


PObjType = Union[param.Parameterized, Type[param.Parameterized]]
NestedSubsetType = Optional[Dict[str, "NestedSubsetType"]]


class SerializableSerialization(Serialization, Serializable):
    """ABC for sensible serialization"""

    @classmethod
    def nest_subsets(cls, subset: Optional[Collection[str]]) -> NestedSubsetType:
        if subset is None:
            return subset
        nested_subsets: NestedSubsetType = dict()
        for s in subset:
            if "." in s:
                k, v = s.split(".", maxsplit=1)
                v = cls.nest_subsets({v})
                d = nested_subsets.get(k, None)
                if d is None:
                    nested_subsets[k] = v
                else:
                    d.update(v)
            else:
                nested_subsets.setdefault(s, None)
        return nested_subsets

    @classmethod
    def get_serialize_pair(
        cls, pobj: PObjType, pname: str, nested_subsets: NestedSubsetType = None
    ) -> Tuple[Any, Any]:
        p = pobj.param[pname]
        value = pobj.param.get_value_generator(pname)
        value = p.serialize(value)
        doc = pobj.param[pname].doc
        doc = doc if not doc else textwrap.dedent(doc).replace("\n", " ").strip()
        return value, doc

    @classmethod
    def get_deserialize_value(
        cls,
        pobj: PObjType,
        pname: str,
        value: Any,
        nested_subsets: NestedSubsetType = None,
    ) -> Any:
        return pobj.param[pname].deserialize(value)

    @classmethod
    def get_serialize_dict(
        cls, pobj: PObjType, nested_subsets: NestedSubsetType = None
    ) -> Tuple[Dict[str, Any], Dict[str, Optional[str]]]:
        dict_, help = dict(), dict()
        for pname in pobj.param.objects("existing"):
            if nested_subsets is not None and pname not in nested_subsets:
                continue
            value, doc = cls.get_serialize_pair(
                pobj,
                pname,
                nested_subsets if nested_subsets is None else nested_subsets[pname],
            )
            dict_[pname] = value
            help[pname] = doc
        return dict_, help

    @classmethod
    def serialize_parameters(
        cls, pobj: PObjType, subset: Optional[Collection[str]] = None
    ) -> str:
        return cls.dumps(*cls.get_serialize_dict(pobj, cls.nest_subsets(subset)))

    @classmethod
    def get_deserialize_dict(
        cls,
        pobj: PObjType,
        deserialized: Dict[str, Any],
        nested_subsets: NestedSubsetType = None,
    ) -> Dict[str, Any]:
        components = dict()
        for pname, value in deserialized.items():
            if nested_subsets is not None and pname not in nested_subsets:
                continue
            components[pname] = cls.get_deserialize_value(
                pobj,
                pname,
                value,
                nested_subsets if nested_subsets is None else nested_subsets[pname],
            )
        return components

    @classmethod
    def deserialize_parameters(
        cls,
        pobj: PObjType,
        serialization: str,
        subset: Optional[Collection[str]] = None,
    ) -> Dict[str, Any]:
        return cls.get_deserialize_dict(
            pobj, cls.loads(serialization), cls.nest_subsets(subset)
        )

    @classmethod
    def serialize_parameter_value(cls, pobj: PObjType, pname: str) -> str:
        return cls.dumps(*cls.get_serialize_pair(pobj, pname))

    @classmethod
    def deserialize_parameter_value(cls, pobj: PObjType, pname: str, value: str) -> Any:
        return cls.get_deserialize_value(pobj, pname, cls.loads(value))


class JsonSerialization(SerializableSerialization, JsonSerializable):
    pass


class YamlSerialization(SerializableSerialization, YamlSerializable):
    """YAML (de)serialization
    
    See Also
    --------
    register_serializer
        For how this is used
    """


class RecklessSerializableSerialization(SerializableSerialization):
    """ABC for reckless serialization"""

    @classmethod
    def get_serialize_pair(
        cls, pobj: PObjType, pname: str, nested_subsets: NestedSubsetType = None
    ) -> Tuple[Any, Any]:
        p = pobj.param[pname]
        value = pobj.param.get_value_generator(pname)
        value = p.serialize(value)
        if isinstance(value, param.Parameterized):
            value, doc = cls.get_serialize_dict(value, nested_subsets)
        else:
            doc = pobj.param[pname].doc
            doc = doc if not doc else textwrap.dedent(doc).replace("\n", " ").strip()
        return value, doc

    @classmethod
    def get_deserialize_value(
        cls,
        pobj: PObjType,
        pname: str,
        value: Any,
        nested_subsets: NestedSubsetType = None,
    ) -> Any:
        pobjp = pobj.param[pname]
        value = pobj.param[pname].deserialize(value)
        class_ = getattr(pobjp, "class_", None)
        if (
            class_ is not None
            and value is not None
            and getattr(pobjp, "is_instance", False)
            and issubclass(class_, param.Parameterized)
        ):
            value = class_(**cls.get_deserialize_dict(class_, value, nested_subsets))
        return value


class RecklessJsonSerialization(RecklessSerializableSerialization, JsonSerializable):
    """Reckless JSON (de)serialization
    
    See Also
    --------
    register_serializer
        For how this is used
    """

    pass


class RecklessYamlSerialization(RecklessSerializableSerialization, YamlSerializable):
    """Reckless YAML (de)serialization
    
    See Also
    --------
    register_serializer
        For how this is used
    """

    pass


_my_serializers = {
    "_json": JsonSerialization,  # don't advertise - for testing purposes
    "yaml": YamlSerialization,
    "reckless_json": RecklessJsonSerialization,
    "reckless_yaml": RecklessYamlSerialization,
}


def register_serializer(mode: Literal["reckless_json", "reckless_yaml", "yaml"]):
    """Add a custom (de)serialization protocol to parameterized instances

    The serialization protocol to be registered is passed as `mode`, which can be
    one of

    1. :obj:`'reckless_json'`, which is identical to the standard :obj:`'json'`
       serializer but for some simplifying assumptions to handle
       [nesting](https://param.holoviz.org/user_guide/Serialization_and_Persistence.html#json-limitations-and-workarounds).
       See the below note for more information.
    2. :obj:`'yaml'`, which follows a similar parsing strategy to vanilla :obj:`'json'`
       but (de)serializes in YAML format instead. Requires either :mod:`yaml` or
       :mod:`ruamel.yaml` to be installed or will raise an import error at the
       first request.
    3. :obj:`'reckless_yaml'`, which makes the same reckless assumptions as
       :obj:`reckless_json'` but (de)serialized in the YAML format.

    After calling this function, parameters can be serialized with the same `mode`
    registered via :func:`param.Parameterized.param.serialize_parameters`:
    
    >>> str_ = p.param.serialize_parameters(subset, mode)
    >>> p = P.param.deserialize_parameters(str_, subset, mode)

    Warnings
    --------
    Functionality is in beta and subject to additions and modifications.

    Notes
    -----
    We make strong simplifying assumptions to handle nesting. The usual means of nesting
    :class:`param.Parameterized` instances is

    >>> class Parent(param.Parameterized):
    ...     child = param.ClassSelector(SomeParameterizedClass)
    >>> parent = Parent(child=SomeParameterizedClass(leaf_value=1))

    While the obvious solution is to recursively call (de)serialization on child
    instances, this solution is not suited to all situations. In deserialization, the
    child may be of type `SomeParameterizedClass`, but may also be one of its
    subclasses. If children are sharing references to the same instance, that
    information will be lost in serialization.
    
    For now (keep track of [this bug](https://github.com/holoviz/param/issues/520) for
    changes), ``mode="json"`` will throw if it sees a nested parameterized instance in
    serialization or deserialization. Reckless serialization is performed recursively
    with no consideration for references. Deserialization is performed by recursing on
    the class provided to the class selector (i.e. `SomeParameterizedClass`), not any of
    its subclasses.

    To (de)serialize only a subset of parameters in a child instance, delimit child
    parameters with ``<name_in_parent>.<name_in_child>`` in the `subset` argument. In
    the example above, we can serialize only `leaf_value` using

    >>> parent.param.serialize_parameters({'child.leaf_value'}, mode="reckless_json")

    See Also
    --------
    unregister_serializer
    """
    # avoids the case where the user mistakenly treats a standard serializer (e.g. json)
    # as something to be registered
    if mode in param.Parameter._serializers:
        return
    param.Parameter._serializers[mode] = _my_serializers[mode]


def unregister_serializer(mode: Literal["reckless_json", "reckless_yaml", "yaml"]):
    """Unregister a previously registered custom serializer
    
    See Also
    --------
    register_serializer
    """
    if mode in param.Parameter._serializers and (
        param.Parameter._serializers[mode] is _my_serializers[mode]
    ):
        param.Parameter._serializers.pop(mode)


try:
    Action = argparse.Action[param.Parameterized]
except:
    Action = argparse.Action


class DeserializationAction(Action):
    """Action to deserialize a parameterized object from file

    Given some subclass of :class:`param.Parameterized`, `MyParameterized`, the action
    can be added by calling, e.g.

    >>> parser.add_argument(
    ...     '--param', type=MyParameterized, action=DeserializationAction)

    In this example, the argument passed with the flag :obj:`--param` is treated as a
    path to a JSON file from which a serialized copy of `MyParameterized` is read and
    instantiatied.
    
    Deserialization is performed with the
    :func:`param.Parameterized.param.deserialize_parameters`. The deserialization `mode`
    and optionally the `subset` of parameters deserialized can be changed by passing the
    `const` keyword argument to :func:`add_argument`. `const` can be either a string
    (just the `mode`) or a tuple of a string (`mode`) and set of strings (`subset`).

    See Also
    --------
    ParameterizedFileReadAction
        Same intent, but using :mod:`pydrobert.param` custom deserialization routines.
    register_serializer
        To enable custom parsing modes.
    """

    class_: Type[param.Parameterized]

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Union[str, int, None] = None,
        const: Union[str, Tuple[str, Optional[Collection[str]]]] = "json",
        default: Any = None,
        type: Type[param.Parameterized] = param.Parameterized,
        choices=None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Union[str, Tuple[str, ...], None] = None,
    ) -> None:
        if not issubclass(type, param.Parameterized):
            raise ValueError("type is not a subclass of param.Parameterized")
        self.class_ = type
        if isinstance(const, str):
            const = const, None
        else:
            const = const[0], (None if const[1] is None else set(const[1]))
        super().__init__(
            option_strings,
            dest,
            nargs,
            const,
            default,
            argparse.FileType("r"),
            choices,
            required,
            help,
            metavar,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[TextIO, List[TextIO]],
        option_string: Union[str, None] = None,
    ) -> None:
        if values is self.const:
            values = []
        values_ = list(values) if isinstance(values, list) else [values]
        mode, subset = self.const
        for i in range(len(values_)):
            value = values_[i]
            name = value.name
            value = value.read()
            try:
                value = self.class_(
                    **self.class_.param.deserialize_parameters(value, subset, mode)
                )
            except Exception as e:
                msg = f": {e.msg}" if hasattr(e, "msg") else ""
                raise argparse.ArgumentError(
                    self, f"error deserializing '{name}' as {mode}{msg}"
                )
            values_[i] = value
        if isinstance(values, list):
            values = values_
        else:
            values = values_[0]
        setattr(namespace, self.dest, values)


class SerializationAction(Action):
    """Action to serialize a parameterized object and then exit

    The counterpart to :class:`DeserializationAction`, adding this action as an
    argument to an :class:`argparse.ArgumentParser` as such

    >>> parser.add_argument(
    ...     '--print', type=MyParameterized, action=SerializationAction)

    will, by default, serialize a new `MyParameterized` instance as JSON and print it to
    stdout if ``'--print'`` is parsed without an argument. Afterwards, the command will
    terminate. If ``'--print'`` is passed a path, the JSON will be printed there
    instead.

    Serialization is performed with
    :func:`param.Parameterized.param.serialize_parameters`. The serialization `mode` and
    optionally the `subset` of parameters serialized can be changed by passing the
    `const` keyword argument to :func:`add_argument`. `const` can be either a string
    (just the `mode`) or a tuple of a string (`mode`) and set of strings (`subset`).
    
    The `type` argument can be either a subclass of :class:`param.Parameterized` or an
    instance of one. In the latter case, the parameter values of that instance will be
    serialized instead.

    See Also
    --------
    ParameterizedFilePrintAction
        Same intent, but using :mod:`pydrobert.param` custom serialization routines.
    register_serializer
        To enable custom parsing modes.
    """

    pobj: PObjType

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Union[str, int, None] = "?",
        const: Union[str, Tuple[str, Optional[Collection[str]]]] = "json",
        default: TextIO = argparse.FileType("w")("-"),
        type: PObjType = param.Parameterized,
        choices=None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Union[str, Tuple[str, ...], None] = None,
    ) -> None:
        if not isinstance(type, param.Parameterized) and not issubclass(
            type, param.Parameterized
        ):
            raise ValueError(
                "type is neither an instance nor a subclass of param.Parameterized"
            )
        self.pobj = type
        if isinstance(const, str):
            const = const, None
        else:
            const = const[0], (None if const[1] is None else set(const[1]))
        super().__init__(
            option_strings,
            dest,
            nargs,
            const,
            default,
            argparse.FileType("w"),
            choices,
            required,
            help,
            metavar,
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[TextIO, List[TextIO]],
        option_string: Union[str, None] = None,
    ) -> None:
        if values is self.const:
            values = []  # nargs = '?'
        if not isinstance(values, list):
            values = [values]
        if not len(values):
            values.append(self.default)
        mode, subset = self.const
        try:
            txt = self.pobj.param.serialize_parameters(subset, mode)
        except Exception as e:
            msg = f": {e.msg}" if hasattr(e, "msg") else ""
            raise argparse.ArgumentError(
                self, f"error serializing parameterized '{self.pobj}'{msg}"
            )
        for value in values:
            value.write(txt)
        sys.exit(0)


def add_deserialization_group_to_parser(
    parser: argparse.ArgumentParser,
    pobj: PObjType,
    dest: str,
    file_formats: Union[
        Literal["json", "yaml"], Collection[Literal["json", "yaml"]], None
    ] = None,
    subset: Optional[Collection[str]] = None,
    reckless: bool = False,
    flag_format_str: Union[str, Sequence[str]] = "--read-{file_format}",
    help_format_str: Optional[str] = (
        "Path to {file_format} file (or '-' for stdin) from which to read in "
        "{dest} parameters"
    ),
    required: bool = False,
    register_missing: bool = True,
):
    """Add flags to parser for deserializing parameterized objects from file
    
    A convenience function for coordinating :class:`DeserializationAction` arguments
    over multiple file formats. The usual case might look like

    >>> add_deserialization_group_to_parser(parser, MyParameterized, 'param')
    >>> namespace = parser.parse_args()
    >>> namespace.param  # stores the MyParameterized instance or None

    Here it adds mutually exclusive flags to deserialize a `MyParameterized` instance
    using serialization protocols for the available file formats.

    Parameters
    ----------
    parser
    pobj
        Either a subclass of :class:`param.Parameterized` or an instance of one.
        Determines the type of parameterized object to deserialize. If `pobj` is a
        :class:`type`, the default value for the parameters in the namespace will be
        :obj:`None`. Otherwise (when `pobj` is an instance), `pobj` will be the default
        value.
    dest
        The name of the attribute in `namespace` to store the deserialized instance
        under.
    file_formats
        If specified, one or a list of file formats to add flags for. If unspecified,
        flags for every available file format will be added. Availability means both
        the correct backend is installed to parse the file and, if `register_missing`
        is :obj:`False`, that the corresponding mode has already been registered. The
        :obj:`'json'` format is always available.
    subset
        If specified, only the parameters with names in this set will be deserialized.
    reckless
        Whether to allow simplifying assumptions to make parsing easier.
    flag_format_str
        One or more Python format strings which, after formatting, will act as the flags
        for the argument. The following keys are available for formatting:
        
        - `file_format`, an entry in `file_formats`
        - `dest`
        - `pobj_name`, either :obj:`pobj.name` if `pobj` is an instance or
          :obj:`pobj.__name__` if `pobj` is a class.
    help_format_str
        A python format string which, after formatting, describes the flags. The same
        keys are available as those to `flag_format_str`.
    required
        Whether to require the user to specify one flag.
    register_missing
        Whether to register any custom modes corresponding to the `file_formats` (and
        `reckless`) which have yet to be registered via :func:`register_serializer`.
        Setting to :obj:`False` will restrict the dynamically chosen value of
        `file_formats`. If `file_formats` is manually specified, the parser will throw
        when it tries to deserialize using an unspecified mode.
    
    Returns
    -------
    grp
        The mutually exclusive group which the flags have beed added to

    Warnings
    --------
    Functionality is in beta and subject to additions and modifications.
    
    See Also
    --------
    add_parameterized_read_group
        An analogous function using custom deserialization routines.
    pydrobert.param.register_serializer
        More information on the file formats and modes of serialization.
    """
    if isinstance(flag_format_str, str):
        flag_format_str = (flag_format_str,)
    elif not len(flag_format_str):
        raise ValueError("Must specify at least one string in flag_format_str")
    if isinstance(pobj, type):
        default, pobj_name = None, pobj.__name__
    else:
        default, pobj_name = pobj, pobj.name
    if reckless:
        fmt2mode = {"json": "reckless_json", "yaml": "reckless_yaml"}
        mode2fmt = {"reckless_json": "json", "reckless_yaml": "yaml"}
    else:
        fmt2mode = mode2fmt = {"json": "json", "yaml": "yaml"}
    if file_formats is None:
        file_formats = set(fmt2mode)
        if not register_missing:
            file_formats &= {mode2fmt[s] for s in param.Parameter._serializers}
        if "yaml" in file_formats and not yaml_is_available():
            file_formats.remove("yaml")
    else:
        file_formats = set(file_formats)
        missing_formats = file_formats - set(fmt2mode)
        if missing_formats:
            raise ValueError(f"No serialization known for: {missing_formats}")

    grp = parser.add_mutually_exclusive_group(required=required)
    grp.set_defaults(**{dest: default})
    for file_format in file_formats:
        mode = fmt2mode[file_format]
        if register_missing:
            register_serializer(mode)
        const = (mode, subset)
        flag_str = (
            f.format(file_format=file_format, dest=dest, pobj_name=pobj_name)
            for f in flag_format_str
        )
        if help_format_str is None:
            help_str = None
        else:
            help_str = help_format_str.format(
                file_format=file_format, dest=dest, pobj_name=pobj_name
            )
        grp.add_argument(
            *flag_str,
            dest=dest,
            action=DeserializationAction,
            metavar=file_format.upper(),
            const=const,
            help=help_str,
        )

    return grp

