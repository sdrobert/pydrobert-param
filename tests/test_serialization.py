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


def BigDumbParams(name=None):
    # why this layer of indirection? Setting some values improperly can change
    # the behaviour of the parameters (which belong to the class). This
    # ensures they reset each initialization.
    class _BigDumbParams(param.Parameterized):
        action = param.Action(default_action, allow_None=True)
        array = param.Array(np.array([1., 2.]))
        boolean = param.Boolean(True, allow_None=True)
        callable = param.Callable(default_action, allow_None=True)
        class_selector = param.ClassSelector(
            int, is_instance=False, allow_None=True)
        color = param.Color('#FFFFFF', allow_None=True)
        composite = param.Composite(['action', 'array'], allow_None=True)
        data_frame = param.DataFrame(
            pd.DataFrame({'A': 1., 'B': np.arange(5)}))
        date = param.Date(datetime.now(), allow_None=True)
        date_range = param.DateRange(
            (datetime.min, datetime.max), allow_None=True)
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
            [],
            path=os.path.join(os.path.dirname(FILE_DIR), '*'),
            allow_None=True,
            check_on_set=True,
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
    return _BigDumbParams(name=name)


@pytest.mark.parametrize('name,set_to,expected', [
    ('action', another_action, another_action),
    ('array', np.array([[1, 2], [3, 4]]), [[1, 2], [3, 4]]),
    ('boolean', True, True),
    ('callable', another_action, another_action),
    ('class_selector', SpecialInt, "SpecialInt"),
    ('class_selector', int, 'int'),
    ('color', '000000', '000000'),
    (
        'data_frame',
        pd.DataFrame({'a': 'foo', 'b': [1, 2, 3]}),
        [['foo', 1], ['foo', 2], ['foo', 3]],
    ),
    ('date', datetime(1945, 8, 15), '1945-08-15'),
    ('date', datetime(1945, 8, 15, 0, 1), '1945-08-15T00:01:00'),
    ('date', datetime(1945, 8, 15, 0, 0, 0, 1), '1945-08-15T00:00:00.000001'),
    (
        'date_range',
        (datetime(11, 11, 11, 11), datetime(12, 12, 12, 12)),
        ['0011-11-11T11:00:00', '0012-12-12T12:00:00'],
    ),
    ('dict_', {'a': {'a': 1}}, {'a': {'a': 1}}),
    # FIXME(sdrobert): what to do with dynamic?
    ('file_selector', 'README.md', 'README.md'),
    (
        'filename',
        os.path.join(FILE_DIR, 'test_argparse.py'),
        os.path.join(FILE_DIR, 'test_argparse.py'),
    ),
    ('foldername', FILE_DIR, FILE_DIR),
    ('hook_list', [CallableObject(4)], [CallableObject(4)]),
    ('integer', 5, 5),
    ('list_', [1, 2, 3], [1, 2, 3]),
    ('list_selector', [2, 1, 2], ['2', '1', '2']),
    ('magnitude', 0.33, 0.33),
    (
        'multi_file_selector',
        [os.path.join(os.path.dirname(FILE_DIR), 'README.md')],
        ['README.md']
    ),
    ('number', 1.2, 1.2),
    ('numeric_tuple', (1., 2.), [1., 2.]),
    ('object_selector', 1, 'True'),
    ('range_', (-1, 1), [-1., 1.]),
    ('string', 'foo', 'foo'),
    ('tuple_', (None, None, None), [None, None, None]),
    ('x_y_coordinates', (10., 4.), [10., 4.]),
])
def test_can_serialize_with_defaults(name, set_to, expected):
    parameterized = BigDumbParams(name='test_can_serialize_with_defaults')
    parameterized.param.set_param(name, set_to)
    p = parameterized.params()[name]
    if type(p) in serial.DEFAULT_SERIALIZER_DICT:
        serializer = serial.DEFAULT_SERIALIZER_DICT[type(p)]
    else:
        serializer = serial.DEFAULT_BACKUP_SERIALIZER
    actual = serializer.serialize(name, parameterized)
    if type(expected) in {np.ndarray, pd.DataFrame, pd.Series}:
        assert all(expected == actual)
    else:
        assert expected == actual


