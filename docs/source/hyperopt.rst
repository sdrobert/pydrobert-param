Hyperparameter Optimization with Optuna
=======================================

:mod:`pydrobert.param.optuna` provides some of the necessary scaffolding for
combining :class:`param.parameterized` instances with
`Optuna <https://optuna.org/>`__.

Optuna is a define-by-run hyperparameter optimization framework. It is worth
reading the
`tutorial <https://optuna.readthedocs.io/en/latest/tutorial/index.html>`__
first to get a feel for whether Optuna is suitable to your needs. Also, while
Optuna was in mind while producing the :mod:`pydrobert.param.optuna`
interfaces, Optuna is not strictly necessary as long as you use something
define-by-run and shove it in the `trial` argument.

Critically, we implement the
:class:`pydrobert.param.optuna.TunableParameterized` interface. For a single
:class:`param.Parameterized` instance, we can build it directly in the
objective function:

>>> from pydrobert.param.optuna import *
>>> import optuna
>>> import param
>>>
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
>>> best_params = Foo.suggest_params(
>>>     optuna.trial.FixedTrial(study.best_params))

The purpose of :func:`pydrobert.param.optuna.TunableParameterized.get_tunable`
is to provide names of what parameters can be optimized. Then it's up to
:func:`pydrobert.param.optuna.TunableParameterized.suggest_params` to use the
:class:`optuna.trial.Trial` to populate either `base` or a new `cls` instance
with parameter values for any listed in `only`. In the above example, we're
optimizing all available parameters in the :class:`Foo` object, which turns
out to only be ``'tune_this'``.

Replacing ``TunableParameterized`` with ``param.Parameterized`` in the above
code would work just as well here. In fact, any :class:`param.Parameterized`
instance implementing the :func:`get_tunable` and :func:`suggest_params`
methods is considered a :class:`pydrobert.param.optuna.TunableParameterized`
anyway. The benefits of :mod:`pydrobert.param.optuna` arise when you have more
than one :class:`TunableParameterized` instance in a dictionary, and you want
to optimize some parameters from (potentially) all of them simultaneously:

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
>>>     'foo.tune_this', 'bar.tune_this', 'bar.something_else'}
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
>>>     optuna.trial.FixedTrial(study.best_params),
>>>     global_dict, {'foo.tune_this'})

Both the functions :func:`pydrobert.param.optuna.get_param_dict_tunable` and
:func:`pydrobert.param.optuna.suggest_param_dict` crawl through `global_dict`,
looking for objects that implement the :class:`TunableParameterized` interface.
The former aggregates all possible tunable parameters into a single set, whilst
the latter calls the appropriate :class:`TunableParameterized` to optimize some
or all its parameters, determined by the argument passed as `only`. Because we
passed ``{'foo.tune_this'}`` as `only` to :func:`suggest_param_dict`, the above
example only optimizes ``global_dict['foo'].tune_this``.

The ``suggest_params`` class method of both the ``Foo`` and ``Bar`` instances
will be called, though `only` will be empty for the latter. If `global_dict` is
ordered, this allows one to pass information between
:class:`TunableParameterized` via an :class:`optuna.trial.Trial` instance's
``set_user_attr`` method.

If you're already populating dictionaries of parameters viz. the mechanisms
from :mod:`pydrobert.param.serialization`, it should be very little effort to
wrap your training/evaluation functions with an Optuna objective, as above.
