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
