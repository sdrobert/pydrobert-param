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

"""Configuration variables"""

from typing import Tuple

__all__ = [
    "YAML_MODULE_PRIORITIES",
]


YAML_MODULE_PRIORITIES: Tuple[str] = ("ruamel.yaml", "ruamel_yaml", "yaml")
"""Specifies the order with which to try YAML parser modules

A number of different `YAML syntax <https://en.wikipedia.org/wiki/YAML>`__ parsers
exist. This tuple specifies the order by which we attempt to import parsers.
"""
