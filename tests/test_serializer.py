import argparse
import os

from datetime import datetime

import pytest
import param
import pandas as pd
import numpy as np

from pydrobert.param.serialization import (
    register_serializer,
    unregister_serializer,
)
from pydrobert.param._serializer import _my_serializers
from pydrobert.param.argparse import DeserializationAction


FILE_DIR = os.path.dirname(os.path.realpath(__file__))
FILE_DIR_DIR = os.path.dirname(FILE_DIR)


@pytest.fixture(scope="function", params=list(_my_serializers))
def mode(request):
    # we register all of them in case we use any
    for mode in _my_serializers:
        register_serializer(mode)
    yield request.param
    for mode in _my_serializers:
        unregister_serializer(mode)


def test_register_serializer(mode):
    param.Parameterized.param.serialize_parameters(mode=mode)
    unregister_serializer(mode)

    with pytest.raises(Exception):
        param.Parameterized.param.serialize_parameters(mode=mode)


def test_reckless_nesting(mode):
    if not mode.startswith("reckless_"):
        pytest.skip(f"'{mode}' not reckless")
    format = mode.split("_")[-1]

    class Nested(param.Parameterized):
        leaf1 = param.Integer(1)
        leaf2 = param.Boolean(False)

    class Parent(param.Parameterized):
        nested = param.ClassSelector(Nested)

    parent = Parent(name="parent")
    txt = parent.param.serialize_parameters(mode=mode)
    if format == "json":
        assert txt == '{"name": "parent", "nested": null}'
    child = Parent(**Parent.param.deserialize_parameters(txt, mode=mode))
    assert child.pprint() == parent.pprint()
    parent.nested = Nested(name="nested", leaf1=2, leaf2=True)
    assert child.pprint() != parent.pprint()
    txt = parent.param.serialize_parameters(mode=mode)
    if format == "json":
        assert (
            txt
            == '{"name": "parent", "nested": {"name": "nested", "leaf1": 2, "leaf2": true}}'
        )
    child = Parent(**Parent.param.deserialize_parameters(txt, mode=mode))
    assert child.pprint() == parent.pprint()
    child = Parent(
        **Parent.param.deserialize_parameters(
            txt, {"name", "nested.name", "nested.leaf1"}, mode=mode
        )
    )
    assert child.pprint() != parent.pprint()
    child.nested.leaf2 = True
    assert child.pprint() == parent.pprint()
    txt = parent.param.serialize_parameters({"name", "nested.leaf1"}, mode=mode)
    if format == "json":
        assert txt == '{"name": "parent", "nested": {"leaf1": 2}}'
    child = Parent(**Parent.param.deserialize_parameters(txt, mode=mode))
    assert child.pprint() != parent.pprint()
    child.nested.leaf2 = True
    assert child.pprint() != parent.pprint()
    txt = txt.replace('"leaf1', '"name": "nested", "leaf1')
    child = Parent(**Parent.param.deserialize_parameters(txt, mode=mode))
    child.nested.leaf2 = True
    assert child.pprint() == parent.pprint()


def _default_action():
    return 1


class _CallableObject(object):
    def __init__(self, val=2):
        self.val = val

    def __call__(self):
        return self.val

    def __eq__(self, other):
        return self.val == other.val

    def __repr__(self):
        return "CallableObject({})".format(self.val)