def test_serialize_to_dict():
    parameterized_a = BigDumbParams(name='test_serialize_to_dict_a')
    parameterized_a.number = 5.
    parameterized_a.date = datetime(1, 2, 3, 4, 5)
    parameterized_b = BigDumbParams(name='test_serialize_to_dict_b')
    dict_ = serial.serialize_to_dict(parameterized_a, only={'number', 'date'})
    assert dict_ == {'number': 5., 'date': '0001-02-03T04:05:00'}
    parameterized_b.number = 4.

    class _StupidNumberSerializer(serial.ParamConfigSerializer):
        def serialize(self, name, parameterized):
            val = getattr(parameterized, name)
            return val - 2.

    class _MyLittleDynamicSerializer(serial.ParamConfigSerializer):
        def serialize(self, name, parameterized):
            return 'electric six'
    dict_ = serial.serialize_to_dict(
        parameterized_b,
        only={'number', 'dynamic'},
        serializer_name_dict={'number': _StupidNumberSerializer()},
        serializer_type_dict={param.Dynamic: _MyLittleDynamicSerializer()},
    )
    assert dict_ == {'number': 2., 'dynamic': 'electric six'}
    dict_ = serial.serialize_to_dict(
        {'a': {'A': parameterized_a}, 'b': {'B': parameterized_b}},
        only={
            'a': {'A': {'number', 'dynamic'}},
            'b': {'B': {'number', 'dynamic'}},
        },
        serializer_name_dict={
            'a': {'A': {'number': _StupidNumberSerializer()}},
            'b': None,
        },
        serializer_type_dict={
            'a': {'A': {
                param.Number: _MyLittleDynamicSerializer(),
                param.Dynamic: _MyLittleDynamicSerializer()
            }},
            'b': {'B': {param.Dynamic: _MyLittleDynamicSerializer()}},
        }
    )
    assert dict_['a']['A'] == {'number': 3., 'dynamic': 'electric six'}
    assert dict_['b']['B'] == {'number': 4., 'dynamic': 'electric six'}


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
    ('date', '2040-10-04', datetime(2040, 10, 4)),
    ('date', '2050-11-05T06:07:08', datetime(2050, 11, 5, 6, 7, 8)),
    ('date', '2060-01-01T00:00:00.000000', datetime(2060, 1, 1)),
    (
        'date_range',
        (datetime(1914, 7, 14), datetime(1918, 11, 11)),
        (datetime(1914, 7, 14), datetime(1918, 11, 11)),
    ),
    (
        'date_range',
        ('1968-01-01', '2001-05-12'),
        (datetime(1968, 1, 1), datetime(2001, 5, 12)),
    ),
    (
        'date_range',
        (1, datetime(9999, 12, 31).toordinal()),
        (datetime.min, datetime(9999, 12, 31)),
    ),
    (
        'date_range',
        (
            datetime(2018, 12, 7, 18, 16, 28, 610366).timestamp(),
            datetime(2018, 12, 7, 18, 16, 38, 466311).timestamp(),
        ),
        (
            datetime(2018, 12, 7, 18, 16, 28, 610366),
            datetime(2018, 12, 7, 18, 16, 38, 466311),
        ),
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


def test_deserialize_from_dict():
    parameterized_a = BigDumbParams(name='test_deserialize_from_dict_a')
    dict_ = {
        'array': [1, 2, 3],
        'filename': os.path.join(FILE_DIR, 'test_serialization.py'),
        'list_': [3, 4, 5],
        'x_y_coordinates': ('3.4', '5'),
    }
    serial.deserialize_from_dict(dict_, parameterized_a)
    assert np.allclose(parameterized_a.array, [1, 2, 3])
    assert parameterized_a.filename == os.path.join(
        FILE_DIR, 'test_serialization.py')
    assert np.allclose(parameterized_a.list_, [3, 4, 5])
    assert np.allclose(parameterized_a.x_y_coordinates, (3.4, 5.))

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
    serial.deserialize_from_dict(dict_, parameterized_a, name_dict, type_dict)
    assert parameterized_a.dynamic == another_action()
    assert parameterized_a.date == datetime.min

    class _HereAreSomeCoordinates(object):
        def deserialize(self, name, block, parameterized):
            parameterized.param.set_param(name, (1., 2.))
    parameterized_b = BigDumbParams(name='test_deserialize_from_dict_b')
    dict_ = {
        'a': {'A': {
            'number': -420.,
            'date': '2018-04-20',
            'x_y_coordinates': 10
        }},
        'b': {'B': dict_},
    }
    name_dict = {
        'a': {'A': {'x_y_coordinates': _HereAreSomeCoordinates()}},
        'b': {'B': name_dict},
    }
    type_dict = {
        'a': None,
        'b': {'B': type_dict},
    }
    serial.deserialize_from_dict(
        dict_,
        {'a': {'A': parameterized_a}, 'b': {'B': parameterized_b}},
        deserializer_name_dict=name_dict,
        deserializer_type_dict=type_dict,
    )
    assert parameterized_b.dynamic == another_action()
    assert parameterized_b.date == datetime.min
    assert parameterized_a.number == -420.
    assert parameterized_a.date == datetime(2018, 4, 20)
    assert parameterized_a.x_y_coordinates == (1., 2.)
