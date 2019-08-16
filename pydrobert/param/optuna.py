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

Critically, we implement the :class:`TunableParameterized` interface. For a
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
