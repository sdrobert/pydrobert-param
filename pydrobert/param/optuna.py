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
import warnings

import pydrobert.param.abc
import param

from collections import OrderedDict

try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc

__author__ = "Sean Robertson"
__email__ = "sdrobert@cs.toronto.edu"
__license__ = "Apache 2.0"
__copyright__ = "Copyright 2018 Sean Robertson"
__all__ = [
    'get_param_dict_tunable',
    'parameterized_class_from_tunable',
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
        '''Get a set of names of tunable parameters

        The values are intended to be names of parameters. Values should not
        contain "."
        '''
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
        prefix : str, optional
            A value to be prepended to the names from `only` when sampling
            those parameters from `trial`

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


def get_param_dict_tunable(param_dict, on_decimal="warn"):
    '''Return a set of all the tunable parameters in a parameter dictionary

    This function crawls through a (possibly nested) dictionary of objects,
    looks for any that implement the :class:`TunableParameterized` interface,
    collects the results of calls to :func:`get_tunable`, and returns the set
    `tunable`.

    Elements of `tunable` are strings with the format
    ``"<key_0>.<key_1>.<...>.<parameter_name>"``, where ``parameter_name`` is
    a parameter from ``param_dict[<key_0>][<key_1>][...].get_tunable()``

    Parameters
    ----------
    param_dict : dict
    on_decimal : {"warn", "raise", "ignore"}, optional
        '.' can produce ambiguous entries in `tunable`. When one is found as a
        key in `param_dict` or as a tunable parameter: "raise" means a
        :class:`ValueError` will be raised; "warn" means a warning will be
        issued via :mod:`warnings`; and "ignore" just ignores it

    Returns
    -------
    tunable : OrderedDict
    '''
    if on_decimal not in {'ignore', 'warn', 'raise'}:
        raise ValueError("on_decimal must be 'ignore', 'warn', or 'raise'")
    tunable_params = _tunable_params_from_param_dict(param_dict, on_decimal)
    tunable = set()
    for prefix, params in tunable_params.items():
        new_tunable = params.get_tunable()
        if on_decimal != 'ignore':
            decimal_tunable = tuple(x for x in new_tunable if '.' in x)
            if decimal_tunable:
                msg = (
                    "Found parameters in param_dict{} with '.' in their name: "
                    "{}. These can lead to ambiguities in suggest_param_dict "
                    "and should be avoided".format(
                        _to_multikey(prefix), decimal_tunable))
                if on_decimal == 'raise':
                    raise ValueError(msg)
                else:
                    warnings.warn(msg)
        tunable |= {'.'.join([prefix, x]) for x in new_tunable}
    return tunable


def parameterized_class_from_tunable(
        tunable, base=param.Parameterized, default=[]):
    '''Construct a param.Parameterized class to store parameters to optimize

    This function creates a subclass of :class:`param.Parameterized` that has
    only one parameter: `only`. `only` is a :class:`param.ListSelector` that
    allows values from `tunable`

    Parameters
    ----------
    tunable : collection
    base : class, optional
        The parent class of the returned class
    default : list, optional
        The default value for the `only` parameter

    Returns
    -------
    Derived : base
        The derived class

    Examples
    --------
    Group what hyperparameters you wish to optimize in the same param dict as
    the rest of your parameters

    >>> class ModelParams(param.Parameterized):
    >>>     lr = param.Number(1e-4, bounds=(1e-8, None))
    >>>     num_layers = param.Integer(3, bounds=(1, None))
    >>>     @classmethod
    >>>     def get_tunable(cls):
    >>>         return {'num_layers', 'lr'}
    >>>     @classmethod
    >>>     def suggest_params(cls, trial, base=None, only=None, prefix=None):
    >>>         pass  # do this
    >>>
    >>> param_dict = {'model': ModelParams()}
    >>> tunable = get_param_dict_tunable(param_dict)
    >>> OptimParams = parameterized_class_from_tunable(tunable)
    >>> param_dict['optim'] = OptimParams()
    '''
    class Derived(base):
        only = param.ListSelector(
            default, objects=list(tunable),
            doc='When performing hyperparameter optimization, only optimize '
            'these parameters')

    return Derived


def _to_multikey(s):
    # turn '.'-delimited string into one ["that"]["looks"]["like"]["this"]
    return '["' + s.replace('.', '"]["') + '"]'


def _tunable_params_from_param_dict(param_dict, on_decimal, prefix=''):
    # crawl a possibly nested dictionary for TunableParameterized instances
    # and return a dictionary where values are TunableParameterized and keys
    # are a '.'-delimited list of the multi-keys that got us there
    tunable_params = OrderedDict()
    for key, value in param_dict.items():
        if '.' in key and on_decimal != 'ignore':
            msg = (
                "Found key{} with '.' in its name: '{}'. This can lead to "
                "ambiguities in suggest_param_dict and should be avoided"
                "".format(
                    " at param_dict" + _to_multikey(prefix) if prefix else "",
                    key))
            if on_decimal == "raise":
                raise ValueError(msg)
            else:
                warnings.warn(msg)
        key = '.'.join([prefix, key] if prefix else [key])
        if isinstance(value, TunableParameterized):
            tunable_params[key] = value
        elif isinstance(value, collections_abc.Mapping):
            tunable_params.update(_tunable_params_from_param_dict(
                value, on_decimal, key))
    return tunable_params


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
