'''Utilities for (de)serializing param.Parameterized objects'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc

from builtins import bytes
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

import param

from future.utils import with_metaclass, raise_from

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2018 Sean Robertson"


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
    '''Raised when failed to (de)serialize Parameterized object'''

    def __init__(self, parameterized, name, message=''):
        super(ParamConfigTypeError, self).__init__(
            '{}.{}: {}'.format(parameterized.name, name, message)
        )


class ParamConfigSerializer(with_metaclass(abc.ABCMeta, object)):
    '''Serialize a parameter value from a parameterized object

    Subclasses of ``ParamConfigSerializer`` are expected to implement
    `serialize`. Instances of the subclass can be passed into
    ``pydrobert.param.serialization.serialize_to_dict``. The goal of a
    serializer is to convert a parameter value from a
    ``param.Parameterized`` object into something that can be handled
    by a dict-like data store. The format of the outgoing data should
    reflect where the dict-like data are going. For example, a JSON
    serializer can handle lists, but not an INI serializer. In
    ``pydrobert.param.serialization``, there are a number of default
    serializers (matching the pattern ``Default*Serializer``) that are
    best guesses on how to serialize data from a variety of sources
    '''

    def help_string(self, name, parameterized):
        '''A string that helps explain this serialization

        The return string will be included in the second element of
        the pair returned by
        ``pydrobert.param.serialization.serialize_to_dict``. Helps
        explain the serialized value to the user.
        '''
        return None

    @abc.abstractmethod
    def serialize(self, name, parameterized):
        '''Serialize data from a parameterized object and return it

        Parameters
        ----------
        name : str
            The name of the parameter in `parameterized` to retrieve the
            value from
        parameterized : param.Parameterized
            The parameterized instance containing a parameter with the
            name `name`

        Returns
        -------
        val : obj
            The serialized value of the parameter

        Raises
        ------
        ParamConfigTypeError
            If serialization could not be performed
        '''
        raise NotImplementedError()


class DefaultSerializer(ParamConfigSerializer):
    '''Default catch-all serializer. Returns value verbatim'''

    def serialize(self, name, parameterized):
        return getattr(parameterized, name)


class DefaultArraySerializer(ParamConfigSerializer):
    '''Default numpy array serializer

    The process:
    1. If None, return
    2. Call value's ``tolist()`` method
    '''

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is None:
            return val
        return val.tolist()


def _get_name_from_param_range(name, parameterized, val):
    p = parameterized.params()[name]
    val_type = type(val)
    for n, v in p.get_range().items():
        if isinstance(v, val_type) and _equal(v, val):
            return n
    parameterized.warning(
        "Could not find value of {} in get_range(), so serializing value "
        "directly".format(name))
    return val


class DefaultClassSelectorSerializer(ParamConfigSerializer):
    '''Default ClassSelector serializer

    The process:
    1. If None, return
    2. If parameter's ``is_instance`` attribute is ``True``, return value
       verbatim
    3. Search for the corresponding name in the selector's ``get_range()``
       dictionary and return that name, if possibile
    4. Return the value
    '''

    def help_string(self, name, parameterized):
        p = parameterized.params()[name]
        hashes = tuple(p.get_range())
        if p.is_instance and len(hashes):
            s = 'Choices: '
            s += ', '.join(('"' + x + '"' for x in hashes))
            return s
        else:
            return None

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        p = parameterized.params()[name]
        if val is None or p.is_instance:
            return val
        else:
            return _get_name_from_param_range(name, parameterized, val)


class DefaultDataFrameSerializer(ParamConfigSerializer):
    '''Default pandas.DataFrame serializer

    The process:
    1. If None, return
    2. Call ``tolist()`` on the ``values`` property of the parameter's
       value and return
    '''

    def help_string(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is not None:
            return "DataFrame axes: {}".format(val.axes)
        else:
            return None

    def serialize(self, name, parameterized):
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
        raise_from(ParamConfigTypeError(parameterized, name), e)
    parameterized.warning(
        'Loss of info for datetime {} in serialized format string'.format(
            dt, s))
    return s, format


class DefaultDateSerializer(ParamConfigSerializer):
    '''Default date serializer

    The process:
    1. If None, return
    2. If a ``datetime.datetime`` instance
       1. If the `format` keyword argument of the serializer is not None:
          1. If `format` is a string, return the result of the value's
             ``strftime(format)`` call
          2. If `format` is list-like, iterate through it, formatting with
             ```strftime(element)``. Whichever string which, when deserialized
             with ``strptime(element)``, produces an equivalent ``datetime``
             object as the value is returned. If no such string exists, the
             last string is returned.
       2. Return the result of the value's ``timestamp()`` call
    3. If a ``numpy.datetime64`` instance, return the value cast to a
       string
    '''

    def __init__(
            self,
            format=('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f')):
        super(DefaultDateSerializer, self).__init__()
        self.format = format

    def help_string(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is None:
            return val
        from datetime import datetime
        if isinstance(val, datetime):
            if self.format is None:
                return "Timestamp"
            else:
                return "Date format string: " + _datetime_to_formatted(
                    parameterized, name, val, self.format)[1]
        else:
            return "ISO 8601 format string"

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is None:
            return val
        from datetime import datetime
        if isinstance(val, datetime):
            if self.format is None:
                return val.timestamp()
            else:
                val = _datetime_to_formatted(
                    parameterized, name, val, self.format)[0]
        return str(val)


class DefaultDateRangeSerializer(ParamConfigSerializer):
    '''Default date range serializer

    Similar to serializing a single `datetime`, but applied to each element
    separately. Also cast to a list
    '''

    def __init__(
            self,
            format=('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f')):
        super(DefaultDateRangeSerializer, self).__init__()
        self.format = format

    def help_string(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is None:
            return val
        val = val[0]  # assuming they're of the same granularity
        from datetime import datetime
        if isinstance(val, datetime):
            if self.format is None:
                return "Timestamp"
            else:
                return "Date format string: " + _datetime_to_formatted(
                    parameterized, name, val, self.format)[1]
        else:
            return "ISO 8601 format string"

    def serialize(self, name, parameterized):
        vals = getattr(parameterized, name)
        if vals is None:
            return vals
        from datetime import datetime
        ret = []
        for val in vals:
            if isinstance(val, datetime):
                if self.format is None:
                    val = val.timestamp()
                else:
                    val = _datetime_to_formatted(
                        parameterized, name, val, self.format)[0]
            else:
                val = str(val)
            ret.append(val)
        return ret


class DefaultListSelectorSerializer(ParamConfigSerializer):
    '''Default ListSelector serializer

    For each element in the value:
    1. Search for its name in the selector's ``get_range()`` dict and
       swap if for the name, if possible
    2. Otherwise, use that element verbatim
    '''

    def help_string(self, name, parameterized):
        p = parameterized.params()[name]
        hashes = tuple(p.get_range())
        if len(hashes):
            s = 'Element choices: '
            s += ', '.join(('"' + x + '"' for x in hashes))
            return s
        else:
            return None

    def serialize(self, name, parameterized):
        return [
            _get_name_from_param_range(name, parameterized, x)
            for x in getattr(parameterized, name)
        ]


class DefaultObjectSelectorSerializer(ParamConfigSerializer):
    '''Default ObjectSelector serializer

    The process:
    1. If None, return
    2. Search for the name of the value in the selector's ``get_range()``
       dictionary and return, if possible
    3. Return value verbatim
    '''

    def help_string(self, name, parameterized):
        p = parameterized.params()[name]
        hashes = tuple(p.get_range())
        if len(hashes):
            s = 'Choices: '
            s += ', '.join(('"' + x + '"' for x in hashes))
            return s
        else:
            return None

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is None:
            return val
        return _get_name_from_param_range(name, parameterized, val)


class DefaultSeriesSerializer(ParamConfigSerializer):
    '''Default pandas.Series serializer

    The process:
    1. If None, return
    2. Call ``tolist()`` on the ``values`` property of the parameter's
       value and return
    '''

    def help_string(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is not None:
            return "Series axes: {}".format(val.axes)
        return None

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        if val is None:
            return
        return val.values.tolist()


class DefaultTupleSerializer(ParamConfigSerializer):
    '''Default tuple serializer

    The process:
    1. If None, return
    2. Casts the value to a list
    '''

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        return val if val is None else list(val)


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


def _serialize_to_dict_flat(
        parameterized, only, serializer_name_dict, serializer_type_dict,
        on_missing):
    if serializer_type_dict is not None:
        serializer_type_dict2 = dict(DEFAULT_SERIALIZER_DICT)
        serializer_type_dict2.update(serializer_type_dict)
        serializer_type_dict = serializer_type_dict2
    else:
        serializer_type_dict = DEFAULT_SERIALIZER_DICT
    if serializer_name_dict is None:
        serializer_name_dict = dict()
    if only is None:
        only = set(parameterized.params())
    dict_ = dict()
    help_dict = dict()
    for name in only:
        if name not in parameterized.params():
            msg = 'No param "{}" to read in "{}"'.format(
                name, parameterized.name)
            if on_missing == 'warn':
                parameterized.warning(msg)
            elif on_missing == 'raise':
                raise ValueError(msg)
            continue
        if name in serializer_name_dict:
            serializer = serializer_name_dict[name]
        else:
            type_ = type(parameterized.params()[name])
            if type_ in serializer_type_dict:
                serializer = serializer_type_dict[type_]
            else:
                serializer = DEFAULT_BACKUP_SERIALIZER
        dict_[name] = serializer.serialize(name, parameterized)
        help_string_serial = serializer.help_string(name, parameterized)
        help_string_doc = parameterized.params()[name].doc
        if help_string_doc:
            if help_string_serial:
                help_string_doc = help_string_doc.strip('. ')
                help_dict[name] = '. '.join(
                    (help_string_doc, help_string_serial))
            else:
                help_dict[name] = help_string_doc
        elif help_string_serial:
            help_dict[name] = help_string_serial
    return dict_, help_dict


def serialize_to_dict(
        parameterized,
        only=None,
        serializer_name_dict=None,
        serializer_type_dict=None,
        on_missing='raise',
        include_help=False):
    '''Serialize a parameterized object into a dictionary

    This function serializes data into a dictionary format, suitable for
    storage in a dict-like file format such as YAML or JSON. Each parameter
    will be serialized into the dictionary using a `ParamConfigSerializer`
    object, matched with the following precedent:
    1. If `serializer_name_dict` is specified and contains the parameter
       name as a key, the value will be used.
    2. If `serializer_type_dict` and the type of the parameter in question
       *exactly matches* a key in `serializer_type_dict`, the value of the
       item in `serializer_type_dict` will be used.
    3. If the type of the parameter in question *exactly matches* a key in
       `DEFAULT_SERIALIZER_DICT`, the value of the item in
       `DEFAULT_SERIALIZER_DICT` will be used.
    4. `DEFAULT_BACKUP_SERIALIZER` will be used.

    Default serializers are likely appropriate for basic types like strings,
    ints, bools, floats, and numeric tuples. For more complex data types,
    including recursive `param.Parameterized` instances, custom serializers
    are recommended.

    It is possible to pass a dictionary as `parameterized` instead of a
    ``param.Parameterized`` instance to this function. This is "hierarchical
    mode". The values of `parameterized` can be ``param.Parameterized`` objects
    or nested dictionaries. The returned dictionary will have the same
    hierarchical dictionary structure as `parameterized`, but with the
    ``param.Parameterized`` values replaced with serialized dictionaries. In
    this case, `only`, `deserializer_name_dict`, and `deserializer_type_dict`
    are expected to be dictionaries with the same hierarchical structure
    (though they can still be ``None``, which propagates to children), whose
    leaves correspond to the arguments used to serialize the leaves of
    `parameterized`.

    Parameters
    ----------
    parameterized : param.Parameterized or dict
    only : set or dict, optional
        If specified, only the parameters with their names in this set will
        be serialized into the return dictionary
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
        What to do if the parameterized instance does not have a parameter
        listed in `only`
    include_help : bool, optional
        If ``True``, the return value will be a pair of dictionaries instead
        of a single dictionary. This dictionary will contain any help strings
        any serializers make available through a call to ``help_string`` (or
        ``None`` if none is available).

    Returns
    -------
    dict or tuple
        A dictionary of serialized parameters or a pair of dictionaries if
        `include_help` was ``True`` (the latter is the help dictionary).

    Raises
    ------
    ParamConfigTypeError
        If serialization of a value fails
    '''
    dict_ = dict()
    help_dict = dict()
    p_stack = [parameterized]
    o_stack = [only]
    snd_stack = [serializer_name_dict]
    std_stack = [serializer_type_dict]
    d_stack = [dict_]
    h_stack = [help_dict]
    while len(p_stack):
        p = p_stack.pop()
        o = o_stack.pop()
        snd = snd_stack.pop()
        std = std_stack.pop()
        d = d_stack.pop()
        h = h_stack.pop()
        if isinstance(p, param.Parameterized):
            dp, hp = _serialize_to_dict_flat(p, o, snd, std, on_missing)
            d.update(dp)
            h.update(hp)
        else:
            for name in p:
                p_stack.append(p[name])
                if o is None:
                    o_stack.append(None)
                else:
                    o_stack.append(o[name])
                if snd is None:
                    snd_stack.append(None)
                else:
                    snd_stack.append(snd[name])
                if std is None:
                    std_stack.append(None)
                else:
                    std_stack.append(std[name])
                d_stack.append(dict())
                d[name] = d_stack[-1]
                h_stack.append(dict())
                h[name] = h_stack[-1]
    return (dict_, help_dict) if include_help else dict_


def _serialize_to_ini_fp(
        fp, parameterized, only, serializer_name_dict, serializer_type_dict,
        on_missing, include_help, help_prefix, one_param_section):
    try:
        from ConfigParser import SafeConfigParser
        parser = SafeConfigParser()
    except ImportError:
        from configparser import ConfigParser
        parser = ConfigParser(
            comment_prefixes=(help_prefix,),
        )
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
    if isinstance(parameterized, param.Parameterized):
        if one_param_section is None:
            one_param_section = parser.default_section
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
                parser.add_section(section)
            if h:
                help_string_io.write('{} [{}]\n'.format(help_prefix, section))
            for key, val in d.items():
                parser.set(section, key, str(val))
                if key in h:
                    help_string_io.write('{} {}: {}\n'.format(
                        help_prefix, key, h[key]))
            if h:
                help_string_io.write('\n')
        else:
            if len(s_queue):
                raise IOError(
                    'INI format cannot serialize hierarchical parameterized '
                    'dictionaries greater than depth 1')
            for key in p:
                if key not in d:
                    continue
                p_queue.insert(0, p[key])
                d_queue.insert(0, d[key])
                h_queue.insert(0, h.get(key, dict()))
                s_queue.insert(0, key)
    help_string = help_string_io.getvalue()
    if len(help_string):
        fp.write('{} == Help == '.format(help_prefix))
        fp.write(help_string)
        fp.write('\n')
    parser.write(fp)


def serialize_to_ini(
        file, parameterized,
        only=None,
        serializer_name_dict=None,
        serializer_type_dict=None,
        on_missing='raise',
        include_help=True,
        help_prefix='#',
        one_param_section=None):
    '''Serialize a parameterized instance into an INI (config) file

    `.INI syntax <https://en.wikipedia.org/wiki/INI_file>`, also including
    `interpolation
    <https://docs.python.org/3.7/library/configparser.html>`. This function
    converts `parameterized` to a dictionary, then fills an INI file with
    the contents of this dictionary.

    INI files are broken up into sections; all key-value
    pairs must belong to a section. If `parameterized` is a
    ``param.Parameterized`` instance (rather than a hierarchical dictionary of
    them), the action will try to serialize `parameterized` into the section
    specified by the `one_param_section` keyword argument. If `parameterized`
    is a hierarchical dictionary, it can only have depth 1, with each leaf
    being a ``param.Parameterized`` instance. In this case, each key
    corresponds to a section. If an ordered dictionary, sections will be
    written in the same order as they exist in `parameterized`.

    Parameters
    ----------
    file : file pointer or str
        The INI file to serialize to. Can be a pointer or a path
    parameterized : param.Parameterized or dict
    only : set or dict, optional
    serializer_name_dict : dict, optional
    serializer_type_dict : dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
    include_help : bool, optional
        If ``True``, help documentation will be included at the top of the
        INI file for any parameters and/or serializers that support it
    help_prefix : str, optional
        The character prefix used at the start of each help line, usually
        indicating a comment
    one_param_section : str or None, optional
        If `parameterized` refers to a single ``param.Parameterized`` instance,
        this keyword is used to indicate which section of the INI file
        `parameterized` will be serialized to. If ``None``, the INI file's
        default section (``"DEFAULT"``) will be used
    '''
    if isinstance(file, str):
        with open(file, 'w') as fp:
            _serialize_to_ini_fp(
                fp, parameterized, only, serializer_name_dict,
                serializer_type_dict, on_missing, include_help, help_prefix,
                one_param_section)
    else:
        _serialize_to_ini_fp(
            file, parameterized, only, serializer_name_dict,
            serializer_type_dict, on_missing, include_help, help_prefix,
            one_param_section)


class ParamConfigDeserializer(with_metaclass(abc.ABCMeta, object)):
    '''Deserialize part of a configuration into a parameterized object

    Subclasses of ``ParamConfigDeserializer`` are expected to implement
    `deserialize`. Instances of the subclass can be passed into
    ``pydrobert.param.serialization.deserialize_from_dict``. The goal of
    a deserializer is to convert data into the value of a parameter in a
    ``param.Parameterized`` object. The format of the incoming data is
    specific to where the dict-like input came from. For example, a JSON
    parser converts numeric strings to floats, and the contents of square
    braces (``[]``) as lists. In ``pydrobert.param.serialization``, there
    are a number of default deserializers (matching the pattern
    ``Default*Deserializer``) that are best guesses on how to deserialize
    data from a variety of sources.
    '''

    @abc.abstractmethod
    def deserialize(self, name, block, parameterized):
        '''Deserialize data and store it in a parameterized object

        Parameters
        ----------
        name : str
            The name of the parameter in `parameterized` to store the
            value under
        block : object
            The data to deserialize into the parameter value
        parameterized : param.Parameterized
            The parameterized instance containing a parameter with the
            name `name`. On completion of this method, that parameter will
            be set with the deserialized contents of `block`

        Raises
        ------
        ParamConfigTypeError
            If deserialization could not be performed
        '''
        raise NotImplementedError()

    @classmethod
    def check_if_allow_none_and_set(cls, name, block, parameterized):
        '''Check if block can be made none and set it if allowed

        Many ```param.Param`` parameters allow ``None`` as a value. This
        is a convenience method that deserializers can use to quickly
        check for a ``None`` value and set it in that case. This method
        sets the parameter and returns ``True`` in the following
        conditions

        1. The parameter allows ``None`` values (the ``allow_None``
           attribute is ``True``)
        2. One of:
           1. `block` is ``None``
           2. `block` is a string matching ``"None"`` or ``"none"``

        If one of these conditions wasn't met, the parameter remains unset
        and the method returns ``False``.

        In ``Default*Deseriazer`` documentation, a call to this method is
        referred to as a "none check".
        '''
        p = parameterized.params()[name]
        if (
                (
                    block is None or
                    (isinstance(block, str) and (block in {'None', 'none'}))
                ) and p.allow_None):
            parameterized.param.set_param(name, None)
            return True
        else:
            return False


class DefaultDeserializer(ParamConfigDeserializer):
    '''Catch-all deserializer

    This serializer performs a none check, then tries to set the parameter
    with the value of `block` verbatim.
    '''

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        try:
            parameterized.set_param(name, block)
        except ValueError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultArrayDeserializer(ParamConfigDeserializer):
    '''Default deserializer for numpy arrays

    Keyword arguments can be passed to referenced methods by initializing this
    deserializer with those keyword arguments.

    The process:
    1. None check
    2. If already a numpy array, set it
    3. If a string ending with '.npy', load it as a file path (``numpy.load``
       with kwargs)
    4. If bytes, load it with ``numpy.frombuffer`` and kwargs
    5. If a string, load it with ``numpy.fromstring`` and kwargs
    6. Try initializing to array with ``numpy.array`` and kwargs
    '''

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        super(DefaultArrayDeserializer, self).__init__()

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        import numpy as np
        if isinstance(block, np.ndarray):
            parameterized.param.set_param(name, block)
            return
        if isinstance(block, str) and block.endswith('.npy'):
            try:
                block = np.load(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except (ValueError, IOError) as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)
        elif isinstance(block, bytes):
            try:
                block = np.frombuffer(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)
        elif isinstance(block, str):
            try:
                block = np.fromstring(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)
        else:
            try:
                block = np.array(block, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultBooleanDeserializer(ParamConfigDeserializer):
    '''Default deserializer for booleans

    The process:
    1. None check
    2. Check `block` against a number of strings commonly meaning ``True``
       (e.g. ``"YES"``, ``"t"``, and ``"on"``) as well as the number 1.
    3. Check `block` against a number of strins commonly meaning ``False``
    4. If a boolean, set it
    '''

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        if block in {
                'True', 'true', 't', 'on', 'TRUE', 'T', 'ON', 'yes',
                'YES', 1, '1'}:
            block = True
        elif block in {
                'False', 'false', 'f', 'off', 'FALSE', 'F', 'OFF',
                'no', 'NO', 0, '0'}:
            block = False
        if block in {True, False}:
            parameterized.param.set_param(name, block)
        else:
            raise ParamConfigTypeError(
                parameterized, name,
                'cannot convert "{}" to bool'.format(block))


def _find_object_in_object_selector(name, block, parameterized):
    p = parameterized.params()[name]
    named_objs = p.get_range()
    for val in named_objs.values():
        if _equal(val, block):
            return val
    try:
        return named_objs[str(block)]
    except Exception:
        pass
    try:
        parameterized.param.set_param(name, block)
    except ValueError as e:
        raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultClassSelectorDeserializer(ParamConfigDeserializer):
    '''Default ClassSelector deserializer

    The process:
    1. None check
    2. If the parameter's ``is_instance`` attribute is ``True``:
       1. If `block` is an instance of the parameter's ``class_`` attribute,
          set it
       2. Try instantiating the class with `block` as the first argument, with
          additional arguments and keyword arguments passed to the deserializer
          passed allong to the constructor.
    3. Look for the block or the block name in the selector's ``get_range()``
       dictionary
    '''

    def __init__(self, *args, **kwargs):
        super(DefaultClassSelectorDeserializer, self).__init__()
        self.args = args
        self.kwargs = kwargs

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        p = parameterized.params()[name]
        try:
            if p.is_instance:
                if not isinstance(block, p.class_):
                    block = p.class_(block, *self.args, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
        except ValueError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)
        block = _find_object_in_object_selector(name, block, parameterized)
        try:
            parameterized.param.set_param(name, block)
        except ValueError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultDataFrameDeserializer(ParamConfigDeserializer):
    '''Default panda.DataFrame deserializer

    Keyword arguments and positional arguments can be passed to referenced
    methods by initializing this deserializer with those keyword arguments.

    The process:
    1. None check
    2. If `block` is a data frame, set it
    3. If `block` is a string that ends with one of a number of file suffixes,
       e.g. ``".csv", ".json", ".html", ".xls"``, use the associated
       ``pandas.read_*`` method with `block` as the first argument plus
       the deserializer's extra args and kwargs
    4. If `block` is a string, try ``pandas.read_table``
    5. Try initializing a ``pandas.DataFrame`` with block as the first argument
       plus the deserializer's extra args and kwargs
    '''

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        super(DefaultDataFrameDeserializer, self).__init__()

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        import pandas
        if isinstance(block, pandas.DataFrame):
            try:
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)
        if isinstance(block, str):
            for suffix, read_func in (
                    ('.csv', pandas.read_csv),
                    ('.json', pandas.read_json),
                    ('.html', pandas.read_html),
                    ('.xls', pandas.read_excel),
                    ('.h5', pandas.read_hdf),
                    ('.feather', pandas.read_feather),
                    ('.parquet', pandas.read_parquet),
                    ('.msg', pandas.read_msgpack),
                    ('.dta', pandas.read_stata),
                    ('.sas7bdat', pandas.read_sas),
                    ('.pkl', pandas.read_pickle)):
                if block.endswith(suffix):
                    try:
                        block = read_func(block, *self.args, **self.kwargs)
                        parameterized.param.set_param(name, block)
                        return
                    except Exception as e:
                        raise_from(ParamConfigTypeError(
                            parameterized, name), e)
            try:
                block = pandas.read_table(block, *self.args, **self.kwargs)
                parameterized.param.set_param(name, block)
                return
            except Exception as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)
        try:
            block = pandas.DataFrame(data=block, **kwargs)
            parameterized.param.set_param(name, block)
            return
        except Exception as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


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
    '''Default datetime deserializer

    The process:
    1. None check
    2. If `block` is a ``datetime.datetime``, set it
    3. If the deserializer's `format` argument is not None and `block` is a
       string:
       1. If `format` is a string, try to convert `block` to a datetime using
          ``datetime.datetime.strptime()``
       2. If `format` is list-like, parse a ``datetime.datetime`` object
          with ``datetime.datetime.strptime(element, format)``. If the parse
          is successful, use that parsed datetime.
    4. Try casting `block` to a float
       1. If the float has a remainder or the value exceeds the maximum
          ordinal value, treat as a timestamp
       2. Otherwise, treat as a Gregorian ordinal time
    5. Try instantiating a datetime with `block` as an argument to the
       constructor.
    6. If ``numpy`` can be imported, try instantiating a ``numpy.datetime64``
       with `block` as an argument to the constructor.
    '''

    def __init__(
            self,
            format=('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d')):
        super(DefaultDateDeserializer, self).__init__()
        self.format = format

    def deserialize(self, name, block, parameterized):
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
                block = datetime.fromtimestamp(float_block)
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
            parameterized, name,
            'cannot convert "{}" to datetime'.format(block))


class DefaultDateRangeDeserializer(ParamConfigDeserializer):
    '''Default date range deserializer

    Similar to deserializing a single `datetime`, but applied to each element
    separately. Cast to a tuple.
    '''

    def __init__(
            self,
            format=('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d')):
        super(DefaultDateRangeDeserializer, self).__init__()
        self.format = format

    def deserialize(self, name, block, parameterized):
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
                    elem = datetime.fromtimestamp(float_elem)
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
                parameterized, name,
                'cannot convert "{}" from "{}" to datetime'.format(
                    elem, block))
        val = tuple(val)
        try:
            parameterized.param.set_param(name, val)
        except ValueError:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultListDeserializer(ParamConfigDeserializer):
    '''Default list deserializer

    The process:
    1. None check
    2. If the parameter's ``class_`` attribute has been set, for each
       element in `block` (we always assume `block` is iterable):
       1. If the element is an instance of the class, leave it alone
       2. Try instantiating a ``class_`` object using the element
          as the first argument plus any arguments or keyword arguments
          passed to the deserializer on initialization.
    3. Cast to a list and set
    '''

    def __init__(self, *args, **kwargs):
        super(DefaultListDeserializer, self).__init__()
        self.args = args
        self.kwargs = kwargs

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        p = parameterized.params()[name]
        try:
            if p.class_:
                block = [
                    x if isinstance(x, p.class_) else p.class_(
                        x, *self.args, **self.kwargs)
                    for x in block
                ]
            else:
                block = list(block)
            parameterized.param.set_param(name, block)
        except (TypeError, ValueError) as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultListSelectorDeserializer(ParamConfigDeserializer):
    '''Default ListSelector deserializer

    For each element in `block` (we assume `block` is iterable), match a
    value or name in the selector's ``get_range()`` method
    '''

    def deserialize(self, name, block, parameterized):
        # a list selector cannot be none, only empty. Therefore, no "None"
        # checks
        try:
            block = [
                _find_object_in_object_selector(name, x, parameterized)
                for x in block
            ]
            parameterized.param.set_param(name, block)
        except TypeError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class _CastDeserializer(ParamConfigDeserializer):
    '''Default {0} deserializer

    The process:
    1. None check
    2. If `block` is a(n) {0}, set it
    3. Initialize a(n) {0} instance with `block` as the first argument
       plus any extra positional or keyword arguments passed to the
       deserializer on initialization
    '''

    def __init__(self, *args, **kwargs):
        super(_CastDeserializer, self).__init__()
        self.args = args
        self.kwargs = kwargs

    @classmethod
    def class_(cls, x, *args, **kwargs):
        raise NotImplementedError(
            "class_ must be specified in definition of {}".format(cls))

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        try:
            if not isinstance(block, self.class_):
                block = self.class_(block, *self.args, **self.kwargs)
            parameterized.param.set_param(name, block)
            return
        except ValueError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultIntegerDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format('int')
    class_ = int


class DefaultNumberDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format('float')
    class_ = float


class DefaultNumericTupleDeserializer(ParamConfigDeserializer):
    '''Default numeric tuple deserializer

    The process:
    1. None check
    2. Cast each element of `block` to a ``float``
    3. Cast `block` to a ``tuple``
    '''

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        try:
            block = tuple(float(x) for x in block)
            parameterized.param.set_param(name, block)
            return
        except ValueError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultObjectSelectorDeserializer(ParamConfigDeserializer):
    '''Default ObjectSelector deserializer

    The process:
    1. None check
    2. Match `block` to a value or name in the selector's ``get_range()``
       method
    '''

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        block = _find_object_in_object_selector(name, block, parameterized)
        parameterized.param.set_param(name, block)


class DefaultSeriesDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format('pandas.Series')

    @property
    def class_(self):
        import pandas
        return pandas.Series


class DefaultStringDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format('str')
    class_ = str


class DefaultTupleDeserializer(_CastDeserializer):
    __doc__ = _CastDeserializer.__doc__.format('tuple')
    class_ = tuple


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


def _deserialize_from_dict_flat(
        dict_, parameterized, deserializer_name_dict,
        deserializer_type_dict, on_missing):
    if deserializer_type_dict is not None:
        deserializer_type_dict2 = dict(DEFAULT_DESERIALIZER_DICT)
        deserializer_type_dict2.update(deserializer_type_dict)
        deserializer_type_dict = deserializer_type_dict2
    else:
        deserializer_type_dict = DEFAULT_DESERIALIZER_DICT
    if deserializer_name_dict is None:
        deserializer_name_dict = dict()
    for name, block in dict_.items():
        if name not in parameterized.params():
            msg = 'No param "{}" to set in "{}"'.format(
                name, parameterized.name)
            if on_missing == 'warn':
                parameterized.warning(msg)
            elif on_missing == 'raise':
                raise ValueError(msg)
            continue
        if name in deserializer_name_dict:
            deserializer = deserializer_name_dict[name]
        else:
            type_ = type(parameterized.params()[name])
            if type_ in deserializer_type_dict:
                deserializer = deserializer_type_dict[type_]
            else:
                deserializer = DEFAULT_BACKUP_DESERIALIZER
        deserializer.deserialize(name, block, parameterized)


def deserialize_from_dict(
        dict_, parameterized,
        deserializer_name_dict=None, deserializer_type_dict=None,
        on_missing='warn'):
    '''Deserialize a dictionary into a parameterized object

    This function is suitable for deserializing the results of parsing
    a data storage file such as a YAML, JSON, or a section of an INI file
    (using the `yaml`, `json`, and `configparser` python modules, resp.)
    into a `param.Parameterized` object. Each key in `dict_` should match
    the name of a parameter in `parameterized`. The parameter will be
    deserialized into `parameterized` using a `ParamConfigDeserializer` object
    matched with the following precedent:

     1. If `deserializer_name_dict` is specified and contains the same key,
        the value of the item in `deserializer_name_dict` will be used.
     2. If `deserializer_type_dict` and the type of the parameter in question
        *exactly matches* a key in `deserializer_type_dict`, the value of the
        item in `deserializer_type_dict` will be used.
     3. If the type of the parameter in question *exactly matches* a key in
        `DEFAULT_DESERIALIZER_DICT`, the value of the item in
        `DEFAULT_DESERIALIZER_DICT` will be used.
     4. `DEFAULT_BACKUP_DESERIALIZER` will be used.

    It is possible to pass a dictionary as `parameterized` instead of a
    ``param.Parameterized`` instance to this function. This is "hierarchical
    mode". The values of `parameterized` can be ``param.Parameterized`` objects
    or nested dictionaries. In this case, `dict_`, `deserializer_name_dict`,
    and `deserializer_type_dict` are expected to be dictionaries with the same
    hierarchical structure (though the latter two can still be ``None``,
    which propagates to children). The leaves of `dict_` deserialize into the
    leaves of `parameterized`, using the leaves of `deserializer_name_dict` and
    `deserializer_type_dict` as arguments. If no leaf of `dict_` exists for
    a given `parameterized` leaf, that parameterized object will not be
    updated.

    Default deserializers are likely appropriate for basic types like strings,
    ints, bools, floats, and numeric tuples. For more complex data types,
    including recursive `param.Parameterized` instances, custom deserializers
    are recommended.

    Parameters
    ----------
    dict_ : dict
    parameterized : param.Parameterized or dict
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
        What to do if the parameterized instance does not have a parameter
        listed in `dict_`, or, in the case of "hierarchical mode", if
        `dict_` contains a key with no matching parameterized object to
        populate

    Raises
    ------
    ParamConfigTypeError
        If deserialization of a value fails
    '''
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
                        'dict_ contains hierarchical key chain {} but no '
                        'parameterized instance to match it'
                    ).format(n_stack[-1])
                    if on_missing == 'raise':
                        raise ValueErro(msg)
                    elif on_missing == 'warn':
                        # FIXME(sdrobert): do something involving param
                        import warnings
                        warnings.warn(msg)
                    continue
                d_stack.append(d[name])
                p_stack.append(p_name)
                if dnd is None:
                    dnd_stack.append(None)
                else:
                    dnd_stack.append(dnd[name])
                if dtd is None:
                    dtd_stack.append(None)
                else:
                    dtd_stack.append(dtd[name])


YAML_MODULE_PRIORITIES = ('ruamel.yaml', 'ruamel_yaml', 'pyyaml')


def _deserialize_from_ini_fp(
        fp, parameterized,
        deserializer_name_dict, deserializer_type_dict, on_missing,
        defaults, comment_prefixes, inline_comment_prefixes,
        one_param_section):
    try:
        from ConfigParser import SafeConfigParser
        parser = SafeConfigParser(default=defaults)
    except ImportError:
        from configparser import ConfigParser
        parser = ConfigParser(
            defaults=defaults,
            comment_prefixes=comment_prefixes,
            inline_comment_prefixes=inline_comment_prefixes,
        )
    if one_param_section is None:
        one_param_section = parser.default_section
    try:
        parser.read_file(fp)
    except AttributeError:
        parser.readfp(fp)
    if isinstance(parameterized, param.Parameterized):
        parser = parser[one_param_section]
    deserialize_from_dict(
        parser, parameterized,
        deserializer_name_dict=deserializer_name_dict,
        deserializer_type_dict=deserializer_type_dict,
        on_missing=on_missing)


def deserialize_from_ini(
        file, parameterized,
        deserializer_name_dict=None,
        deserializer_type_dict=None,
        on_missing='warn',
        defaults=None,
        comment_prefixes=('#', ';'),
        inline_comment_prefixes=(';',),
        one_param_section=None):
    '''Deserialize an INI (config) file into a parameterized instance

    `.INI syntax <https://en.wikipedia.org/wiki/INI_file>`, also including
    `interpolation
    <https://docs.python.org/3.7/library/configparser.html>`. This function
    converts an INI file to a dictionary, then populates `parameterized` with
    the contents of this dictionary.

    INI files are broken up into sections; all key-value
    pairs must belong to a section. If `parameterized` is a
    ``param.Parameterized`` instance (rather than a hierarchical dictionary of
    them), the action will try to deserialize the section specified by
    `one_param_section` keyword argument

    Paramters
    ---------
    file : file pointer or str
        The INI file to deserialize from. Can be a pointer or a path
    parameterized : param.Parameterized or dict
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
    defaults : dict, optional
        Default key-values used in interpolation (substitution). Terms such
        as ``(key)%s`` (like a python 2.7 format string) are substituted with
        these values
    comment_prefixes : sequence, optional
        A sequence of characters that indicate a full-line comment in the INI
        file. Ignored in python 2.7
    inline_comment_prefixes : sequence, optional
        A sequence of characters that indicate an inline (including full-line)
        comment in the INI file. Ignored in python 2.7
    one_param_section : str or None, optional
        If `parameterized` refers to a single ``param.Parameterized`` instance,
        this keyword is used to indicate which section of the INI file will
        be deserialized. If ``None``, the INI file's default section
        (``"DEFAULT"``) will be used

    See Also
    --------
    deserialize_from_dict : A description of the deserialization process and
        the parameters to this function
    '''
    if isinstance(file, str):
        with open(file) as fp:
            _deserialize_from_ini_fp(
                fp, parameterized,
                deserializer_name_dict, deserializer_type_dict, on_missing,
                defaults, comment_prefixes, inline_comment_prefixes,
                one_param_section)
    else:
        _deserialize_from_ini_fp(
            file, parameterized,
            deserializer_name_dict, deserializer_type_dict, on_missing,
            defaults, comment_prefixes, inline_comment_prefixes,
            one_param_section)


def _deserialize_from_yaml_fp(
        fp, parameterized,
        deserializer_name_dict, deserializer_type_dict, on_missing):
    yaml = None
    for name in YAML_MODULE_PRIORITIES:
        if name == 'ruamel.yaml':
            try:
                from ruamel.yaml import YAML
                yaml = YAML()
            except ImportError:
                pass
        elif name == 'ruamel_yaml':
            try:
                from ruamel_yaml import YAML
                yaml = YAML()
            except ImportError:
                pass
        elif name == 'pyyaml':
            try:
                import yaml
            except ImportError:
                pass
        else:
            raise ValueError(
                "Invalid value in YAML_MODULE_PRIORITIES: {}".format(name))
    if yaml is None:
        raise ImportError(
            'Could not import any of {} for YAML deserialization'.format(
                YAML_MODULE_PRIORITIES))
    dict_ = yaml.load(fp)
    deserialize_from_dict(
        dict_, parameterized,
        deserializer_name_dict=deserializer_name_dict,
        deserializer_type_dict=deserializer_type_dict,
        on_missing=on_missing)


def deserialize_from_yaml(
        file, parameterized,
        deserializer_name_dict=None,
        deserializer_type_dict=None, on_missing='warn'):
    '''Deserialize a YAML file into a parameterized instance

    `YAML syntax <https://en.wikipedia.org/wiki/YAML>`. This function converts
    a YAML file to a dictionary, then populates `parameterized` with the
    contents of this dictionary

    Paramters
    ---------
    file : file pointer or str
        The YAML file to deserialize from. Can be a pointer or a path
    parameterized : param.Parameterized or dict
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional

    See Also
    --------
    deserialize_from_dict : A description of the deserialization process and
        the parameters to this function

    Notes
    -----
    This function tries to use the YAML (de)serialization module to load the
    YAML file in the order listed in
    ``pydrobert.param.serialization.YAML_MODULE_PRIORITIES``, falling back on
    the next if there's an ``ImportError``. Only ``"ruamel.yaml"``,
    ``"ruamel_yaml"``, and "``pyyaml``" are supported constants in
    ``YAML_MODULE_PRIORITIES``
    '''
    if isinstance(file, str):
        with open(file) as fp:
            _deserialize_from_yaml_fp(
                fp, parameterized,
                deserializer_name_dict, deserializer_type_dict, on_missing)
    else:
        _deserialize_from_yaml_fp(
            file, parameterized,
            deserializer_name_dict, deserializer_type_dict, on_missing)


def _deserialize_from_json_fp(
        fp, parameterized,
        deserializer_name_dict, deserializer_type_dict, on_missing):
    import json
    dict_ = json.load(fp)
    deserialize_from_dict(
        dict_, parameterized,
        deserializer_name_dict=deserializer_name_dict,
        deserializer_type_dict=deserializer_type_dict,
        on_missing=on_missing)


def deserialize_from_json(
        file, parameterized,
        deserializer_name_dict=None,
        deserializer_type_dict=None, on_missing='warn'):
    '''Deserialize a YAML file into a parameterized instance

    `JSON syntax <https://en.wikipedia.org/wiki/JSON>`. This function converts
    a JSON file to a dictionary, then populates `parameterized` with the
    contents of this dictionary

    Paramters
    ---------
    file : file pointer or str
        The JSON file to deserialize from. Can be a pointer or a path
    parameterized : param.Parameterized or dict
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional

    See Also
    --------
    deserialize_from_dict : A description of the deserialization process and
        the parameters to this function
    '''
    if isinstance(file, str):
        with open(file) as fp:
            _deserialize_from_json_fp(
                fp, parameterized,
                deserializer_name_dict, deserializer_type_dict, on_missing)
    else:
        _deserialize_from_json_fp(
            file, parameterized,
            deserializer_name_dict, deserializer_type_dict, on_missing)
