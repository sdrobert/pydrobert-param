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


class ParamsA(param.Parameterized):
    bingo = param.String(None)
    bango = param.Number(None)
    bongo = param.List(None)


class ParamsB(param.Parameterized):
    object_selector = param.ObjectSelector(None, objects=[1, '2'])
    dont_try_this = param.Callable(None)


class CommaListDeserializer(object):
    def deserialize(self, name, block, parameterized):
        block = block.split(',')
        parameterized.param.set_param(name, block)


def test_ini_action():
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        action=pargparse.ParameterizedIniConfigAction,
        type=ParamsA,
        deserializer_type_dict={param.List: CommaListDeserializer()},
    )
    parsed = parser.parse_args([os.path.join(FILE_DIR, 'param.ini')])
    assert parsed.zoo.bingo == 'a'
    assert parsed.zoo.bango == 1
    assert parsed.zoo.bongo == ['b', 'a', 'd']
    parser = ArgumentParser()
    parser.add_argument(
        'zoo',
        action=pargparse.ParameterizedIniConfigAction,
        parameterized={'params_b': ParamsB()},
        deserializer_type_dict={param.List: CommaListDeserializer()},
    )
    parsed = parser.parse_args([os.path.join(FILE_DIR, 'param.ini')])
    assert parsed.zoo['params_b'].object_selector == 1
