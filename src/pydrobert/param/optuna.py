# Copyright 2021 Sean Robertson
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

"""Utilities for optimizing param parameters via Optuna

See Also
--------
:ref:`Hyperparameter Optimization with Optuna`
    A tutorial on how to use this module
"""


import abc
import warnings
import collections.abc

from typing import Collection, Optional, Set
from collections import OrderedDict
from copy import deepcopy

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

import param

from pydrobert.param.abc import AbstractParameterized


__all__ = [
    "get_param_dict_tunable",
    "parameterized_class_from_tunable",
    "suggest_param_dict",
    "TunableParameterized",
]


class TunableParameterized(AbstractParameterized):
    """An interface for Optuna to tune Parameterized instances

    The :class:`TunableParameterized` interface requires two class methods:

    - :func:`get_tunable`
    - :func:`suggest_params`

    Any object with both is a :class:`TunableParameterized`. Just like in
    :mod:`collections.abc`, the class need not directly subclass
    :class:`TunableParameterized` for :func:`isinstance` and :func:`issubclass` to
    return :obj:`True`. Subclassing :class:`TunableParameterized` directly will ensure
    the function also inherits from :class:`param.parameterized.Parameterized`
    """

    __abstract = True  # this is how param handles abstract classes for now
    __slots__ = tuple()

    @classmethod
    @abc.abstractmethod
    def get_tunable(cls) -> Set[str]:
        """Get a set of names of tunable parameters

        The values are intended to be names of parameters. Values should not contain "."
        """
        return set()

    @classmethod
    @abc.abstractmethod
    def suggest_params(
        cls,
        trial,
        base: Optional["TunableParameterized"] = None,
        only: Optional[Collection[str]] = None,
        prefix: str = "",
    ):
        """Populate an instance of this class with parameters based on trial

        Parameters
        ----------
        trial : optuna.trial.Trial
            The current optuna trial. Parameter values will be sampled from
            this
        base : TunableParameterized or :obj:`None`, optional
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
        TunableParameterized
            Either `base` if not :obj:`None`, or a new instance of this class
            with parameters matching sampled values
        """
        params = cls() if base is None else base
        return params

    @classmethod
    def __subclasshook__(cls, C):
        if cls is TunableParameterized:
            return _check_methods(C, "get_tunable", "suggest_params")
        return NotImplemented


def get_param_dict_tunable(
    param_dict: dict, on_decimal: Literal["ignore", "warn", "raise"] = "warn"
) -> OrderedDict:
    """Return a set of all the tunable parameters in a parameter dictionary

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
        :obj:`'.'` can produce ambiguous parameters in `tunable`. When one is found as a
        key in `param_dict` or as a tunable parameter: "raise" means a
        :class:`ValueError` will be raised; "warn" means a warning will be issued via
        :mod:`warnings`; and "ignore" just ignores it

    Returns
    -------
    tunable : collections.OrderedDict
    """
    if on_decimal not in {"ignore", "warn", "raise"}:
        raise ValueError("on_decimal must be 'ignore', 'warn', or 'raise'")
    tunable_params = _tunable_params_from_param_dict(param_dict, on_decimal)
    tunable = set()
    for prefix, params in list(tunable_params.items()):
        new_tunable = params.get_tunable()
        if on_decimal != "ignore":
            decimal_tunable = tuple(x for x in new_tunable if "." in x)
            if decimal_tunable:
                msg = (
                    "Found parameters in param_dict{} with '.' in their name: "
                    "{}. These can lead to ambiguities in suggest_param_dict "
                    "and should be avoided".format(
                        _to_multikey(prefix), decimal_tunable
                    )
                )
                if on_decimal == "raise":
                    raise ValueError(msg)
                else:
                    warnings.warn(msg)
        tunable |= {".".join([prefix, x]) for x in new_tunable}
    return tunable


