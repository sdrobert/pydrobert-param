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

import abc
import json
import configparser

from collections import OrderedDict
from io import StringIO
from typing import Any, Collection, List, Optional, Sequence, TextIO, Union

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

import param

from ._file_serialization import (
    serialize_from_obj_to_json,
    serialize_from_obj_to_yaml,
    deserialize_from_json_to_obj,
    deserialize_from_yaml_to_obj,
)

try:
    import numpy as np

    def _equal_array(a, b):
        try:
            a = np.array(a, copy=False)
            b = np.array(b, copy=False)
            return a.size() == b.size() and np.allclose(a, b)
        except Exception:
            return 0


except ImportError:

    def _equal_array(a, b):
        try:
            return all(c == d for c, d in zip(a, b))
        except Exception:
            return 0


def _equal(a, b):
    r = _equal_array(a, b)
    if r == 0:
        r = a == b
    return r


class ParamConfigTypeError(TypeError):
    """Raised when failed to (de)serialize Parameterized object"""

    def __init__(self, parameterized, name, message=""):
        super(ParamConfigTypeError, self).__init__(
            "{}.{}: {}".format(parameterized.name, name, message)
        )


class ParamConfigSerializer(object, metaclass=abc.ABCMeta):
    """Serialize a parameter value from a Parameterized object

    Subclasses of :class:`ParamConfigSerializer` are expected to implement
    :func:`serialize`. Instances of the subclass can be passed into
    :func:`serialize_to_dict`. The goal of a serializer is to convert a parameter value
    from a :class:`param.parameterized.Parameterized` object into something that can be
    handled by a dict-like data store. The format of the outgoing data should reflect
    where the dict-like data are going. For example, a JSON serializer can handle lists,
    but not an INI serializer. In :mod:`pydrobert.param.serialization`, there are a
    number of default serializers (matching the pattern ``Default*Serializer``) that are
    best guesses on how to serialize data from a variety of sources
    """

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        """A string that helps explain this serialization

        The return string will be included in the second element of the pair returned by
        :func:`serialize_to_dict`. Helps explain the serialized value to the user.
        """
        return None

    @abc.abstractmethod
    def serialize(self, name: str, parameterized: param.Parameterized) -> Any:
        """Serialize data from a parameterized object and return it

        Parameters
        ----------
        name
            The name of the parameter in `parameterized` to retrieve the value from
        parameterized
            The parameterized instance containing a parameter with the name `name`

        Returns
        -------
        val : obj
            The serialized value of the parameter

        Raises
        ------
        ParamConfigTypeError
            If serialization could not be performed
        """
        raise NotImplementedError()


class DefaultSerializer(ParamConfigSerializer):
    """Default catch-all serializer. Returns value verbatim"""

    def serialize(self, name: str, parameterized: param.Parameterized) -> Any:
        return getattr(parameterized, name)


