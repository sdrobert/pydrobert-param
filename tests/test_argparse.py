"""Tests for pydrobert.param.argparse"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from argparse import ArgumentParser

import pytest
import param
import pydrobert.param.argparse as pargparse

FILE_DIR = os.path.dirname(os.path.realpath(__file__))


def ParamsA(name=None):
    class _ParamsA(param.Parameterized):
        bingo = param.String(None)
        bango = param.Number(None)
        bongo = param.List(None)
    return _ParamsA(name=name)


def ParamsB(name=None):
    class _ParamsB(param.Parameterized):
        object_selector = param.ObjectSelector(None, objects=[1, '2'])
        dont_try_this = param.Callable(None)
        date_range = param.DateRange(None)
        list_ = param.List(None)
    return _ParamsB(name=name)


class CommaListDeserializer(object):
    def deserialize(self, name, block, parameterized):
        block = block.split(',')
        parameterized.param.set_param(name, block)


def test_ini_read_action():
    parser = ArgumentParser()
    parser.add_argument(
        '--zoo',
        action=pargparse.ParameterizedIniReadAction,
        type=ParamsA,
        nargs='?',
        const=os.path.join(FILE_DIR, 'param.ini'),
        deserializer_type_dict={param.List: CommaListDeserializer()},
    )
    parsed = parser.parse_args(['--zoo'])
    assert parsed.zoo.bingo == 'a'
    assert parsed.zoo.bango == 1
    assert parsed.zoo.bongo == ['b', 'a', 'd']
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        action=pargparse.ParameterizedIniReadAction,
        nargs='+',
        parameterized={'params_b': ParamsB()},
    )
    parsed = parser.parse_args([os.path.join(FILE_DIR, 'param.ini')])
    assert parsed.zoo['params_b'].object_selector == 1
    assert parsed.zoo['params_b'].list_ == [1, 1, 3]


def test_yaml_read_action(yaml_loader):
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        nargs='+',
        action=pargparse.ParameterizedYamlReadAction,
        type=ParamsA,
    )
    parsed = parser.parse_args([
        os.path.join(FILE_DIR, 'param.yaml'),
        os.path.join(FILE_DIR, 'param.yaml')
    ])
    assert parsed.zoo.bingo == 'a'
    assert parsed.zoo.bango == 1
    assert parsed.zoo.bongo == ['b', 1, False]
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        action=pargparse.ParameterizedYamlReadAction,
        parameterized={'params_b': ParamsB()},
    )
    parsed = parser.parse_args([os.path.join(FILE_DIR, 'param.yaml')])
    assert parsed.zoo['params_b'].object_selector == '2'
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        nargs='*',
        action=pargparse.ParameterizedYamlReadAction,
        parameterized={'params_a': ParamsB()},  # mismatch if actually parsed
    )
    parsed = parser.parse_args([])
    assert parsed.zoo['params_a'].object_selector is None


def test_json_read_action():
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        action=pargparse.ParameterizedJsonReadAction,
        type=ParamsA,
    )
    parsed = parser.parse_args([os.path.join(FILE_DIR, 'param.json')])
    assert parsed.zoo.bingo == ""
    assert parsed.zoo.bango == 12
    assert parsed.zoo.bongo == [4, '2', False]
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        nargs='*',
        action=pargparse.ParameterizedJsonReadAction,
        parameterized={'params_b': ParamsB()},
    )
    parsed = parser.parse_args([os.path.join(FILE_DIR, 'param.json')])
    assert parsed.zoo['params_b'].object_selector == 1
