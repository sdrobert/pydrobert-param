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

import argparse
from typing import (
    Any,
    Collection,
    List,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import param

from param.serializer import JSONSerialization


class RecklessJsonSerialization(JSONSerialization):
    """JSON serializer which makes reckless assumptions

    See Also
    --------
    register_reckless_json
        How to use this.
    """

    @classmethod
    def split_subset(cls, subset):
        nested_subsets = dict()
        if subset is not None:
            subset_ = set()
            for s in subset:
                if "." in s:
                    k, v = s.split(".", maxsplit=1)
                    nested_subsets.setdefault(k, set()).add(v)
                    subset_.add(k)
                else:
                    subset_.add(s)
            subset = subset_
        return subset, nested_subsets

    @classmethod
    def serialize_parameters(cls, pobj, subset=None):
        subset, nested_subsets = cls.split_subset(subset)
        components = {}
        for name, p in pobj.param.objects("existing").items():
            if subset is not None and name not in subset:
                continue
            value = pobj.param.get_value_generator(name)
            value = p.serialize(value)
            if isinstance(value, param.Parameterized):
                value = cls.loads(
                    value.param.serialize_parameters(
                        nested_subsets.get(name, None), "reckless_json"
                    )
                )
            components[name] = value
        return cls.dumps(components)

    @classmethod
    def deserialize_parameters(cls, pobj, serialization, subset=None):
        subset, nested_subsets = cls.split_subset(subset)
        deserialized = cls.loads(serialization)
        components = {}
        for name, value in deserialized.items():
            if subset is not None and name not in subset:
                continue
            pobjp = pobj.param[name]
            value = pobjp.deserialize(value)
            class_ = getattr(pobjp, "class_", None)
            if (
                class_ is not None
                and value is not None
                and getattr(pobjp, "is_instance", False)
                and issubclass(class_, param.Parameterized)
            ):
                value = class_(
                    **cls.deserialize_parameters(
                        class_, cls.dumps(value), nested_subsets.get(name, None)
                    )
                )
            components[name] = value
        return components


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
    param.Parameter._serializers.setdefault(
        "reckless_json", RecklessJsonSerialization()
    )


def unregister_reckless_json():
    """Remove reckless JSON (de)serialization from parameters
    
    See Also
    --------
    register_reckless_json
    """
    if "reckless_json" in param.Parameter._serializers and isinstance(
        param.Parameter._serializers["reckless_json"], RecklessJsonSerialization
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

