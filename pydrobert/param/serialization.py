'''Utilities for (de)serializing param.Parameterized objects'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc

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


class ParamConfigDeserializer(with_metaclass(object, abc.ABCMeta)):
    '''Deserialize part of a configuration into a parameter object'''

    def __init__(self, parameterized):
        super(ParamConfigDeserializer, self).__init__()
        self.parameterized = parameterized

    @abc.abstractmethod
    def deserialize(self, name, block):
        pass

    def check_if_allow_none_and_set(self, name, block):
        p = self.parameterized.params()[name]
        if (block is None or block == 'None') and p.allow_None:
            self.parameterized.param.set_param(name, None)
            return True
        else:
            return False


class DefaultDeserializer(ParamConfigDeserializer):

    def deserialize(self, name, block):
        if self.check_if_allow_none_and_set(name, block):
            return
        try:
            self.parameterized.set_param(name, block)
        except ValueError as e:
            raise_from(ParamConfigTypeError(self.parameterized, name), e)


class DefaultArrayDeserializer(ParamConfigDeserializer):

    def __init__(self, parameterized, sep=' '):
        self.sep = sep
        super(DefaultArrayDeserializer, self).__init__(parameterized)

    def deserialize(self, name, block):
        if self.check_if_allow_none_and_set(name, block):
            return
        import numpy as np
        if isinstance(block, np.ndarray):
            self.parameterized.param.set_param(name, block)
            return
        try:
            block = np.fromstring(block, sep=self.sep)
        except ValueError as e:
            raise_from(ParamConfigTypeError(self.parameterized, name), e)
        self.parameterized.param.set_param(name, block)


class DefaultBooleanDeserializer(ParamConfigDeserializer):

    def deserialize(self, name, block):
        if self.check_if_allow_none_and_set(name, block):
            return
        if block in {
                'True', 'true', 't', 'on', 'TRUE', 'T', 'ON', 'yes',
                'YES'}:
            block = True
        elif block in {
                'False', 'false', 'f', 'off', 'FALSE', 'F', 'OFF',
                'no', 'NO'}:
            block = False
        if block in {True, False}:
            self.parameterized.param.set_param(name, block)
        else:
            raise ParamConfigTypeError(
                self.parameterized, name,
                'cannot convert "{}" to bool'.format(block))


class DefaultDataFrameDeserializer(ParamConfigDeserializer):

    def __init__(self, parameterized, **kwargs):
        self.kwargs = kwargs
        super(DefaultDataFrameDeserializer, self).__init__(parameterized)

    def deserialize(self, name, block):
        if self.check_if_allow_none_and_set(name, block):
            return
        import pandas
        for f in (
                pandas.read_table, pandas.read_csv, pandas.read_fwf,
                pandas.read_msgpack, pandas.read_excel, pandas.read_json,
                pandas.read_html, pandas.read_hdf, pandas.read_feather,
                pandas.read_parquet, pandas.read_sas, pandas.read_stata,):
            try:
                block = f(block, **self.kwargs)
                self.parameterized.param.set_param(name, block)
                return
            except Exception:
                pass
        raise ParamConfigTypeError(
            self.parameterized, name,
            'cannot convert "{}" to bool'.format(block))
