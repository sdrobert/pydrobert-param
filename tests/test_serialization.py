"""Tests for pydrobert.param.serialization"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from datetime import datetime

import pytest
import param
import numpy as np
import pandas as pd
import pydrobert.param.serialization as serial

FILE_DIR = os.path.dirname(os.path.realpath(__file__))


def default_action():
    return 1


def another_action():
    return 2


class CallableObject(object):

    def __init__(self, val=2):
        self.val = val

    def __call__(self):
        return self.val

    def __eq__(self, other):
        return self.val == other.val

    def __repr__(self):
        return 'CallableObject({})'.format(self.val)


class SpecialInt(int):
    pass


class BigDumbParams(param.Parameterized):
    action = param.Action(default_action, allow_None=True)
    array = param.Array(np.array([1., 2.]))
    boolean = param.Boolean(True, allow_None=True)
    callable = param.Callable(default_action, allow_None=True)
    class_selector = param.ClassSelector(
        int, is_instance=False, allow_None=True)
    color = param.Color('#FFFFFF', allow_None=True)
    composite = param.Composite(['action', 'array'], allow_None=True)
    data_frame = param.DataFrame(pd.DataFrame({'A': 1., 'B': np.arange(5)}))
    date = param.Date(datetime.now(), allow_None=True)
    date_range = param.DateRange((datetime.min, datetime.max), allow_None=True)
    dict_ = param.Dict({'foo': 'bar'}, allow_None=True)
    dynamic = param.Dynamic(default=default_action, allow_None=True)
    file_selector = param.FileSelector(
        "LICENSE",
        path=os.path.join(os.path.dirname(FILE_DIR), '*'),
        allow_None=True,
    )
    filename = param.Filename(FILE_DIR + "/../LICENSE", allow_None=True)
    foldername = param.Foldername(FILE_DIR + "/..", allow_None=True)
    hook_list = param.HookList(
        [CallableObject(), CallableObject()], class_=CallableObject,
        allow_None=True)
    integer = param.Integer(10, allow_None=True)
    list_ = param.List([1, 2, 3], allow_None=True, class_=int)
    list_selector = param.ListSelector(
        [2, 2], objects=[1, 2, 3], allow_None=True)
    magnitude = param.Magnitude(.5, allow_None=True)
    multi_file_selector = param.MultiFileSelector(
        ["LICENSE", "README.md"],
        path=os.path.join(os.path.dirname(FILE_DIR), '*'),
        allow_None=True
    )
    number = param.Number(-10., allow_None=True)
    numeric_tuple = param.NumericTuple((5., 10.), allow_None=True)
    object_selector = param.ObjectSelector(
        False, objects={'False': False, 'True': 1}, allow_None=True)
    path = param.Path(FILE_DIR + "/../LICENSE", allow_None=True)
    range_ = param.Range((-1., 2.), allow_None=True)
    series = param.Series(pd.Series(range(5)))
    string = param.String("foo", allow_None=True)
    tuple_ = param.Tuple((3, 4, 'fi'), allow_None=True)
    x_y_coordinates = param.XYCoordinates((1., 2.), allow_None=True)


@pytest.mark.parametrize('block', [None, 'None'])
def test_can_deserialize_none(block):
    parameterized = BigDumbParams(name='test_can_deserialize_none')
    for name, p in parameterized.params().items():
        if name in {
                'name', 'composite', 'list_selector', 'multi_file_selector',
                'color'}:
            continue
        assert p.allow_None
        if type(p) in serial.DEFAULT_DESERIALIZER_DICT:
            deserializer = serial.DEFAULT_DESERIALIZER_DICT[type(p)]
        else:
            deserializer = serial.DEFAULT_BACKUP_DESERIALIZER
        deserializer.deserialize(name, block, parameterized)
        assert getattr(parameterized, name) is None


@pytest.mark.parametrize('name,block,expected', [
    ('action', another_action, another_action),
    ('array', np.array([1, 2]), np.array([1, 2])),
    ('array', [3, 4], np.array([3, 4])),
    ('boolean', True, True),
    ('boolean', 'yes', True),
    ('boolean', 'False', False),
    ('callable', another_action, another_action),
    ('class_selector', SpecialInt, SpecialInt),
    ('class_selector', int, int),
    ('class_selector', 'int', int),
    ('color', '#000000', '#000000'),
    ('color', '#111111', '#111111'),
    (
        'data_frame',
        pd.DataFrame({'foo': [1, 2]}),
        pd.DataFrame({'foo': [1, 2]}),
    ),
    (
        'data_frame',
        FILE_DIR + '/pandas_data_frame.csv',
        pd.DataFrame({'foo': [1., 3.], 'bar': [2., 4.]}),
    ),
    ('date', datetime(2020, 10, 2).timestamp(), datetime(2020, 10, 2)),
    ('date', datetime(2030, 1, 8).toordinal(), datetime(2030, 1, 8)),
    (
        'date_range',
        (datetime(1914, 7, 14), datetime(1918, 11, 11)),
        (datetime(1914, 7, 14), datetime(1918, 11, 11)),
    ),
    ('dict_', {'a': 1, 'b': 'howdy'}, {'a': 1, 'b': 'howdy'}),
    ('dynamic', another_action, another_action()),
    ('file_selector', 'README.md', 'README.md'),
    (
        'filename',
        os.path.join(FILE_DIR, 'test_serialization.py'),
        os.path.join(FILE_DIR, 'test_serialization.py'),
    ),
    ('foldername', FILE_DIR, FILE_DIR),
    ('hook_list', [CallableObject(3)], [CallableObject(3)]),
    ('integer', '-45', -45),
    ('integer', 10, 10),
    ('list_', [10, 4, 2], [10, 4, 2]),
    ('list_selector', [1, '3'], [1, 3]),
    ('magnitude', '1e-5', 1e-5),
    (
        'multi_file_selector',
        ['setup.py', 'LICENSE'],
        [
            os.path.join(os.path.dirname(FILE_DIR), x)
            for x in ('setup.py', 'LICENSE')
        ],
    ),
    ('number', '1e10', 1e10),
    ('numeric_tuple', ['5', 3.14], (5, 3.14)),
    ('object_selector', 'True', 1),
    ('object_selector', False, False),
    (
        'path',
        os.path.join(FILE_DIR, 'test_serialization.py'),
        os.path.join(FILE_DIR, 'test_serialization.py'),
    ),
    ('range_', ('-10', 4), (-10., 4.)),
    ('series', pd.Series([1, 2, 3]), pd.Series([1, 2, 3])),
    ('string', 1, '1'),
    ('tuple_', [another_action, True, 1], (another_action, True, 1)),
    ('x_y_coordinates', (0, float('inf')), (0, float('inf'))),
])
def test_can_deserialize_with_defaults(name, block, expected):
    parameterized = BigDumbParams(name='test_can_deserialize_with_defaults')
    p = parameterized.params()[name]
    if type(p) in serial.DEFAULT_DESERIALIZER_DICT:
        deserializer = serial.DEFAULT_DESERIALIZER_DICT[type(p)]
    else:
        deserializer = serial.DEFAULT_BACKUP_DESERIALIZER
    deserializer.deserialize(name, block, parameterized)
    if type(expected) in {np.ndarray, pd.DataFrame, pd.Series}:
        assert all(expected == getattr(parameterized, name))
    else:
        assert expected == getattr(parameterized, name)


def test_deserialize_dict():
    parameterized = BigDumbParams(name='test_deserialize_dict')
    dict_ = {
        'array': [1, 2, 3],
        'filename': os.path.join(FILE_DIR, 'test_serialization.py'),
        'list_': [3, 4, 5],
        'x_y_coordinates': ('3.4', '5'),
    }
    serial.deserialize_from_dict(dict_, parameterized)
    assert np.allclose(parameterized.array, [1, 2, 3])
    assert parameterized.filename == os.path.join(
        FILE_DIR, 'test_serialization.py')
    assert np.allclose(parameterized.list_, [3, 4, 5])
    assert np.allclose(parameterized.x_y_coordinates, (3.4, 5.))

    class _DontCallThis(object):

        def deserialize(self, *args):
            assert False

    class _ThisIsFine(object):

        def deserialize(self, name, block, parameterized):
            parameterized.param.set_param(name, another_action)

    class _AlsoFine(object):

        def deserialize(self, name, block, parameterized):
            parameterized.param.set_param(name, datetime.min)
    type_dict = {
        param.Dynamic: _DontCallThis(),
        param.Date: _AlsoFine(),
    }
    name_dict = {
        'dynamic': _ThisIsFine(),
    }
    dict_['dynamic'] = lambda: -4
    dict_['date'] = datetime.max
    serial.deserialize_from_dict(dict_, parameterized, name_dict, type_dict)
    assert parameterized.dynamic == another_action()
    assert parameterized.date == datetime.min
