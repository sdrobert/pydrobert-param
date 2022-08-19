# Copyright 2022 Sean Robertson
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

"""Abstract base class for :class:`param.ParameterizedMetaclass`"""

from __future__ import annotations

import abc
import param

__all__ = [
    "AbstractParameterized",
    "AbstractParameterizedMetaclass",
]


class AbstractParameterizedMetaclass(
    abc.ABCMeta, param.parameterized.ParameterizedMetaclass
):
    """Metaclass for defining Abstract Base Classes for Parameterized instances"""


class AbstractParameterized(
    param.Parameterized, metaclass=AbstractParameterizedMetaclass
):
    """A Parameterized with metaclass AbstractParameterizedMetaclass

    Functions similarly to :class:`abc.ABCMeta` in that subclassing an
    :class:`AbstractParameterized` gives the subclass a
    :class:`AbstractParameterizedMetaclass` metaclass. Instead of a base class of
    :class:`object`, however, an :class:`AbstractParameterized` has
    :class:`param.parameterized.Parameterized` as a base class
    """
