'''Utilities for (de)serializing param.Parameterized objects'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc

from builtins import bytes

import param

from future.utils import with_metaclass, raise_from

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2018 Sean Robertson"


class ParamConfigTypeError(TypeError):
    '''Raised when failed to (de)serialize Parameterized object'''

    def __init__(self, parameterized, name, message=''):
        super(ParamConfigTypeError, self).__init__(
            '{}.{}: {}'.format(parameterized.name, name, message)
        )


class ParamConfigDeserializer(with_metaclass(abc.ABCMeta, object)):
    '''Deserialize part of a configuration into a parameter object

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
            The name of the parameter in `parameterized` to store the value
            under
        block : object
            The data to deserialize into the parameter value
        parameterized : param.Parameterized
            The parameterized instance containing a parameter with the name
            `name`. On completion of this method, that parameter will be set
            with the deserialized contents of `block`

        Raises
        ------
        ParamConfigTypeError
            If deserialization could not be performed
        '''
        pass

    @classmethod
    def check_if_allow_none_and_set(cls, name, block, parameterized):
        '''Check if block can be made none and set it if parameter allows it

        Many ```param.Param`` parameters allow ``None`` as a value. This is a
        convenience method that deserializers can use to quickly check for
        a ``None`` value and set it in that case. This method sets the
        parameter and returns ``True`` in the following conditions

        1. The parameter allows ``None`` values (the ``allow_None`` attribute
           is ``True``)
        2. One of:
           1. `block` is ``None``
           2. `block` is a string matching ``"None"`` or ``"none"``

        If one of these conditions wasn't met, the parameter remains unset and
        the method returns ``False``.

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
    if block in named_objs.values():
        return block
    elif block in named_objs:
        return named_objs[block]
    else:
        raise ParamConfigTypeError(
            parameterized, name,
            'Cannot find {} in {}'.format(block, named_objs.keys()))


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


class DefaultDateDeserializer(ParamConfigDeserializer):
    '''Default datetime deserializer

    This deserializer accepts a format string as a keyword argument to the
    constructor.

    The process:
    1. None check
    2. If `block` is a ``datetime.datetime``, set it
    3. If the deserializer's `format` string is not none and `block` is a
       string, try to convert `block` to a datetime using
       ``datetime.datetime.strptime()``
    4. Try casting `block` to a float
       1. If the float has a remainder or the value exceeds the maximum
          ordinal value, treat as a timestamp
       2. Otherwise, treat as a Gregorian ordinal time
    5. Try instantiating a datetime with `block` as an argument to the
       constructor.
    6. If ``numpy`` can be imported, try instantiating a ``numpy.datetime64``
       with `block` as an argument to the constructor.
    '''

    def __init__(self, format='%m-%d-%y %H:%M:%S'):
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
            try:
                block = datetime.strptime(block, self.format)
                parameterized.param.set_param(name, block)
                return
            except ValueError as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)
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

    The process:
    1. None check
    2. For each element in `block` (we assume `block` is iterable),
       match a value or name in the selector's ``get_range()`` method
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

    Default deserializers are likely appropriate for basic types like strings,
    ints, bools, floats, and numeric tuples. For more complex data types,
    including recursive `param.Parameterized` instances, custom deserializers
    are recommended.

    Parameters
    ----------
    dict_ : dict
    parameterized : param.Parameterized
    deserializer_name_dict : dict, optional
    deserializer_type_dict : dict, optional
    on_missing : {'ignore', 'warn', 'raise'}, optional
        What to do if the parameterized instance does not have a parameter
        listed in `dict_`

    Raises
    ------
    ParamConfigTypeError
        If deserialization of a value fails
    '''
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
