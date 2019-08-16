"""Tests for pydrobert.param.optuna"""

import sys
import pytest
import param
import pydrobert.param.optuna as poptuna


@pytest.mark.parametrize('check_type', ['instance', 'subclass'])
def test_tunable_parameterized_interface(check_type):
    if check_type == 'instance':

        def check(cls, other):
            return isinstance(cls(), other)

    else:

        def check(cls, other):
            return issubclass(cls, other)

    if sys.version_info[0] >= 3:
        with pytest.raises(TypeError):
            params = poptuna.TunableParameterized()

    assert not check(param.Parameterized, poptuna.TunableParameterized)

    class DirectInheritance(poptuna.TunableParameterized):
        @classmethod
        def suggest_params(cls, *args, **kwargs):
            pass

        @classmethod
        def get_tunable(cls):
            pass

    assert check(DirectInheritance, poptuna.TunableParameterized)

    # this would fail if we directly used abc.ABCMeta for TunableParameterized
    # since they would use diffent (and not compatible) metaclasses
    class RedundantInheritance(
            poptuna.TunableParameterized, param.Parameterized):

        @classmethod
        def suggest_params(cls, *args, **kwargs):
            pass

        @classmethod
        def get_tunable(cls):
            pass

    assert check(RedundantInheritance, poptuna.TunableParameterized)
    assert check(RedundantInheritance, param.Parameterized)

    class NotParameterizedNewStyle(object):
        @classmethod
        def suggest_params(cls, *args, **kwargs):
            pass

        @classmethod
        def get_tunable(cls):
            pass

    assert check(NotParameterizedNewStyle, poptuna.TunableParameterized)
    assert not check(NotParameterizedNewStyle, param.Parameterized)

    class NotParameterizedOldStyle:
        @classmethod
        def suggest_params(cls, *args, **kwargs):
            pass

        @classmethod
        def get_tunable(cls):
            pass

    assert check(NotParameterizedOldStyle, poptuna.TunableParameterized)
    assert not check(NotParameterizedOldStyle, param.Parameterized)

    class ForceTheIssue:
        pass

    assert not check(ForceTheIssue, poptuna.TunableParameterized)
    poptuna.TunableParameterized.register(ForceTheIssue)
    assert check(ForceTheIssue, poptuna.TunableParameterized)


def test_get_param_dict_tunable():

    class FirstObject(object):
        @classmethod
        def get_tunable(cls):
            return {'lookit', 'me'}

        @classmethod
        def suggest_params(cls):
            pass

    class SecondObject(object):
        @classmethod
        def get_tunable(cls):
            return {'watch', 'me'}

        @classmethod
        def suggest_params(cls):
            pass

    param_dict = {
        'ignore_me': 1,
        'not_me': {"ive_got_nested": FirstObject()},
        'me': FirstObject(),
        'too': SecondObject(),
    }
    tunable = poptuna.get_param_dict_tunable(param_dict)
    assert tunable == {
        'not_me.ive_got_nested.me', 'not_me.ive_got_nested.lookit',
        'me.me', 'me.lookit',
        'too.watch', 'too.me',
    }
    param_dict['me.too'] = FirstObject()
    with pytest.raises(ValueError, match='me.too'):
        poptuna.get_param_dict_tunable(param_dict, on_decimal='raise')
    with pytest.warns(UserWarning) as record:
        tunable = poptuna.get_param_dict_tunable(
            param_dict, on_decimal='ignore')
        assert not record
        poptuna.get_param_dict_tunable(param_dict)  # this warns
    del param_dict['me.too']

    class Renegade(object):
        @classmethod
        def get_tunable(cls):
            return {'uh oh', 'bad.boy'}

        @classmethod
        def suggest_params(cls):
            pass
    param_dict['nice'] = Renegade()
    with pytest.warns(UserWarning, match='bad.boy'):
        poptuna.get_param_dict_tunable(param_dict)


def test_parameterized_class_from_tunable_set():
    class Base(param.Parameterized):
        pass
    tunable = {'it', 'does', 'not', 'matter'}
    Derived = poptuna.parameterized_class_from_tunable_set(
        tunable, base=Base, default=['not', 'matter'])
    derived = Derived()
    assert derived.only == ['not', 'matter']
    derived.only = ['not', 'matter', 'it', 'does']
    derived.only = []
    with pytest.raises(ValueError):
        derived.only = ['foo']
