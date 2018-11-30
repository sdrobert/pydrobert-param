'''Utilities for (de)serializing param.Parameterized objects'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc

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
    '''Deserialize part of a configuration into a parameter object'''

    @abc.abstractmethod
    def deserialize(self, name, block, parameterized):
        pass

    @classmethod
    def check_if_allow_none_and_set(cls, name, block, parameterized):
        p = parameterized.params()[name]
        if (
                (
                    block is None or
                    (isinstance(block, str) and (block == 'None'))
                ) and p.allow_None):
            parameterized.param.set_param(name, None)
            return True
        else:
            return False


class DefaultDeserializer(ParamConfigDeserializer):

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        try:
            parameterized.set_param(name, block)
        except ValueError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultArrayDeserializer(ParamConfigDeserializer):

    def __init__(self, sep=' '):
        self.sep = sep
        super(DefaultArrayDeserializer, self).__init__()

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        import numpy as np
        if isinstance(block, np.ndarray):
            parameterized.param.set_param(name, block)
            return
        if isinstance(block, str):
            try:
                block = np.fromstring(block, sep=self.sep)
                parameterized.param.set_param(name, block)
            except ValueError as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)
        else:
            try:
                block = np.array(block)
                parameterized.param.set_param(name, block)
            except ValueError as e:
                raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultBooleanDeserializer(ParamConfigDeserializer):

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


class DefaultClassSelector(ParamConfigDeserializer):

    def __init__(self, *args, **kwargs):
        super(DefaultClassSelector, self).__init__()
        self.args = args
        self.kwargs = kwargs

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        p = parameterized.params()[name]
        try:
            if p.is_instance and not isinstance(block, p.class_):
                block = p.class_(block, *self.args, **self.kwargs)
            parameterized.param.set_param(name, block)
        except ValueError as e:
            raise_from(ParamConfigTypeError(parameterized, name), e)


class DefaultDataFrameDeserializer(ParamConfigDeserializer):

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

    def __init__(self, format=None):
        super(DefaultDateDeserializer, self).__init__()
        self.format = format

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        from datetime import datetime
        if isinstance(block, datetime):
            parameterized.param.set_param(name, block)
            return
        if self.format is not None:
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
        if len(param.dt_types) > 1:
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


class DefaultListSelectorDeserializer(ParamConfigDeserializer):

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
    class_ = int


class DefaultNumberDeserializer(_CastDeserializer):
    class_ = float


class DefaultNumericTupleDeserializer(ParamConfigDeserializer):

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

    def deserialize(self, name, block, parameterized):
        if self.check_if_allow_none_and_set(name, block, parameterized):
            return
        block = _find_object_in_object_selector(name, block, parameterized)
        parameterized.param.set_param(name, block)


class DefaultSeriesDeserializer(_CastDeserializer):

    @property
    def class_(self):
        import pandas
        return pandas.Series


class DefaultStringDeserializer(_CastDeserializer):
    class_ = str


class DefaultTupleDeserializer(_CastDeserializer):
    class_ = tuple


DEFAULT_DESERIALIZER_DICT = {
    param.Array: DefaultArrayDeserializer(),
    param.Boolean: DefaultBooleanDeserializer(),
    param.ClassSelector: DefaultClassSelector(),
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
        deserializer_name_dict=None,
        deserializer_type_dict=None):
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

    Raises
    ------
    ParamConfigTypeError : if deserialization of a value fails
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
        if name in deserializer_name_dict:
            deserializer = deserializer_name_dict[name]
        else:
            type_ = type(parameterized.params()[name])
            if type_ in deserializer_type_dict:
                deserializer = deserializer_type_dict[type_]
            else:
                deserializer = DEFAULT_BACKUP_DESERIALIZER
        deserializer.deserialize(name, block, parameterized)
