"""Abstract base class for param.ParameterizedMetaclass"""

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
