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


def test_parameterized_class_from_tunable():
    class Base(param.Parameterized):
        pass
    tunable = {'it', 'does', 'not', 'matter'}
    Derived = poptuna.parameterized_class_from_tunable(
        tunable, base=Base, default=['not', 'matter'])
    derived = Derived()
    assert derived.only == ['not', 'matter']
    derived.only = ['not', 'matter', 'it', 'does']
    derived.only = []
    with pytest.raises(ValueError):
        derived.only = ['foo']


def test_suggest_param_dict():

    class FirstObject(object):
        def __init__(self):
            self.foo = False
            self.bar = False

        @classmethod
        def get_tunable(cls):
            return {'foo', 'bar'}

        @classmethod
        def suggest_params(cls, trial, base=None, only=None, prefix=None):
            assert base is not None
            assert only is not None
            assert not (only - {'foo', 'bar'})
            base.foo = 'foo' in only
            base.bar = 'bar' in only

    global_dict = {
        'again': {'no touching': 'me'},
        'foo': FirstObject(),
        'bar': {'foo': FirstObject()}
    }
    param_dict = poptuna.suggest_param_dict(object(), global_dict)
    assert param_dict['again']['no touching'] == 'me'
    assert param_dict['foo'].foo
    assert param_dict['foo'].bar
    assert param_dict['bar']['foo'].foo
    assert param_dict['bar']['foo'].bar
    assert not global_dict['foo'].foo
    assert not global_dict['bar']['foo'].bar
    param_dict = poptuna.suggest_param_dict(
        object(), global_dict, {'bar.foo.bar'})
    assert not param_dict['foo'].foo
    assert not param_dict['foo'].bar
    assert not param_dict['bar']['foo'].foo
    assert param_dict['bar']['foo'].bar
    with pytest.warns(UserWarning, match="'foo'"):
        poptuna.suggest_param_dict(object(), global_dict, {'foo'})
    with pytest.warns(UserWarning, match="bar.foo.baz"):
        poptuna.suggest_param_dict(object(), global_dict, {'bar.foo.baz'})


def test_with_optuna():
    optuna = pytest.importorskip('optuna')

    class XHolder(poptuna.TunableParameterized):
        x = param.Number(None)

        @classmethod
        def get_tunable(cls):
            return {'x'}

        @classmethod
        def suggest_params(cls, trial, base=None, only=None, prefix=''):
            if only is None:
                only = cls.get_tunable()
            params = cls() if base is None else base
            if 'x' in only:
                params.x = trial.suggest_uniform(prefix + 'x', 0.0, 1.0)
            return params

    def objective_1(trial):
        params = XHolder.suggest_params(trial)
        return params.x

    sampler = optuna.samplers.RandomSampler(seed=5)
    study_1 = optuna.create_study(sampler=sampler)
    study_1.optimize(objective_1, n_trials=10)
    best_params = XHolder.suggest_params(
        optuna.trial.FixedTrial(study_1.best_params))
    assert best_params.x < .5  # what a feat

    global_dict = {'one': XHolder(), 'two': XHolder()}

    def objective_2(trial):
        param_dict = poptuna.suggest_param_dict(trial, global_dict)
        return param_dict['one'].x - param_dict['two'].x

    study_2 = optuna.create_study(sampler=sampler)
    study_2.optimize(objective_2, n_trials=10)
    best_param_dict = poptuna.suggest_param_dict(
        optuna.trial.FixedTrial(study_2.best_params), global_dict)
    assert best_param_dict['one'].x < 0.5
    assert best_param_dict['two'].x > 0.5
