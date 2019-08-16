# Copyright 2019 Sean Robertson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''Utilities for optimizing param.Parameterized via Optuna

`Optuna <https://optuna.org/>`__ is a define-by-run hyperparameter optimization
framework. This submodule allows one to easily build this optimization in a
modular way.

Examples
--------

Critically, we implement the :class:`Tunable` interface. For a
single :class:`param.Parameterized` instance, we can build it directly in the
objective function:

>>> class Foo(TunableParameterized):
>>>     tune_this = param.Number(None)
>>>     not_this = param.Boolean(False)
>>>     @classmethod
>>>     def get_tunable(cls):
>>>         return {'tune_this'}
>>>     @classmethod
>>>     def suggest_params(cls, trial, base=None, only=None, prefix=''):
>>>         params = cls() if base is None else base
>>>         only = cls.get_tunable() if only is None else only
>>>         if 'tune_this' in only:
>>>             params.tune_this = trial.suggest_uniform(
>>>                 prefix + 'tune_this', 0.0, 1.0)
>>>         return params
>>>
>>> def objective(trial):
>>>     params = Foo.suggest_params(trial)
>>>     return params.tune_this ** 2
>>>
>>> study = optuna.create_study()
>>> study.optimize(objective, n_trials=30)
>>> best_params = Foo.sugget_params(study.best_trial)

We can use the functions of this submodule to optimize more complicated
environments, too

>>> # Foo as above
>>> class Bar(Foo):
>>>     something_else = param.Integer(10)
>>>     @classmethod
>>>     def get_tunable(cls):
>>>         return super(Bar, cls).get_tunable() | {'something_else'}
>>>     @classmethod
>>>     def suggest_params(cls, trial, base=None, only=None, prefix=''):
>>>         if only is None:
>>>             only = cls.get_tunable()
>>>         params = super(Bar, cls).suggest_params(trial, base, only, prefix)
>>>         if 'something_else' in only:
>>>             params.something_else = trial.suggest_int(
>>>                 prefix + 'something_else', 1, 3)
>>>         return params
>>>
>>> global_dict = {'foo': Foo(), 'bar': Bar(not_this=True)}
>>> assert get_param_dict_tunable(global_dict) == {
...     'foo.tune_this', 'bar.tune_this', 'bar.something_else'}
>>>
>>> def objective(trial):
>>>     param_dict = suggest_param_dict(trial, global_dict, {'foo.tune_this'})
>>>     assert param_dict['bar'].not_this  # sets to global_dict val
>>>     param_dict['bar'].not_this = False  # but is deep copy of global_dict
>>>     return param_dict['foo'].tune_this ** 2
>>>
>>> study = optuna.create_study()
>>> study.optimize(objective, n_trials=30)
>>> best_params = suggest_param_dict(
...     study.best_trial, global_dict, {'foo.tune_this'})
'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc

import pydrobert.param.abc
import param

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2018 Sean Robertson"
__all__ = [
    'TunableParameterized',
]


class TunableParameterized(pydrobert.param.abc.AbstractParameterized):
    '''An interface for Optuna to tune param.Parameterized instances

    The :class:`TunableParameterized` interface requires two class methods:

    - :func:`get_tunable`
    - :func:`suggest_params`

    Any object with both is a :class:`TunableParameterized`. Just like in
    :mod:`collections.abc`, the class need not directly subclass
    :class:`TunableParameterized` for :func:`isinstance` and :func:`issubclass`
    to return :obj:`True`. However, subclassing :class:`TunableParameterized`
    will
    '''

    __abstract = True  # this is how param handles abstract classes for now
    __slots__ = tuple()

    @classmethod
    @abc.abstractmethod
    def get_tunable(cls):
        '''Get a set of names of tunable parameters'''
        return set()

    @classmethod
    @abc.abstractmethod
    def suggest_params(cls, trial, base=None, only=None, prefix=''):
        '''Populate an instance of this class with parameters based on trial

        Parameters
        ----------
        trial : optuna.trial.Trial
            The current optuna trial. Parameter values will be sampled from
            this
        base : Tunable or :obj:`None`, optional
            If set, parameter values will be loaded into this instance. If
            :obj:`None`, a new instance will be created matching this class
            type
        only : collection or :obj:`None`, optional
            Only sample parameters with names in this set. If :obj:`None`,
            all the parameters from :func:`get_tunable()` will be sampled

        Returns
        -------
        Tunable
            Either `base` if not :obj:`None`, or a new instance of this class
            with parameters matching sampled values
        '''
        params = cls() if base is None else base
        return params

    @classmethod
    def __subclasshook__(cls, C):
        if cls is TunableParameterized:
            return _check_methods(C, "get_tunable", "suggest_params")
        return NotImplemented


# from
# https://github.com/python/cpython/blob/2085bd0877e17ad4d98a4586d5eabb6faecbb190/Lib/_collections_abc.py
# combined with
# https://github.com/python/cpython/blob/1a7c3571c789d704503135fe7c20d6e6f78aec86/Lib/_abcoll.py
def _check_methods(C, *methods):
    try:
        mro = C.__mro__
        for method in methods:
            for B in mro:
                if method in B.__dict__:
                    if B.__dict__[method] is None:
                        return NotImplemented
                    break
            else:
                return NotImplemented
    except AttributeError:
        for method in methods:
            if getattr(C, method, None) is None:
                return NotImplemented
    return True