def parameterized_class_from_tunable(
    tunable: Collection, base: type = param.Parameterized, default: list = []
) -> type:
    """Construct a Parameterized class to store parameters to optimize

    This function creates a subclass of :class:`param.parameterized.Parameterized` that
    has only one parameter: `only`. `only` is a :class:`param.ListSelector` that allows
    values from `tunable`

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
    >>> param_dict['hyperparameter_optimization'] = OptimParams()
    """

    class Derived(base):
        only = param.ListSelector(
            default,
            objects=list(tunable),
            doc="When performing hyperparameter optimization, only optimize "
            "these parameters",
        )

    return Derived


def suggest_param_dict(
    trial,
    global_dict: dict,
    only: Optional[set] = None,
    on_decimal: Literal["ignore", "warn", "raise"] = "warn",
    warn: bool = True,
) -> dict:
    """Use Optuna trial to sample values for TunableParameterized in dict

    This function creates a deep copy of the dictionary `global_dict`. Then, for every
    :class:`TunableParameterized` it finds in the copy, it calls that instance's
    :func:`suggest_params` to optimize an appropriate subset of parameters.

    Parameters
    ----------
    trial : optunal.trial.Trial
        The trial from an Optuna experiment. This is passed along to each
        :class:`TunableParameterized` in `global_dict`
    global_dict : dict
        A (possibly nested) dictionary containing some
        :class:`TunableParameterized` as values
    only : set or :obj:`None`, optional
        A set containing parameter names to optimize. Names are formatted
        ``"<key_0>.<key_1>.<...>.<parameter_name>"``, where ``parameter_name``
        is a parameter from
        ``global_dict[<key_0>][<key_1>][...].get_tunable()``. If :obj:`None`,
        the entire set returned by :func:`get_param_dict_tunable`.
    on_decimal : {"warn", "raise", "ignore"}, optional
        '.' can produce ambiguous parameters in `only`. When one is found as a
        key in `global_dict` or as a tunable parameter: "raise" means a
        :class:`ValueError` will be raised; "warn" means a warning will be
        issued via :mod:`warnings`; and "ignore" just ignores it
    warn : bool, optional
        If `warn` is :obj:`True` and any elements of `only` do not match this
        description, a warning will be raised via :mod:`warnings`

    Returns
    -------
    param_dict : dict
    """
    if only is None:
        only = get_param_dict_tunable(global_dict, on_decimal)
        second_pass = True
    else:
        only = set(only)  # in case a list, and also allows us to modify
        second_pass = False
    param_dict = deepcopy(global_dict)
    tunable_params = _tunable_params_from_param_dict(
        param_dict, "ignore" if second_pass else on_decimal
    )
    for prefix, param_ in list(tunable_params.items()):
        prefix = prefix + "."
        prefix_only = {x[len(prefix) :] for x in only if x.startswith(prefix)}
        prefix_only = prefix_only & param_.get_tunable()
        only -= {prefix + x for x in prefix_only}
        param_.suggest_params(trial, base=param_, only=prefix_only, prefix=prefix)
    if warn and only:
        warnings.warn(
            '"only" contained extra parameters: {}. To suppress this warning, '
            "set warn=False".format(only)
        )
    return param_dict


def _to_multikey(s):
    # turn '.'-delimited string into one ["that"]["looks"]["like"]["this"]
    return '["' + s.replace(".", '"]["') + '"]'


def _tunable_params_from_param_dict(param_dict, on_decimal, prefix=""):
    # crawl a possibly nested dictionary for TunableParameterized instances
    # and return a dictionary where values are TunableParameterized and keys
    # are a '.'-delimited list of the multi-keys that got us there
    tunable_params = OrderedDict()
    for key, value in list(param_dict.items()):
        if "." in key and on_decimal != "ignore":
            msg = (
                "Found key{} with '.' in its name: '{}'. This can lead to "
                "ambiguities in suggest_param_dict and should be avoided"
                "".format(
                    " at param_dict" + _to_multikey(prefix) if prefix else "", key
                )
            )
            if on_decimal == "raise":
                raise ValueError(msg)
            else:
                warnings.warn(msg)
        key = ".".join([prefix, key] if prefix else [key])
        if isinstance(value, TunableParameterized):
            tunable_params[key] = value
        elif isinstance(value, collections.abc.Mapping):
            tunable_params.update(
                _tunable_params_from_param_dict(value, on_decimal, key)
            )
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
