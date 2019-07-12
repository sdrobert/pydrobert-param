"""Tests for pydrobert.param.argparse"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

from argparse import ArgumentParser
from collections import OrderedDict

import pytest
import param
import pydrobert.param.argparse as pargparse

try:
    # python 2.7 wants us to write bytes
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

FILE_DIR = os.path.dirname(os.path.realpath(__file__))


def ParamsA(**kwargs):
    class _ParamsA(param.Parameterized):
        bingo = param.String(None)
        bango = param.Number(None)
        bongo = param.List(None)
    return _ParamsA(**kwargs)


def ParamsB(**kwargs):
    class _ParamsB(param.Parameterized):
        object_selector = param.ObjectSelector(None, objects=[1, '2'])
        dont_try_this = param.Callable(None)
        date_range = param.DateRange(None)
        list_ = param.List(None)
    return _ParamsB(**kwargs)


class CommaListDeserializer(object):
    def deserialize(self, name, block, parameterized):
        block = block.split(',')
        parameterized.param.set_param(name, block)


class CommaListSerializer(object):
    def help_string(self, name, parameterized):
        return ""

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        return ','.join([str(x) for x in val])


class ZeroSerializer(object):
    def help_string(self, name, parameterized):
        return ""

    def serialize(self, name, parameterized):
        val = getattr(parameterized, name)
        if val == 0:
            return "zero"
        else:
            return "not zero"


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


def test_ini_print_action():
    parser = ArgumentParser()
    ss = StringIO()
    parser.add_argument(
        '--print',
        action=pargparse.ParameterizedIniPrintAction,
        out_stream=ss,
        type=ParamsA,
    )
    parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(['--print'])
    ss.seek(0)
    assert ss.read().strip() == '''\
# == Help ==
# [DEFAULT]
# bongo: A JSON object


[DEFAULT]
bango
bingo
bongo'''
    ss.seek(0)
    ss.truncate()
    parser = ArgumentParser()
    parameterized = OrderedDict()
    parameterized['params_a'] = ParamsA(bongo=['I', 'am', 'a', 'bongo'])
    parameterized['params_b'] = ParamsB(
        list_=['I', 'am', 'comma-d'], object_selector='2')
    parser.add_argument(
        '--print',
        action=pargparse.ParameterizedIniPrintAction, out_stream=ss,
        parameterized=parameterized,
        only={'params_a': {'bongo'}, 'params_b': {'list_'}},
        include_help=False,
        serializer_name_dict={'params_b': {'list_': CommaListSerializer()}},
    )
    with pytest.raises(SystemExit):
        parser.parse_args(['--print'])
    ss.seek(0)
    assert ss.read().strip() == '''\
[params_a]
bongo = ["I", "am", "a", "bongo"]

[params_b]
list_ = I,am,comma-d'''


def test_json_print_action():
    parser = ArgumentParser()
    ss = StringIO()
    parser.add_argument(
        '--print',
        action=pargparse.ParameterizedJsonPrintAction,
        out_stream=ss,
        type=ParamsB,
        only={"object_selector"},
    )
    parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(['--print'])
    ss.seek(0)
    assert ss.read().strip() == '''\
{
  "object_selector": null
}'''
    ss.seek(0)
    ss.truncate()
    parameterized = {'nesting': OrderedDict()}
    parameterized['nesting']['params_b'] = ParamsB(list_=['foo', 'bar'])
    parameterized['nesting']['params_a'] = ParamsA(bingo="BINGO!")
    parser = ArgumentParser()
    parser.add_argument(
        '--print',
        action=pargparse.ParameterizedJsonPrintAction, out_stream=ss,
        parameterized=parameterized, only={
            'nesting': {'params_a': {'bingo'}, 'params_b': {'list_'}}
        },
        indent=None,
    )
    with pytest.raises(SystemExit):
        parser.parse_args(['--print'])
    ss.seek(0)
    assert (
        ss.read().strip() ==
        '{"nesting": {"params_b": {"list_": ["foo", "bar"]}, '
        '"params_a": {"bingo": "BINGO!"}}}')


def test_yaml_print_action(yaml_loader):
    parser = ArgumentParser()
    ss = StringIO()
    parameterized = OrderedDict()
    parameterized['foo'] = ParamsA(bango=1.1)
    parameterized['bar'] = ParamsA(bongo=[1, 2, 3])
    parameterized['baz'] = ParamsB()
    parser.add_argument(
        '--print',
        action=pargparse.ParameterizedYamlPrintAction,
        include_help=False,
        parameterized=parameterized,
        only={'foo': {'bango'}, 'bar': {'bongo'}},
        serializer_type_dict={param.Number: ZeroSerializer()},
        out_stream=ss,
    )
    parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(['--print'])
    ss.seek(0)
    assert ss.read().strip() == '''\
foo:
  bango: not zero
bar:
  bongo:
  - 1
  - 2
  - 3
baz:
  date_range:
  dont_try_this:
  list_:
  object_selector:'''


def test_add_parameterized_read_group(temp_dir, with_yaml):
    ini_path = os.path.join(temp_dir, 'config.ini')
    json_path = os.path.join(temp_dir, 'config.json')
    yaml_path = os.path.join(temp_dir, 'config.yaml')
    with open(ini_path, 'w') as f:
        f.write('''\
[DEFAULT]
who = notme

[flurp]
who = ini
''')
    with open(json_path, 'w') as f:
        f.write('{"who": "json"}\n')
    with open(yaml_path, 'w') as f:
        f.write('who: yaml\n')

    class MyParams(param.Parameterized):
        who = param.ObjectSelector(None, objects=["ini", "json", "yaml"])

    parser = ArgumentParser()
    pargparse.add_parameterized_read_group(
        parser, type=MyParams, ini_kwargs={'one_param_section': 'flurp'})
    options = parser.parse_args([])
    assert options.params.who is None
    options = parser.parse_args(['--read-ini', ini_path])
    assert options.params.who == "ini"
    options = parser.parse_args(['--read-json', json_path])
    assert options.params.who == "json"
    if with_yaml:
        options = parser.parse_args(['--read-yaml', yaml_path])
        assert options.params.who == "yaml"
    else:
        with pytest.raises(SystemExit):
            parser.parse_args(['--read-yaml', yaml_path])
    with pytest.raises(SystemExit):
        parser.parse_args(['--read-ini', ini_path, '--read-json', json_path])


def test_add_parameterized_print_group(with_yaml):

    class MyParams(param.Parameterized):
        zoomba = param.Integer(30000, doc="Best fitness level")

    parser = ArgumentParser()
    ss = StringIO()
    pargparse.add_parameterized_print_group(
        parser, type=MyParams,
        ini_kwargs={'out_stream': ss},
        json_kwargs={'out_stream': ss, 'indent': None},
        yaml_kwargs={'out_stream': ss, 'include_help': False},
    )
    parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(['--print-ini'])
    ss.seek(0)
    assert ss.read().strip() == '''\
# == Help ==
# [DEFAULT]
# zoomba: Best fitness level


[DEFAULT]
zoomba = 30000'''
    ss.seek(0)
    ss.truncate()
    with pytest.raises(SystemExit):
        parser.parse_args(['--print-json'])
    ss.seek(0)
    assert ss.read().strip() == '{"zoomba": 30000}'
    ss.seek(0)
    ss.truncate()
    with pytest.raises(SystemExit) as ex:
        parser.parse_args(['--print-yaml'])
    ss.seek(0)
    if with_yaml:
        assert not ex.value.code
        assert ss.read().strip() == "zoomba: 30000"
        ss.seek(0)
        ss.truncate()
    else:
        assert ex.value.code
        assert not ss.read()
