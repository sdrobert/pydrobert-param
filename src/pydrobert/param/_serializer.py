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
    TypeVar,
    Union,
)

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol

import param

from param.serializer import Serialization


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


PObjType = Union[param.Parameterized, Type[param.Parameterized]]
NestedSubsetType = Optional[Dict[str, "NestedSubsetType"]]


class SerializableSerialization(Serialization, Serializable):
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


class RecklessSerializableSerialization(SerializableSerialization):
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
    pass


def register_reckless_json():
    """Add reckless JSON (de)serialization to parameters
    
    Similar to [regular JSON
    serialization](https://param.holoviz.org/user_guide/Serialization_and_Persistence.html)
    but makes simplifying assumptions to deal with [its
    limitations](https://param.holoviz.org/user_guide/Serialization_and_Persistence.html#json-limitations-and-workarounds).
    See the notes below for the specific assumptions.

    After calling this function, parameters can be serialized according to these
    assumptions by calling

    >>> json_ = p.param.serialize_parameters(mode="reckless_json")

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
    instances, this solution is ambiguous. In deserialization, the child may be of type
    `SomeParameterizedClass`, but may also be one of its subclasses. If children are
    sharing references to the same instance, that information will be lost.
    
    For now (keep track of [this bug](https://github.com/holoviz/param/issues/520) for
    changes), ``mode="json"`` will throw if it sees a nested parameterized instance in
    serialization or deserialization. Under ``mode="reckless_json"``, serialization is
    performed recursively with no consideration for references. Deserialization is
    performed by recursing on the class provided to the class selector (i.e.
    `SomeParameterizedClass`), not any of its subclasses.

    To (de)serialize only a subset of parameters in a child instance, delimit child
    parameters with ``<name_in_parent>.<name_in_child>`` in the `subset` argument. In
    the example above, we can serialize only `leaf_value` using

    >>> parent.param.serialize_parameters({'child.leaf_value'}, mode="reckless_json")

    See Also
    --------
    unregister_reckless_json
    """
    param.Parameter._serializers.setdefault("reckless_json", RecklessJsonSerialization)


def unregister_reckless_json():
    """Remove reckless JSON (de)serialization from parameters
    
    See Also
    --------
    register_reckless_json
    """
    if "reckless_json" in param.Parameter._serializers and (
        param.Parameter._serializers["reckless_json"] is RecklessJsonSerialization
    ):
        param.Parameter._serializers.pop("reckless_json")


P = TypeVar("P", bound=param.Parameterized)

try:
    Action = argparse.Action[P]
except:
    Action = argparse.Action


class DeserializationAction(Action):
    """Action to deserialize a parameterized object from file

    Given some subclass of :class:`param.Parameterized`, `MyParameterized`, the action
    can be added by calling, e.g.

    >>> parser.add_argument('--param', type=MyParameterized)

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
    register_reckless_json
        To enable :obj:`'reckless_json'` mode for more flexible JSON parsing.
    """

    class_: Type[P]

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Union[str, int, None] = None,
        const: Union[str, Tuple[str, Optional[Collection[str]]]] = "json",
        default: Any = None,
        type: Type[P] = param.Parameterized,
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
        if values is None and issubclass(type(self.default), type):
            values = self.default()
        if not isinstance(values, list):
            values_ = [values]
        else:
            values_ = list(values)
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
                msg = f": {e.msg}" if hasattr(e, msg) else ""
                raise argparse.ArgumentError(
                    self, f"error deserializing '{name}' as {mode}{msg}"
                )
            values_[i] = value
        if isinstance(values, list):
            values = values_
        else:
            values = values_[0]
        setattr(namespace, self.dest, values)

