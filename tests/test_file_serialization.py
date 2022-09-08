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

import pytest

# import pydrobert.param.config as config

from pydrobert.param.serialization import (
    serialize_from_obj_to_yaml,
    deserialize_from_yaml_to_obj,
)


def test_serialize_from_obj_to_yaml(yaml_loader, temp_dir):

    obj_a = dict(a=[1, 2], b=[3, dict(c=1, d=2)])
    help_a = dict(a="foo", b=["bar", dict(d="baz")])
    file_a = f"{temp_dir}/file_a"

    serialize_from_obj_to_yaml(file_a, obj_a, help_a)

    # XXX(sdrobert): we don't guarantee any specific formatting of the yaml. It is also
    # subject to the backend settings and hence any check is fragile. Let's just make
    # sure we can go round-trip.

    #     with open(file_a) as f:
    #         txt = f.read()

    #     if config.YAML_MODULE_PRIORITIES[0].startswith("ru"):
    #         assert (
    #             txt
    #             == """\
    # a:  # foo
    # - 1
    # - 2
    # b:
    # - 3  # bar
    # - c: 1
    #   d: 2  # baz
    # """
    #         )
    #     else:
    #         assert (
    #             txt
    #             == """\
    # # == Help ==
    # # a: foo
    # # b:
    # # - bar
    # # - d: baz

    # a:
    # - 1
    # - 2
    # b:
    # - 3
    # - c: 1
    #   d: 2
    # """
    #         )

    with open(file_a) as f:
        obj_b = yaml_loader(f)
    assert obj_a == obj_b

    obj_c = [1, [2, 3], dict(c=4), 5]
    help_c = ["mid", ["lo"], dict(c="hi"), ""]
    file_c = f"{temp_dir}/file_c"

    serialize_from_obj_to_yaml(file_c, obj_c, help_c)

    #     with open(file_c) as f:
    #         txt = f.read()

    #     if config.YAML_MODULE_PRIORITIES[0].startswith("ru"):
    #         assert (
    #             txt
    #             == """\
    # - 1  # mid
    # # lo
    # - - 2
    #   - 3
    # - c: 4  # hi
    # - 5
    # """
    #         )
    #     else:
    #         print(txt)
    #         assert (
    #             txt
    #             == """\
    # # == Help ==
    # # - mid
    # # - - lo
    # # - c: hi
    # # - ''

    # - 1
    # - - 2
    #   - 3
    # - c: 4
    # - 5
    # """
    #         )

    with open(file_c) as f:
        obj_c = yaml_loader(f)
    assert obj_a == obj_b


def test_deserialize_from_yaml_to_obj(yaml_dumper, temp_dir):

    obj_a = [1, 3, 5, dict(seven=7, nine=[9, "foo"])]
    file_a = f"{temp_dir}/file_a"
    with open(file_a, "w") as f:
        yaml_dumper(obj_a, f)

    obj_b = deserialize_from_yaml_to_obj(file_a)
    assert obj_a == obj_b

    obj_c = dict(a=None, b=[1, 2, dict(c=3)])
    file_c = f"{temp_dir}/file_c"
    with open(file_c, "w") as f:
        yaml_dumper(obj_c, f)

    obj_d = deserialize_from_yaml_to_obj(file_c)
    assert obj_d == obj_d