class DefaultArraySerializer(ParamConfigSerializer):
    """Default numpy array serializer

    The process:
    1. If :obj:`None`, return
    2. Call value's ``tolist()`` method
    """

    def serialize(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[list]:
        val = getattr(parameterized, name)
        if val is None:
            return val
        return val.tolist()


def _get_name_from_param_range(name: str, parameterized: param.Parameterized, val):
    p = parameterized.param.params()[name]
    val_type = type(val)
    for n, v in list(p.get_range().items()):
        if isinstance(v, val_type) and _equal(v, val):
            return n
    parameterized.param.warning(
        "Could not find value of {} in get_range(), so serializing value "
        "directly".format(name)
    )
    return val


class DefaultClassSelectorSerializer(ParamConfigSerializer):
    """Default ClassSelector serializer

    The process:

    1. If :obj:`None`, return
    2. If parameter's ``is_instance`` attribute is :obj:`True`, return value verbatim
    3. Search for the corresponding name in the selector's
       :func:`param.ClassSelector.get_range` dictionary and return that name, if
       possible
    4. Return the value
    """

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        p = parameterized.param.params()[name]
        hashes = tuple(p.get_range())
        if p.is_instance and len(hashes):
            s = "Choices: "
            s += ", ".join(('"' + x + '"' for x in hashes))
            return s
        else:
            return None

    def serialize(self, name: str, parameterized: param.Parameterized) -> Any:
        val = getattr(parameterized, name)
        p = parameterized.param.params()[name]
        if val is None or p.is_instance:
            return val
        else:
            return _get_name_from_param_range(name, parameterized, val)


class DefaultDataFrameSerializer(ParamConfigSerializer):
    """Default pandas.DataFrame serializer

    The process:

    1. If :obj:`None`, return
    2. Call ``tolist()`` on the ``values`` property of the parameter's value and return
    """

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        val = getattr(parameterized, name)
        if val is not None:
            return "DataFrame axes: {}".format(val.axes)
        else:
            return None

    def serialize(self, name: str, parameterized: param.Parameterized) -> list:
        val = getattr(parameterized, name)
        if val is None:
            return None
        return val.values.tolist()


def _datetime_to_formatted(parameterized, name, dt, formats):
    if isinstance(formats, str):
        formats = (formats,)
    s = None
    try:
        for format in formats:
            s = dt.strftime(format)
            dt2 = dt.strptime(s, format)
            if dt == dt2:
                return s, format
    except ValueError as e:
        raise ParamConfigTypeError(parameterized, name) from e
    parameterized.warning(
        "Loss of info for datetime {} in serialized format string".format(dt, s)
    )
    return s, format


def _timestamp(dt):
    import datetime

    if dt.tzinfo:
        zero = datetime.timedelta(0)

        class _UTC(datetime.tzinfo):
            def utcoffset(self, dt):
                return zero

            def tzname(self, dt):
                return "UTC"

            def dst(self, dt):
                return zero

        utc = _UTC()
        return (dt - datetime.datetime(1970, 1, 1, tzinfo=utc)).total_seconds()
    else:
        return (dt - datetime.datetime(1970, 1, 1)).total_seconds()


class DefaultDateSerializer(ParamConfigSerializer):
    """Default datetime.datetime serializer

    The process:

    1. If :obj:`None`, return
    2. If a :class:`datetime.datetime` instance

       1. If the `format` keyword argument of the serializer is not :obj:`None`:

          1. If `format` is a string, return the result of the value's
             ``strftime(format)`` call
          2. If `format` is list-like, iterate through it, formatting with
             ``strftime(element)``. Whichever string which, when deserialized with
             ``strptime(element)``, produces an equivalent :class`datetime.datetime`
             object as the value is returned. If no such string exists, the last string
             is returned.

       2. Return the result of the value's ``timestamp()`` call

    3. If a :class:`numpy.datetime64` instance, return the value cast to a string
    """

    def __init__(
        self,
        format: Optional[Sequence[str]] = (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ),
    ):
        super(DefaultDateSerializer, self).__init__()
        self.format = format

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        val = getattr(parameterized, name)
        if val is None:
            return val
        from datetime import datetime

        if isinstance(val, datetime):
            if self.format is None:
                return "Timestamp"
            else:
                return (
                    "Date format string: "
                    + _datetime_to_formatted(parameterized, name, val, self.format)[1]
                )
        else:
            return "ISO 8601 format string"

    def serialize(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[Union[float, str]]:
        val = getattr(parameterized, name)
        if val is None:
            return val
        from datetime import datetime

        if isinstance(val, datetime):
            if self.format is None:
                return _timestamp(val)
            else:
                val = _datetime_to_formatted(parameterized, name, val, self.format)[0]
        return str(val)


class DefaultDateRangeSerializer(ParamConfigSerializer):
    """Default date range serializer

    Similar to serializing a single :class:`datetime.datetime`, but applied to each
    element separately. Also cast to a list
    """

    def __init__(
        self,
        format: Optional[Sequence[str]] = (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ),
    ):
        super(DefaultDateRangeSerializer, self).__init__()
        self.format = format

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        val = getattr(parameterized, name)
        if val is None:
            return val
        val = val[0]  # assuming they're of the same granularity
        from datetime import datetime

        if isinstance(val, datetime):
            if self.format is None:
                return "Timestamp"
            else:
                return (
                    "Date format string: "
                    + _datetime_to_formatted(parameterized, name, val, self.format)[1]
                )
        else:
            return "ISO 8601 format string"

    def serialize(
        self, name: str, parameterized: param.Parameterized
    ) -> List[Union[float, str]]:
        vals = getattr(parameterized, name)
        if vals is None:
            return vals
        from datetime import datetime

        ret = []
        for val in vals:
            if isinstance(val, datetime):
                if self.format is None:
                    val = _timestamp(val)
                else:
                    val = _datetime_to_formatted(parameterized, name, val, self.format)[
                        0
                    ]
            else:
                val = str(val)
            ret.append(val)
        return ret


class DefaultListSelectorSerializer(ParamConfigSerializer):
    """Default ListSelector serializer

    For each element in the value:

    1. Search for its name in the selector's :func:`param.ListSelector.get_range` dict
       and swap if for the name, if possible
    2. Otherwise, use that element verbatim
    """

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        p = parameterized.param.params()[name]
        hashes = tuple(p.get_range())
        if len(hashes):
            s = "Element choices: "
            s += ", ".join(('"' + x + '"' for x in hashes))
            return s
        else:
            return None

    def serialize(self, name: str, parameterized: param.Parameterized) -> list:
        return [
            _get_name_from_param_range(name, parameterized, x)
            for x in getattr(parameterized, name)
        ]


class DefaultObjectSelectorSerializer(ParamConfigSerializer):
    """Default ObjectSelector serializer

    The process:

    1. If :obj:`None`, return
    2. Search for the name of the value in the selector's
       :func:`param.ObjectSelector.get_range` dictionary and return, if possible
    3. Return value verbatim
    """

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        p = parameterized.param.params()[name]
        hashes = tuple(p.get_range())
        if len(hashes):
            s = "Choices: "
            s += ", ".join(('"' + x + '"' for x in hashes))
            return s
        else:
            return None

    def serialize(self, name: str, parameterized: param.Parameterized) -> Any:
        val = getattr(parameterized, name)
        if val is None:
            return val
        return _get_name_from_param_range(name, parameterized, val)


class DefaultSeriesSerializer(ParamConfigSerializer):
    """Default pandas.Series serializer

    The process:

    1. If :obj:`None`, return
    2. Call ``tolist()`` on the ``values`` property of the parameter's value and return
    """

    def help_string(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[str]:
        val = getattr(parameterized, name)
        if val is not None:
            return "Series axes: {}".format(val.axes)
        return None

    def serialize(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[list]:
        val = getattr(parameterized, name)
        if val is None:
            return
        return val.values.tolist()


class DefaultTupleSerializer(ParamConfigSerializer):
    """Default tuple serializer

    The process:
    1. If :obj:`None`, return
    2. Casts the value to a :class:`list`
    """

    def serialize(
        self, name: str, parameterized: param.Parameterized
    ) -> Optional[list]:
        val = getattr(parameterized, name)
        return val if val is None else list(val)


def _to_json_string_serializer(cls, typename):
    class _JsonStringSerializer(cls):
        """Converts a {} to a JSON string

        The default serializer used in INI files. This:

        1. Follows the process of :class:`{}`
        2. If the resulting value is :obj:`None`, return that
        3. Otherwise, converts it to a string of JSON

        See Also
        --------
        serialize_to_json
            To serialize an entire :class:`param.parameterized.Parameterized` instance
            as json
        """.format(
            typename, cls.__name__
        )

        def help_string(self, name: str, parameterized: param.Parameterized) -> str:
            s = super(_JsonStringSerializer, self).help_string(name, parameterized)
            if s is None:
                return "A JSON object"
            else:
                return "A JSON object. " + s

        def serialize(self, name: str, parameterized: param.Parameterized) -> Any:
            val = super(_JsonStringSerializer, self).serialize(name, parameterized)
            if val is None:
                return val
            try:
                return json.dumps(val)
            except (TypeError, ValueError) as e:
                raise ParamConfigTypeError(parameterized, name) from e

    return _JsonStringSerializer


JsonStringArraySerializer = _to_json_string_serializer(
    DefaultArraySerializer, "param.Array"
)

JsonStringDataFrameSerializer = _to_json_string_serializer(
    DefaultDataFrameSerializer, "param.DataFrame"
)

JsonStringDateRangeSerializer = _to_json_string_serializer(
    DefaultDateRangeSerializer, "param.DateRange"
)

JsonStringDictSerializer = _to_json_string_serializer(DefaultSerializer, "dict")

JsonStringListSerializer = _to_json_string_serializer(DefaultSerializer, "list")

JsonStringListSelectorSerializer = _to_json_string_serializer(
    DefaultListSelectorSerializer, "param.ListSelector"
)

JsonStringSeriesSerializer = _to_json_string_serializer(
    DefaultSeriesSerializer, "param.Series"
)

JsonStringTupleSerializer = _to_json_string_serializer(DefaultTupleSerializer, "tuple")

DEFAULT_SERIALIZER_DICT = {
    param.Array: DefaultArraySerializer(),
    param.ClassSelector: DefaultClassSelectorSerializer(),
    param.DataFrame: DefaultDataFrameSerializer(),
    param.Date: DefaultDateSerializer(),
    param.DateRange: DefaultDateRangeSerializer(),
    param.ListSelector: DefaultListSelectorSerializer(),
    param.MultiFileSelector: DefaultListSelectorSerializer(),
    param.NumericTuple: DefaultTupleSerializer(),
    param.ObjectSelector: DefaultObjectSelectorSerializer(),
    param.Range: DefaultTupleSerializer(),
    param.Series: DefaultSeriesSerializer(),
    param.Tuple: DefaultTupleSerializer(),
    param.XYCoordinates: DefaultTupleSerializer(),
}

DEFAULT_BACKUP_SERIALIZER = DefaultSerializer()


JSON_STRING_SERIALIZER_DICT = {
    param.Array: JsonStringArraySerializer(),
    param.DataFrame: JsonStringDataFrameSerializer(),
    param.DateRange: JsonStringDateRangeSerializer(),
    param.List: JsonStringListSerializer(),
    param.Dict: JsonStringDictSerializer(),
    param.ListSelector: JsonStringListSelectorSerializer(),
    param.MultiFileSelector: JsonStringListSelectorSerializer(),
    param.NumericTuple: JsonStringTupleSerializer(),
    param.Range: JsonStringTupleSerializer(),
    param.Series: JsonStringSeriesSerializer(),
    param.Tuple: JsonStringTupleSerializer(),
    param.XYCoordinates: JsonStringTupleSerializer(),
}


def _serialize_to_dict_flat(
    parameterized, only, serializer_name_dict, serializer_type_dict, on_missing
):
    if serializer_type_dict is not None:
        serializer_type_dict2 = dict(DEFAULT_SERIALIZER_DICT)
        serializer_type_dict2.update(serializer_type_dict)
        serializer_type_dict = serializer_type_dict2
    else:
        serializer_type_dict = DEFAULT_SERIALIZER_DICT
    if serializer_name_dict is None:
        serializer_name_dict = dict()
    if only is None:
        only = set(parameterized.param.params())
        only.remove("name")
    dict_ = dict()
    help_dict = dict()
    for name in only:
        if name not in parameterized.param.params():
            msg = 'No param "{}" to read in "{}"'.format(name, parameterized.name)
            if on_missing == "warn":
                parameterized.warning(msg)
            elif on_missing == "raise":
                raise ValueError(msg)
            continue
        if name in serializer_name_dict:
            serializer = serializer_name_dict[name]
        else:
            type_ = type(parameterized.param.params()[name])
            if type_ in serializer_type_dict:
                serializer = serializer_type_dict[type_]
            else:
                serializer = DEFAULT_BACKUP_SERIALIZER
        dict_[name] = serializer.serialize(name, parameterized)
        help_string_serial = serializer.help_string(name, parameterized)
        help_string_doc = parameterized.param.params()[name].doc
        if help_string_doc:
            if help_string_serial:
                help_string_doc = help_string_doc.strip(". ")
                help_dict[name] = ". ".join((help_string_doc, help_string_serial))
            else:
                help_dict[name] = help_string_doc
        elif help_string_serial:
            help_dict[name] = help_string_serial
    # deterministic output
    dict_ = OrderedDict(sorted((k, v) for (k, v) in list(dict_.items())))
    return dict_, help_dict


def serialize_to_dict(
    parameterized: Union[param.Parameterized, dict],
    only: Optional[Collection[str]] = None,
    serializer_name_dict: Optional[dict] = None,
    serializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "raise",
    include_help: bool = False,
) -> Union[OrderedDict, tuple]:
    """Serialize a parameterized object into a dictionary

    This function serializes data into a dictionary format, suitable for storage in a
    dict-like file format such as YAML or JSON. Each parameter will be serialized into
    the dictionary using a `ParamConfigSerializer` object, matched with the following
    precedent:

    1. If `serializer_name_dict` is specified and contains the parameter
       name as a key, the value will be used.
    2. If `serializer_type_dict` and the type of the parameter in question
       *exactly matches* a key in `serializer_type_dict`, the value of the
       item in `serializer_type_dict` will be used.
    3. If the type of the parameter in question has a ``Default<type>Serializer``, it
       will be used.
    4. :class:`DefaultBackupSerializer` will be used.

    Default serializers are likely appropriate for basic types like strings,
    ints, bools, floats, and numeric tuples. For more complex data types,
    including recursive :class:`param.parameterized.Parameterized` instances, custom
    serializers are recommended.

    It is possible to pass a dictionary as `parameterized` instead of a
    :class:`param.parameterized.Parameterized` instance to this function. This is
    "hierarchical mode". The values of `parameterized` can be
    :class:`param.parameterized.Parameterized` objects or nested dictionaries. The
    returned dictionary will have the same hierarchical dictionary structure as
    `parameterized`, but with the :class:`param.parameterized.Parameterized` values
    replaced with serialized dictionaries. In this case, `only` and
    `serializer_name_dict` are expected to be dictionaries with the same hierarchical
    structure (though they can still be :obj:`None`, which propagates to children),
    whose leaves correspond to the arguments used to serialize the leaves of
    `parameterized`. `serializer_type_dict` can also be hierarchical, can be flat, or be
    some combination.

    Parameters
    ----------
    parameterized
    only
        If specified, only the parameters with their names in this set will be
        serialized into the return dictionary. If unset, all parameters except ``name``
        will be serialized.
    serializer_name_dict
    serializer_type_dict
    on_missing
        What to do if the parameterized instance does not have a parameter listed in
        `only`
    include_help
        If :obj:`True`, the return value will be a pair of dictionaries instead of a
        single dictionary. This dictionary will contain any help strings any serializers
        make available through a call to ``help_string`` (or :obj:`None` if none is
        available).

    Returns
    -------
    collections.OrderedDict or tuple
        A dictionary of serialized parameters or a pair of dictionaries if
        `include_help` was :obj:`True` (the latter is the help dictionary). If
        `parameterized` was an ordered dictionary, the returned serialized dictionary
        will have the same order. Parameters from a
        :class:`param.parameterized.Parameterized` instance are sorted alphabeticallly

    Raises
    ------
    ParamConfigTypeError
        If serialization of a value fails
    """
    dict_ = OrderedDict()
    help_dict = dict()
    p_queue = [parameterized]
    o_queue = [only]
    snd_queue = [serializer_name_dict]
    std_queue = [serializer_type_dict]
    d_queue = [dict_]
    h_queue = [help_dict]
    while len(p_queue):
        p = p_queue.pop(0)
        o = o_queue.pop(0)
        snd = snd_queue.pop(0)
        std = std_queue.pop(0)
        d = d_queue.pop(0)
        h = h_queue.pop(0)
        if isinstance(p, param.Parameterized):
            dp, hp = _serialize_to_dict_flat(p, o, snd, std, on_missing)
            d.update(dp)
            h.update(hp)
        else:
            for name in p:
                p_queue.append(p[name])
                if o is None:
                    o_queue.append(None)
                else:
                    o_queue.append(o.get(name, None))
                if snd is None:
                    snd_queue.append(None)
                else:
                    snd_queue.append(snd.get(name, None))
                if std is None or std.get(name, "a") is None:
                    std_queue.append(None)
                else:
                    std_name = dict(
                        (k, v) for (k, v) in list(std.items()) if isinstance(k, type)
                    )
                    std_name.update(std.get(name, dict()))
                    std_queue.append(std_name)
                d_queue.append(OrderedDict())
                d[name] = d_queue[-1]
                h_queue.append(dict())
                h[name] = h_queue[-1]
    return (dict_, help_dict) if include_help else dict_


def serialize_to_ini(
    file: Union[str, TextIO],
    parameterized: Union[param.Parameterized, dict],
    only: Collection[str] = None,
    serializer_name_dict: Optional[dict] = None,
    serializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "raise",
    include_help: bool = True,
    help_prefix: str = "#",
    one_param_section: Optional[str] = None,
) -> None:
    """Serialize a parameterized instance into an INI (config) file

    `.INI syntax <https://en.wikipedia.org/wiki/INI_file>`__, extended with
    :mod:`configparser`. :mod:`configparser` extends the INI syntax with value
    interpolation. Further, keys missing a value will be interpreted as having the value
    :obj:`None`. This function converts `parameterized` to a dictionary, then fills an
    INI file with the contents of this dictionary.

    INI files are broken up into sections; all key-value pairs must belong to a section.
    If `parameterized` is a :class:`param.parameterized.Parameterized` instance (rather
    than a hierarchical dictionary of them), the action will try to serialize
    `parameterized` into the section specified by the `one_param_section` keyword
    argument. If `parameterized` is a hierarchical dictionary, it can only have depth 1,
    with each leaf being a :class:`param.parameterized.Parameterized` instance. In this
    case, each key corresponds to a section. If an ordered dictionary, sections will be
    written in the same order as they exist in `parameterized`.

    Because the INI syntax does not support standard containers like dicts or lists
    out-of-the-box, this function uses the ``JsonString*Serializer`` to convert
    container values to JSON strings before writing them to the INI file. This solution
    was proposed `here
    <https://stackoverflow.com/questions/335695/lists-in-configparser>`__. Defaults
    ``Default<type>Serializer`` are clobbered with ``Json<type>Serializer``.You can get
    the original defaults back by including them in `serializer_type_dict`.

    Parameters
    ----------
    file
        The INI file to serialize to. Can be a pointer or a path.
    parameterized
    only
    serializer_name_dict
    serializer_type_dict
    on_missing
    include_help
        If :obj:`True`, help documentation will be included at the top of the INI file
        for any parameters and/or serializers that support it
    help_prefix
        The character prefix used at the start of each help line, usually indicating a
        comment
    one_param_section
        If `parameterized` refers to a single :class:`param.parameterized.Parameterized`
        instance, this keyword is used to indicate which section of the INI file
        `parameterized` will be serialized to. If :obj:`None`, the ``name`` attribute of
        the `parameterized` instance will be the used

    See Also
    --------
    serialize_to_dict
    """
    if isinstance(file, str):
        with open(file, "w") as fp:
            return serialize_to_ini(
                fp,
                parameterized,
                only,
                serializer_name_dict,
                serializer_type_dict,
                on_missing,
                include_help,
                help_prefix,
                one_param_section,
            )
    if serializer_type_dict:
        d = JSON_STRING_SERIALIZER_DICT.copy()
        d.update(serializer_type_dict)
        serializer_type_dict = d
    else:
        serializer_type_dict = JSON_STRING_SERIALIZER_DICT
    dict_ = serialize_to_dict(
        parameterized,
        only=only,
        serializer_name_dict=serializer_name_dict,
        serializer_type_dict=serializer_type_dict,
        on_missing=on_missing,
        include_help=include_help,
    )
    if include_help:
        dict_, help_dict = dict_
    else:
        help_dict = dict()
    parser = configparser.ConfigParser(
        comment_prefixes=(help_prefix,), allow_no_value=True
    )
    if isinstance(parameterized, param.Parameterized):
        if one_param_section is None:
            one_param_section = parameterized.name
        parameterized = {one_param_section: parameterized}
        dict_ = {one_param_section: dict_}
        help_dict = {one_param_section: help_dict}
    # use queues to maintain order of parameterized (if OrderedDict)
    p_queue = [parameterized]
    d_queue = [dict_]
    h_queue = [help_dict]
    s_queue = []
    help_string_io = StringIO()
    while len(p_queue):
        p = p_queue.pop()
        d = d_queue.pop()
        h = h_queue.pop()
        if isinstance(p, param.Parameterized):
            assert len(s_queue)
            assert d is not None
            section = s_queue.pop()
            if section != parser.default_section:
                parser.add_section(str(section))
            if h:
                help_string_io.write("{} [{}]\n".format(help_prefix, section))
            for key, val in list(d.items()):
                if val is None:
                    parser.set(str(section), str(key))
                else:
                    parser.set(str(section), str(key), str(val))
                if key in h:
                    help_string_io.write("{} {}: {}\n".format(help_prefix, key, h[key]))
            if h:
                help_string_io.write("\n")
        else:
            if len(s_queue):
                raise IOError(
                    "INI format cannot serialize hierarchical parameterized "
                    "dictionaries greater than depth 1"
                )
            for key in p:
                if key not in d:
                    continue
                p_queue.insert(0, p[key])
                d_queue.insert(0, d[key])
                h_queue.insert(0, h.get(key, dict()))
                s_queue.insert(0, key)
    help_string = help_string_io.getvalue()
    if len(help_string):
        file.write("{} == Help ==\n".format(help_prefix))
        file.write(help_string)
        file.write("\n")
    parser.write(file)


def serialize_to_yaml(
    file_: Union[str, TextIO],
    parameterized: Union[param.Parameterized, dict],
    only: Optional[Collection[str]] = None,
    serializer_name_dict: Optional[dict] = None,
    serializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "raise",
    include_help: bool = True,
) -> None:
    """Serialize a parameterized instance into a YAML file

    Composes :func:`serialize_to_dict` with :func:`serialize_from_obj_to_yaml`.
    """
    dict_ = serialize_to_dict(
        parameterized,
        only=only,
        serializer_name_dict=serializer_name_dict,
        serializer_type_dict=serializer_type_dict,
        on_missing=on_missing,
        include_help=include_help,
    )
    if include_help:
        dict_, help_dict = dict_
    else:
        help_dict = None
    serialize_from_obj_to_yaml(file_, dict_, help_dict)


def serialize_to_json(
    file_: Union[str, TextIO],
    parameterized: Union[param.Parameterized, dict],
    only: Optional[Collection[str]] = None,
    serializer_name_dict: Optional[dict] = None,
    serializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "raise",
    indent: Optional[int] = 2,
) -> None:
    """Serialize a parameterized instance into a JSON file

    Composes :func:`serialize_to_dict` with :func:`serialize_from_obj_to_json`.
    """
    dict_ = serialize_to_dict(
        parameterized,
        only=only,
        serializer_name_dict=serializer_name_dict,
        serializer_type_dict=serializer_type_dict,
        on_missing=on_missing,
        include_help=False,
    )
    serialize_from_obj_to_json(file_, dict_, indent)


class ParamConfigDeserializer(object, metaclass=abc.ABCMeta):
    """Deserialize part of a configuration into a parameterized object

    Subclasses of :class:`ParamConfigDeserializer` are expected to implement
    :func:`deserialize`. Instances of the subclass can be passed into
    :func:`deserialize_from_dict`. The goal of a deserializer is to convert data into
    the value of a parameter in a :class:`param.parameterized.Parameterized` object. The
    format of the incoming data is specific to where the dict-like input came from. For
    example, a JSON parser converts numeric strings to floats, and the contents of
    square braces (``[]``) as lists. In :mod:`pydrobert.param.serialization`, there are
    a number of default deserializers (matching the pattern ``Default*Deserializer``)
    that are best guesses on how to deserialize data from a variety of sources
    """

    @abc.abstractmethod
    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        """Deserialize data and store it in a parameterized object

        Parameters
        ----------
        name
            The name of the parameter in `parameterized` to store the value under
        block
            The data to deserialize into the parameter value
        parameterized
            The parameterized instance containing a parameter with the name `name`. On
            completion of this method, that parameter will be set with the deserialized
            contents of `block`

        Raises
        ------
        ParamConfigTypeError
            If deserialization could not be performed
        """
        raise NotImplementedError()

    @staticmethod
    def check_if_allow_none_and_set(
        name: str, block: Any, parameterized: param.Parameterized
    ) -> bool:
        """Check if block can be made none and set it if allowed

        Many :class:`param.Param` parameters allow :obj:`None` as a value. This is a
        convenience method that deserializers can use to quickly check for a :obj:`None`
        value and set it in that case. This method sets the parameter and returns
        :obj:`True` in the following conditions

        1. The parameter allows :obj:`None` values (the ``allow_None`` attribute is
           :obj:`True`)
        2. `block` is :obj:`None`

        If one of these conditions wasn't met, the parameter remains unset and the
        method returns :obj:`False`.

        In ``Default*Deserializer`` documentation, a call to this method is referred to
        as a "none check".
        """
        p = parameterized.param.params()[name]
        if block is None and p.allow_None:
            parameterized.param.set_param(name, None)
            return True
        else:
            return False


class DefaultDeserializer(ParamConfigDeserializer):
    """Catch-all deserializer

    This serializer performs a none check, then tries to set the parameter with the
    value of `block` verbatim.
    """

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        try:
            parameterized.param.set_param(name, block)
        except ValueError as e:
            raise ParamConfigTypeError(parameterized, name) from e


class DefaultArrayDeserializer(ParamConfigDeserializer):
    """Default deserializer for numpy arrays

    Keyword arguments can be passed to referenced methods by initializing this
    deserializer with those keyword arguments.

    The process:

    1. :obj:`None` check
    2. If already a :class:`numpy.ndarray`, set it
    3. If a string ending with ``'.npy'``, load it as a file path (:func:`numpy.load`
       with kwargs)
    4. If bytes, load it with :func:`numpy.frombuffer` and kwargs
    5. If a string, load it with :func:`numpy.fromstring` and kwargs
    6. Try initializing to array with :func:`numpy.array` and kwargs
    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        super(DefaultArrayDeserializer, self).__init__()

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        import numpy as np

        if isinstance(block, np.ndarray):
            parameterized.param.set_param(name, block)
            return
        if isinstance(block, str) and block.endswith(".npy"):
            try:
                block = np.load(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except (ValueError, IOError) as e:
                raise ParamConfigTypeError(parameterized, name) from e
        elif isinstance(block, bytes):
            try:
                block = np.frombuffer(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise ParamConfigTypeError(parameterized, name) from e
        elif isinstance(block, str):
            try:
                block = np.fromstring(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise ParamConfigTypeError(parameterized, name) from e
        else:
            try:
                block = np.array(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise ParamConfigTypeError(parameterized, name) from e


class DefaultBooleanDeserializer(ParamConfigDeserializer):
    """Default deserializer for booleans

    The process:

    1. :obj:`None` check
    2. If `block` is in :obj:`TRUE_VALUES`, set as :obj:`True`
    3. If `block` is in :obj:`FALSE_VALUES`, set as :obj:`False`
    4. If `block` is already a :class:`bool`, use verbatim
    """

    TRUE_VALUES = {
        "True",
        "true",
        "t",
        "on",
        "TRUE",
        "T",
        "ON",
        "yes",
        "YES",
        1,
        "1",
    }  #:
    FALSE_VALUES = {
        "False",
        "false",
        "f",
        "off",
        "FALSE",
        "F",
        "OFF",
        "no",
        "NO",
        0,
        "0",
    }  #:

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        if block in self.TRUE_VALUES:
            block = True
        elif block in self.FALSE_VALUES:
            block = False
        if isinstance(block, bool):
            parameterized.param.set_param(name, block)
        else:
            raise ParamConfigTypeError(
                parameterized, name, 'cannot convert "{}" to bool'.format(block)
            )


def _find_object_in_object_selector(name, block, parameterized):
    p = parameterized.param.params()[name]
    named_objs = p.get_range()
    for val in list(named_objs.values()):
        if _equal(val, block):
            return val
    try:
        return named_objs[str(block)]
    except Exception:
        pass
    try:
        parameterized.param.set_param(name, block)
    except ValueError as e:
        raise ParamConfigTypeError(parameterized, name) from e


class DefaultClassSelectorDeserializer(ParamConfigDeserializer):
    """Default ClassSelector deserializer

    The process:

    1. :obj:`None` check
    2. If the parameter's ``is_instance`` attribute is :obj:`True`:

       1. If `block` is an instance of the parameter's ``class_`` attribute, set it
       2. Try instantiating the class with `block` as the first argument, with
          additional arguments and keyword arguments passed to the deserializer passed
          allong to the constructor.

    3. Look for the block or the block name in the selector's
       :class:`param.ClassSelector.get_range` dictionary
    """

    def __init__(self, *args, **kwargs):
        super(DefaultClassSelectorDeserializer, self).__init__()
        self.args = args
        self.kwargs = kwargs

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        p = parameterized.param.params()[name]
        try:
            if p.is_instance:
                if not isinstance(block, p.class_):
                    block = p.class_(block, *self.args, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
        except ValueError as e:
            raise ParamConfigTypeError(parameterized, name) from e
        block = _find_object_in_object_selector(name, block, parameterized)
        try:
            parameterized.param.set_param(name, block)
        except ValueError as e:
            raise ParamConfigTypeError(parameterized, name) from e


class DefaultDataFrameDeserializer(ParamConfigDeserializer):
    """Default pandas.DataFrame deserializer

    Keyword arguments and positional arguments can be passed to referenced methods by
    initializing this deserializer with those keyword arguments.

    The process:

    1. :obj:`None` check
    2. If `block` is a data frame, set it
    3. If `block` is a string that ends with one of a number of file suffixes, e.g.
       :obj:`".csv"`, :obj:`".json"`, :obj:`".html"`, :obj:`".xls"`, use the associated
       ``pandas.read_*`` method with `block` as the first argument plus the
       deserializer's extra args and kwargs
    4. If `block` is a string, try :func:`pandas.read_table`
    5. Try initializing a :class:`pandas.DataFrame` with block as the first argument
       plus the deserializer's extra args and kwargs
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        super(DefaultDataFrameDeserializer, self).__init__()

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        import pandas

        if isinstance(block, pandas.DataFrame):
            try:
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise ParamConfigTypeError(parameterized, name) from e
        if isinstance(block, str):
            for suffix, read_func in (
                (".csv", pandas.read_csv),
                (".json", pandas.read_json),
                (".html", pandas.read_html),
                (".xls", pandas.read_excel),
                (".h5", pandas.read_hdf),
                (".feather", pandas.read_feather),
                (".parquet", pandas.read_parquet),
                (".dta", pandas.read_stata),
                (".sas7bdat", pandas.read_sas),
                (".pkl", pandas.read_pickle),
            ):
                if block.endswith(suffix):
                    try:
                        block = read_func(block, *self.args, **self.kwargs)
                        parameterized.param.set_param(name, block)
                        return
                    except Exception as e:
                        raise ParamConfigTypeError(parameterized, name) from e
            try:
                block = pandas.read_table(block, *self.args, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except Exception as e:
                raise ParamConfigTypeError(parameterized, name) from e
        try:
            block = pandas.DataFrame(data=block, **self.kwargs)
            parameterized.param.set_param(name, block)
            return
        except Exception as e:
            raise ParamConfigTypeError(parameterized, name) from e


def _get_datetime_from_formats(block, formats):
    if isinstance(formats, str):
        formats = (formats,)
    from datetime import datetime

    for format in formats:
        try:
            return datetime.strptime(block, format)
        except ValueError:
            pass
    return None


class DefaultDateDeserializer(ParamConfigDeserializer):
    """Default datetime.datetime deserializer

    The process:

    1. :obj:`None` check
    2. If `block` is a :class:`datetime.datetime`, set it
    3. If the deserializer's `format` argument is not None and `block` is a string:

       1. If `format` is a string, try to convert `block` to a datetime using
          :func:`datetime.datetime.strptime`
       2. If `format` is list-like, parse a :class:`datetime.datetime` object with
          ``datetime.datetime.strptime(element, format)``. If the parse is successful,
          use that parsed datetime.

    4. Try casting `block` to a float

       1. If the float has a remainder or the value exceeds the maximum
          ordinal value, treat as a UTC timestamp
       2. Otherwise, treat as a Gregorian ordinal time

    5. Try instantiating a datetime with `block` as an argument to the
       constructor.
    6. If :mod:`numpy` can be imported, try instantiating a
       :obj:`numpy.datetime64` with `block` as an argument to the constructor.
    """

    format: Optional[Union[str, Sequence[str]]]

    def __init__(
        self,
        format: Optional[Union[str, Sequence[str]]] = (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ),
    ):
        super(DefaultDateDeserializer, self).__init__()
        self.format = format

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        from datetime import datetime

        if isinstance(block, datetime):
            parameterized.param.set_param(name, block)
            return
        if self.format is not None and isinstance(block, str):
            v = _get_datetime_from_formats(block, self.format)
            if v is not None:
                parameterized.param.set_param(name, v)
                return
        try:
            float_block = float(block)
            if float_block % 1 or float_block > datetime.max.toordinal():
                block = datetime.utcfromtimestamp(float_block)
            else:
                block = datetime.fromordinal(int(float_block))
            parameterized.param.set_param(name, block)
            return
        except Exception:
            pass
        for dt_type in param.dt_types:
            try:
                block = dt_type(block)
                parameterized.param.set_param(name, block)
                return
            except Exception:
                pass
        raise ParamConfigTypeError(
            parameterized, name, 'cannot convert "{}" to datetime'.format(block)
        )


class DefaultDateRangeDeserializer(ParamConfigDeserializer):
    """Default date range deserializer

    Similar to deserializing a single :class:`datetime.datetime`, but applied to each
    element separately. Cast to a :class:`tuple`.
    """

    format: Optional[Union[str, Sequence[str]]]

    def __init__(
        self,
        format: Optional[Union[str, Sequence[str]]] = (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ),
    ):
        super(DefaultDateRangeDeserializer, self).__init__()
        self.format = format

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        from datetime import datetime

        val = []
        for elem in block:
            if isinstance(elem, datetime):
                val.append(elem)
                continue
            if self.format is not None and isinstance(elem, str):
                v = _get_datetime_from_formats(elem, self.format)
                if v is not None:
                    val.append(v)
                    continue
            try:
                float_elem = float(elem)
                if float_elem % 1 or float_elem > datetime.max.toordinal():
                    elem = datetime.utcfromtimestamp(float_elem)
                else:
                    elem = datetime.fromordinal(int(float_elem))
                val.append(elem)
                continue
            except Exception:
                pass
            for dt_type in param.dt_types:
                try:
                    elem = dt_type(elem)
                    val.append(elem)
                    continue
                except Exception:
                    pass
            raise ParamConfigTypeError(
                parameterized,
                name,
                'cannot convert "{}" from "{}" to datetime'.format(elem, block),
            )
        val = tuple(val)
        try:
            parameterized.param.set_param(name, val)
        except ValueError as e:
            raise ParamConfigTypeError(parameterized, name) from e


class DefaultListDeserializer(ParamConfigDeserializer):
    """Default list deserializer

    The process:

    1. :obj:`None` check
    2. If the parameter's ``class_`` attribute has been set, for each element in `block`
       (we always assume `block` is iterable):

       1. If the element is an instance of the class, leave it alone
       2. Try instantiating a ``class_`` object using the element as the first argument
          plus any arguments or keyword arguments passed to the deserializer on
          initialization.

    3. Cast to a list and set
    """

    def __init__(self, *args, **kwargs):
        super(DefaultListDeserializer, self).__init__()
        self.args = args
        self.kwargs = kwargs

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        p = parameterized.param.params()[name]
        try:
            if p.class_:
                block = [
                    x
                    if isinstance(x, p.class_)
                    else p.class_(x, *self.args, **self.kwargs)
                    for x in block
                ]
            else:
                block = list(block)
            parameterized.param.set_param(name, block)
        except (TypeError, ValueError) as e:
            raise ParamConfigTypeError(parameterized, name) from e


class DefaultListSelectorDeserializer(ParamConfigDeserializer):
    """Default ListSelector deserializer

    For each element in `block` (we assume `block` is iterable), match a value or name
    in the selector's :func:`param.ListSelector.get_range` method
    """

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        # a list selector cannot be none, only empty. Therefore, no "None" checks
        try:
            block = [
                _find_object_in_object_selector(name, x, parameterized) for x in block
            ]
            parameterized.param.set_param(name, block)
        except TypeError as e:
            raise ParamConfigTypeError(parameterized, name) from e


class _CastDeserializer(ParamConfigDeserializer):
    """Default {0} deserializer

    The process:

    1. :obj:`None` check
    2. If `block` is a(n) :class:`{0}`, set it
    3. Initialize a(n) :class:`{0}` instance with `block` as the first argument plus any
       extra positional or keyword arguments passed to the deserializer on
       initialization
    """

    def __init__(self, *args, **kwargs):
        super(_CastDeserializer, self).__init__()
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def class_(cls, x, *args, **kwargs):
        raise NotImplementedError(
            "class_ must be specified in definition of {}".format(cls)
        )

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        try:
            if not isinstance(block, self.class_):
                block = self.class_(block, *self.args, **self.kwargs)
            parameterized.param.set_param(name, block)
            return
        except ValueError as e:
            raise ParamConfigTypeError(parameterized, name) from e


class DefaultIntegerDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format("int")
    class_ = int


class DefaultNumberDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format("float")
    class_ = float


class DefaultNumericTupleDeserializer(ParamConfigDeserializer):
    """Default numeric tuple deserializer

    The process:
    1. :obj:`None` check
    2. Cast each element of `block` to a :class:`float`
    3. Cast `block` to a :class:`tuple`
    """

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        try:
            block = tuple(float(x) for x in block)
            parameterized.param.set_param(name, block)
            return
        except ValueError as e:
            raise ParamConfigTypeError(parameterized, name) from e


class DefaultObjectSelectorDeserializer(ParamConfigDeserializer):
    """Default :class:`param.ObjectSelector` deserializer

    The process:

    1. :obj:`None` check
    2. Match `block` to a value or name in the selector's
       :func:`param.ObjectSelector.get_range` method
    """

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        block = _find_object_in_object_selector(name, block, parameterized)
        parameterized.param.set_param(name, block)


class DefaultSeriesDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format("pandas.Series")

    @property
    def class_(self):
        import pandas

        return pandas.Series


class DefaultStringDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format("str")
    class_ = str


class DefaultTupleDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format("tuple")
    class_ = tuple


class JsonStringArrayDeserializer(DefaultArrayDeserializer):
    """Parses a block as JSON before converting it into a numpy array

    The default deserializer used in INI files. Input is always assumed to be a string
    or :obj:`None`. If :obj:`None`, a none check is performed. Otherwise, it parses the
    value as JSON, then does the same as :class:`DefaultArrayDeserializer`. However, if
    the input ends in the file suffix :obj:`".npy"`, the input will be immediately
    passed to :class:`DefaultArrayDeserializer`

    See Also
    --------
    deserialize_from_json
        To deserialize JSON into :class:`param.parameterized.Parameterized` instances
    """

    file_suffixes = {"csv"}

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        bs = block.split(".")
        if len(bs) > 1 and bs[-1] in self.file_suffixes:
            return super(JsonStringArrayDeserializer, self).deserialize(
                name, block, parameterized
            )
        try:
            block = json.loads(block)
        except json.JSONDecodeError as e:
            raise ParamConfigTypeError(parameterized, name) from e
        super(JsonStringArrayDeserializer, self).deserialize(name, block, parameterized)


class JsonStringDataFrameDeserializer(DefaultDataFrameDeserializer):
    """Parses block as JSON before converting to pandas.DataFrame

    The default deserializer used in INI files. Input is always assumed to be a string
    or :obj:`None`. If :obj:`None`, a none check is performed. Otherwise, it parses the
    value as JSON, then does the same as :class:`DefaultDataFrameSerializer`. However,
    if the input ends in a file suffix like :obj:`".csv"`, :obj:`".xls"`, etc., the
    input will be immediately passed to :class:`DefaultDataFrameSerializer`

    See Also
    --------
    deserialize_from_json
        To deserialize JSON into :class:`param.parameterized.Parameterized` instances
    """

    file_suffixes = {
        "csv",
        "dta",
        "feather",
        "h5",
        "html",
        "json",
        "parquet",
        "pkl",
        "sas7bdat",
        "xls",
    }  #:

    def deserialize(
        self, name: str, block: Any, parameterized: param.Parameterized
    ) -> None:
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        bs = block.split(".")
        if len(bs) > 1 and bs[-1] in self.file_suffixes:
            return super(JsonStringDataFrameDeserializer, self).deserialize(
                name, block, parameterized
            )
        try:
            block = json.loads(block)
        except json.JSONDecodeError as e:
            raise ParamConfigTypeError(parameterized, name) from e
        super(JsonStringDataFrameDeserializer, self).deserialize(
            name, block, parameterized
        )


def _to_json_string_deserializer(cls, typename):
    class _JsonStringDeserializer(cls):
        """Parses block as json before converting into {}

        The default deserializer used in INI files.

        1. :obj:`None` check
        2. It parses the value as a JSON string
        3. Does the same as :class:`{}`

        See Also
        --------
        deserialize_from_json
            To deserialize json into :class:`param.parameterized.Parameterized`
            instances
        """.format(
            typename, cls.__name__
        )

        def deserialize(
            self, name: str, block: Any, parameterized: param.Parameterized
        ) -> None:
            if self.check_if_allow_none_and_set(name, block, parameterized):
                return
            try:
                block = json.loads(block)
            except json.JSONDecodeError as e:
                raise ParamConfigTypeError(parameterized, name) from e
            super(_JsonStringDeserializer, self).deserialize(name, block, parameterized)

    return _JsonStringDeserializer


JsonStringDateRangeDeserializer = _to_json_string_deserializer(
    DefaultDateRangeDeserializer, "param.DateRange"
)

JsonStringDictDeserializer = _to_json_string_deserializer(DefaultDeserializer, "dict")

JsonStringListDeserializer = _to_json_string_deserializer(
    DefaultListDeserializer, "list"
)

JsonStringListSelectorDeserializer = _to_json_string_deserializer(
    DefaultListSelectorDeserializer, "param.ListSelector"
)

JsonStringNumericTupleDeserializer = _to_json_string_deserializer(
    DefaultNumericTupleDeserializer, "param.NumericTuple"
)

JsonStringSeriesDeserializer = _to_json_string_deserializer(
    DefaultSeriesDeserializer, "param.Series"
)

JsonStringTupleDeserializer = _to_json_string_deserializer(
    DefaultTupleDeserializer, "tuple"
)


DEFAULT_DESERIALIZER_DICT = {
    param.Array: DefaultArrayDeserializer(),
    param.Boolean: DefaultBooleanDeserializer(),
    param.ClassSelector: DefaultClassSelectorDeserializer(),
    param.DataFrame: DefaultDataFrameDeserializer(),
    param.Date: DefaultDateDeserializer(),
    param.DateRange: DefaultDateRangeDeserializer(),
    param.HookList: DefaultListDeserializer(),
    param.Integer: DefaultIntegerDeserializer(),
    param.List: DefaultListDeserializer(),
    param.ListSelector: DefaultListSelectorDeserializer(),
    param.Magnitude: DefaultNumberDeserializer(),
    param.MultiFileSelector: DefaultListSelectorDeserializer(),
    param.Number: DefaultNumberDeserializer(),
    param.NumericTuple: DefaultNumericTupleDeserializer(),
    param.ObjectSelector: DefaultObjectSelectorDeserializer(),
    param.Range: DefaultNumericTupleDeserializer(),
    param.Series: DefaultSeriesDeserializer(),
    param.String: DefaultStringDeserializer(),
    param.Tuple: DefaultTupleDeserializer(),
    param.XYCoordinates: DefaultNumericTupleDeserializer(),
}

DEFAULT_BACKUP_DESERIALIZER = DefaultDeserializer()


JSON_STRING_DESERIALIZER_DICT = {
    param.Array: JsonStringArrayDeserializer(),
    param.DataFrame: JsonStringDataFrameDeserializer(),
    param.DateRange: JsonStringDateRangeDeserializer(),
    param.Dict: JsonStringDictDeserializer(),
    param.List: JsonStringListDeserializer(),
    param.ListSelector: JsonStringListSelectorDeserializer(),
    param.MultiFileSelector: JsonStringListSelectorDeserializer(),
    param.NumericTuple: JsonStringNumericTupleDeserializer(),
    param.Range: JsonStringNumericTupleDeserializer(),
    param.Series: JsonStringSeriesDeserializer(),
    param.Tuple: JsonStringTupleDeserializer(),
    param.XYCoordinates: JsonStringNumericTupleDeserializer(),
}


def _deserialize_from_dict_flat(
    dict_, parameterized, deserializer_name_dict, deserializer_type_dict, on_missing
):
    if deserializer_type_dict is not None:
        deserializer_type_dict2 = dict(DEFAULT_DESERIALIZER_DICT)
        deserializer_type_dict2.update(deserializer_type_dict)
        deserializer_type_dict = deserializer_type_dict2
    else:
        deserializer_type_dict = DEFAULT_DESERIALIZER_DICT
    if deserializer_name_dict is None:
        deserializer_name_dict = dict()
    for name, block in list(dict_.items()):
        if name not in parameterized.param.params():
            msg = 'No param "{}" to set in "{}"'.format(name, parameterized.name)
            if on_missing == "warn":
                parameterized.warning(msg)
            elif on_missing == "raise":
                raise ValueError(msg)
            continue
        if name in deserializer_name_dict:
            deserializer = deserializer_name_dict[name]
        else:
            type_ = type(parameterized.param.params()[name])
            if type_ in deserializer_type_dict:
                deserializer = deserializer_type_dict[type_]
            else:
                deserializer = DEFAULT_BACKUP_DESERIALIZER
        deserializer.deserialize(name, block, parameterized)


def deserialize_from_dict(
    dict_: dict,
    parameterized: Union[param.Parameterized, dict],
    deserializer_name_dict: Optional[dict] = None,
    deserializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "warn",
) -> None:
    """Deserialize a dictionary into a parameterized object

    This function is suitable for deserializing the results of parsing a data storage
    file such as a YAML, JSON, or a section of an INI file (using the :mod:`yaml`,
    :mod:`json`, and :mod:`configparser` python modules, resp.) into a
    :class:`param.parameterized.Parameterized` object. Each key in `dict_` should match
    the name of a parameter in `parameterized`. The parameter will be deserialized into
    `parameterized` using a :class:`ParamConfigDeserializer` object matched with the
    following precedent:

     1. If `deserializer_name_dict` is specified and contains the same key, the value of
        the item in `deserializer_name_dict` will be used.
     2. If `deserializer_type_dict` and the type of the parameter in question *exactly
        matches* a key in `deserializer_type_dict`, the value of the item in
        `deserializer_type_dict` will be used.
     3. If the type of the parameter in question has a default deserializer (i.e.
        ``Default<type>Deserializer``), it will be used.
     4. :class:`DefaultBackupDeserializer` will be used.

    It is possible to pass a dictionary as `parameterized` instead of a
    :class:`param.parameterized.Parameterized` instance to this function. This is
    "hierarchical mode". The values of `parameterized` can be
    :class:`param.parameterized.Parameterized` objects or nested dictionaries. In this
    case, `dict_` and `deserializer_name_dict` are expected to be dictionaries with the
    same hierarchical structure (though the latter can still be :obj:`None`).
    `deserializer_type_dict` can be a flat dictionary of types to be applied to all
    nodes, or a hierarchical dictionary of strings like `dict_`, or some combination.
    The leaves of `dict_` deserialize into the leaves of `parameterized`. If no leaf of
    `dict_` exists for a given `parameterized` leaf, that parameterized object will not
    be updated.

    Default deserializers are likely appropriate for basic types like strings, ints,
    bools, floats, and numeric tuples. For more complex data types, including recursive
    :class:`param.parameterized.Parameterized` instances, custom deserializers are
    recommended.

    Parameters
    ----------
    dict_
    parameterized
    deserializer_name_dict
    deserializer_type_dict
    on_missing
        What to do if the parameterized instance does not have a parameter
        listed in `dict_`, or, in the case of "hierarchical mode", if
        `dict_` contains a key with no matching parameterized object to
        populate

    Raises
    ------
    ParamConfigTypeError
        If deserialization of a value fails
    """
    d_stack = [dict_]
    p_stack = [parameterized]
    dnd_stack = [deserializer_name_dict]
    dtd_stack = [deserializer_type_dict]
    n_stack = [tuple()]
    while len(d_stack):
        d = d_stack.pop()
        p = p_stack.pop()
        dnd = dnd_stack.pop()
        dtd = dtd_stack.pop()
        n = n_stack.pop()
        if isinstance(p, param.Parameterized):
            _deserialize_from_dict_flat(d, p, dnd, dtd, on_missing)
        else:
            for name in d:
                p_name = p.get(name, None)
                n_stack.append(n + (name,))
                if p_name is None:
                    msg = (
                        "dict_ contains hierarchical key chain {} but no "
                        "parameterized instance to match it"
                    ).format(n_stack[-1])
                    if on_missing == "raise":
                        raise ValueError(msg)
                    elif on_missing == "warn":
                        param.get_logger().warning(msg)
                    continue
                d_stack.append(d.get(name, dict()))
                p_stack.append(p_name)
                if dnd is None:
                    dnd_stack.append(None)
                else:
                    dnd_stack.append(dnd.get(name, None))
                if dtd is None or dtd.get(name, "a") is None:
                    dtd_stack.append(None)
                else:
                    dtd_name = dict(
                        (k, v) for (k, v) in list(dtd.items()) if isinstance(k, type)
                    )
                    dtd_name.update(dtd.get(name, dict()))
                    dtd_stack.append(dtd_name)


def deserialize_from_ini(
    file: Union[TextIO, str],
    parameterized: Union[param.Parameterized, dict],
    deserializer_name_dict: Optional[dict] = None,
    deserializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "warn",
    defaults: Optional[dict] = None,
    comment_prefixes: Sequence[str] = ("#", ";"),
    inline_comment_prefixes: Sequence[str] = (";",),
    one_param_section: Optional[str] = None,
) -> None:
    """Deserialize an INI (config) file into a parameterized instance

    `.INI syntax <https://en.wikipedia.org/wiki/INI_file>`__, extended with
    :mod:`configparser`. :mod:`configparser` extends the INI syntax with value
    interpolation. Further, keys missing a value will be interpreted as having the value
    :obj:`None`. This function converts an INI file to a dictionary, then populates
    `parameterized` with the contents of this dictionary.

    INI files are broken up into sections; all key-value pairs must belong to a section.
    If `parameterized` is a :class:`param.parameterized.Parameterized` instance (rather
    than a hierarchical dictionary of them), the action will try to deserialize the
    section specified by `one_param_section` keyword argument.

    Because the INI syntax does not support standard containers like dicts or lists
    out-of-the-box, this function uses the ``JsonString*Deserializer`` to read container
    values to JSON strings before trying the standard method of deserialization. This
    solution was proposed `here
    <https://stackoverflow.com/questions/335695/lists-in-configparser>`__. Defaults
    ``Default<type>Deserializer`` are clobbered by those of form
    ``Json<type>Deserializer``. You can get the original defaults back by including them
    in `deserializer_type_dict`

    Parameters
    ----------
    file
        The INI file to deserialize from. Can be a pointer or a path
    parameterized
    deserializer_name_dict
    deserializer_type_dict
    on_missing
    defaults
        Default key-values used in interpolation (substitution). Terms such
        as ``(key)%s`` (like a python 2.7 format string) are substituted with
        these values
    comment_prefixes
        A sequence of characters that indicate a full-line comment in the INI file
    inline_comment_prefixes
        A sequence of characters that indicate an inline (including full-line) comment
        in the INI file
    one_param_section
        If `parameterized` refers to a single :class:`param.parameterized.Parameterized`
        instance, this keyword is used to indicate which section of the INI file will be
        deserialized. If unspecified, will default to the ``name`` attribute of
        `parameterized`

    See Also
    --------
    deserialize_from_dict
        A description of the deserialization process and the parameters to this function
    """
    if isinstance(file, str):
        with open(file) as fp:
            return deserialize_from_ini(
                fp,
                parameterized,
                deserializer_name_dict,
                deserializer_type_dict,
                on_missing,
                defaults,
                comment_prefixes,
                inline_comment_prefixes,
                one_param_section,
            )
    if deserializer_type_dict:
        d = JSON_STRING_DESERIALIZER_DICT.copy()
        d.update(deserializer_type_dict)
        deserializer_type_dict = d
    else:
        deserializer_type_dict = JSON_STRING_DESERIALIZER_DICT
    parser = configparser.ConfigParser(
        defaults=defaults,
        comment_prefixes=comment_prefixes,
        inline_comment_prefixes=inline_comment_prefixes,
        allow_no_value=True,
    )
    try:
        parser.read_file(file)
    except AttributeError:
        parser.readfp(file)
    if isinstance(parameterized, param.Parameterized):
        if one_param_section is None:
            one_param_section = parameterized.name
        dict_ = OrderedDict(parser.items(one_param_section))
    else:
        dict_ = OrderedDict(
            (s, OrderedDict(list(parser[s].items()))) for s in parser.sections()
        )
    deserialize_from_dict(
        dict_,
        parameterized,
        deserializer_name_dict=deserializer_name_dict,
        deserializer_type_dict=deserializer_type_dict,
        on_missing=on_missing,
    )


def deserialize_from_yaml(
    file: Union[TextIO, str],
    parameterized: Union[param.Parameterized, dict],
    deserializer_name_dict: Optional[dict] = None,
    deserializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "warn",
) -> None:
    """Deserialize a YAML file into a parameterized instance

    Composes :func:`deserialize_from_yaml_to_obj` with :func:`deserialize_from_dict`.
    """
    dict_ = deserialize_from_yaml_to_obj(file)
    deserialize_from_dict(
        dict_,
        parameterized,
        deserializer_name_dict=deserializer_name_dict,
        deserializer_type_dict=deserializer_type_dict,
        on_missing=on_missing,
    )


def deserialize_from_json(
    file_: Union[TextIO, str],
    parameterized: Union[param.Parameterized, str],
    deserializer_name_dict: Optional[dict] = None,
    deserializer_type_dict: Optional[dict] = None,
    on_missing: Literal["ignore", "warn", "raise"] = "warn",
) -> None:
    """Deserialize a YAML file into a parameterized instance

    Composes :func:`deserialize_from_json_to_obj` with :func:`deserialize_from_dict`.
    """
    dict_ = deserialize_from_json_to_obj(file_)
    deserialize_from_dict(
        dict_,
        parameterized,
        deserializer_name_dict=deserializer_name_dict,
        deserializer_type_dict=deserializer_type_dict,
        on_missing=on_missing,
    )