def test_reckless_otherwise_same(mode):
    if not mode.startswith("reckless_"):
        pytest.skip(f"'{mode}' not reckless")
    safe_mode = mode[9:]

    class P(param.Parameterized):
        action = param.Action(_default_action, allow_None=True)
        array = param.Array(np.array([1.0, 2.0]))
        boolean = param.Boolean(True, allow_None=True)
        callable = param.Callable(_default_action, allow_None=True)
        class_selector = param.ClassSelector(int, is_instance=False, allow_None=True)
        color = param.Color("#FFFFFF", allow_None=True)
        composite = param.Composite(["action", "array"], allow_None=True)
        try:
            data_frame = param.DataFrame(
                pd.DataFrame({"A": 1.0, "B": np.arange(5)}), allow_None=True
            )
        except TypeError:
            data_frame = param.DataFrame(pd.DataFrame({"A": 1.0, "B": np.arange(5)}))
        date = param.Date(datetime.now(), allow_None=True)
        date_range = param.DateRange((datetime.min, datetime.max), allow_None=True)
        dict_ = param.Dict({"foo": "bar"}, allow_None=True, doc="dict means dictionary")
        dynamic = param.Dynamic(default=_default_action, allow_None=True)
        file_selector = param.FileSelector(
            os.path.join(FILE_DIR_DIR, "LICENSE"),
            path=os.path.join(FILE_DIR_DIR, "*"),
            allow_None=True,
        )
        filename = param.Filename(
            os.path.join(FILE_DIR_DIR, "LICENSE"), allow_None=True
        )
        foldername = param.Foldername(os.path.join(FILE_DIR_DIR), allow_None=True)
        hook_list = param.HookList(
            [_CallableObject(), _CallableObject()],
            class_=_CallableObject,
            allow_None=True,
        )
        integer = param.Integer(10, allow_None=True)
        list_ = param.List([1, 2, 3], allow_None=True, class_=int)
        list_selector = param.ListSelector([2, 2], objects=[1, 2, 3], allow_None=True)
        magnitude = param.Magnitude(0.5, allow_None=True)
        multi_file_selector = param.MultiFileSelector(
            [],
            path=os.path.join(FILE_DIR_DIR, "*"),
            allow_None=True,
            check_on_set=True,
        )
        number = param.Number(-10.0, allow_None=True, doc="here is a number")
        numeric_tuple = param.NumericTuple((5.0, 10.0), allow_None=True)
        object_selector = param.ObjectSelector(
            False, objects={"False": False, "True": 1}, allow_None=True
        )
        path = param.Path(os.path.join(FILE_DIR_DIR, "LICENSE"), allow_None=True)
        range_ = param.Range((-1.0, 2.0), allow_None=True)
        series = param.Series(pd.Series(range(5)), allow_None=True)
        string = param.String("foo", allow_None=True, doc="this is a string")
        tuple_ = param.Tuple((3, 4, "fi"), allow_None=True)
        x_y_coordinates = param.XYCoordinates((1.0, 2.0), allow_None=True)

    p = P(name="foo")
    pnames = sorted(p.param)
    for pname in pnames:
        except_a = except_b = json_a = json_b = None
        try:
            json_a = p.param.serialize_parameters({pname}, safe_mode)
        except Exception as e:
            except_a = type(e)
        try:
            json_b = p.param.serialize_parameters({pname}, mode)
        except Exception as e:
            except_b = type(e)
        assert json_a == json_b
        assert except_a == except_b
        if json_a is not None:
            p_a = P(**P.param.deserialize_parameters(json_a, {pname}, safe_mode))
            p_b = P(**P.param.deserialize_parameters(json_a, {pname}, mode))
            assert p_a.pprint() == p_b.pprint()


def test_deserialization_action(temp_dir, mode):
    class Foo(param.Parameterized):
        a = param.Integer(1)
        b = param.Boolean(False)

    foo_0 = Foo(name="0", b=True)
    foo_1 = Foo(name="0", a=2)
    assert foo_0.pprint() != foo_1.pprint() != Foo().pprint()
    for i, foo in enumerate((foo_0, foo_1)):
        temp_file = f"{temp_dir}/{i}.{mode}"
        txt = foo.param.serialize_parameters(mode=mode)
        with open(temp_file, "w") as f:
            f.write(txt)

    parser = argparse.ArgumentParser()
    arg = parser.add_argument("--p", action=DeserializationAction, type=Foo, const=mode)
    options = parser.parse_args([])
    assert options.p is None
    options = parser.parse_args(["--p", f"{temp_dir}/0.{mode}"])
    assert options.p.pprint() == foo_0.pprint()
    options = parser.parse_args(["--p", f"{temp_dir}/1.{mode}"])
    assert options.p.pprint() == foo_1.pprint()
    arg.nargs = "*"
    options = parser.parse_args(["--p"])
    assert options.p == []
    options = parser.parse_args(["--p", f"{temp_dir}/0.{mode}", f"{temp_dir}/1.{mode}"])
    assert len(options.p) == 2
    assert options.p[0].pprint() == foo_0.pprint()
    assert options.p[1].pprint() == foo_1.pprint()
