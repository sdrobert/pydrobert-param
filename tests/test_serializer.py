import argparse
import os
import sys

from datetime import datetime, timedelta

import pytest
import param
import pandas as pd
import numpy as np

from pydrobert.param.serialization import (
    register_serializer,
    unregister_serializer,
    yaml_is_available,
)
from pydrobert.param._serializer import _my_serializers
from pydrobert.param.argparse import (
    DeserializationAction,
    SerializationAction,
    add_deserialization_group_to_parser,
    add_serialization_group_to_parser,
)


FILE_DIR = os.path.dirname(os.path.realpath(__file__))
FILE_DIR_DIR = os.path.dirname(FILE_DIR)


@pytest.fixture(scope="function", params=list(_my_serializers))
def mode(request):
    if "yaml" in request.param and not yaml_is_available():
        pytest.skip("yaml unavailable")
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
        nested = param.ClassSelector(class_=Nested)

    parent = Parent(name="parent")
    txt = parent.param.serialize_parameters(mode=mode)
    if format == "json":
        assert txt == '{"name": "parent", "nested": null}'
    child = Parent(**Parent.param.deserialize_parameters(txt, mode=mode))
    assert child.param.pprint() == parent.param.pprint()
    parent.nested = Nested(name="nested", leaf1=2, leaf2=True)
    assert child.param.pprint() != parent.param.pprint()
    txt = parent.param.serialize_parameters(mode=mode)
    if format == "json":
        assert (
            txt
            == '{"name": "parent", "nested": {"name": "nested", "leaf1": 2, "leaf2": true}}'
        )
    child = Parent(**Parent.param.deserialize_parameters(txt, mode=mode))
    assert child.param.pprint() == parent.param.pprint()
    child = Parent(
        **Parent.param.deserialize_parameters(
            txt, {"name", "nested.name", "nested.leaf1"}, mode=mode
        )
    )
    assert child.param.pprint() != parent.param.pprint()
    child.nested.leaf2 = True
    assert child.param.pprint() == parent.param.pprint()
    txt = parent.param.serialize_parameters({"name", "nested.leaf1"}, mode=mode)
    if format == "json":
        assert txt == '{"name": "parent", "nested": {"leaf1": 2}}'
    child = Parent(**Parent.param.deserialize_parameters(txt, mode=mode))
    assert child.param.pprint() != parent.param.pprint()
    child.nested.leaf2 = True
    assert child.param.pprint() != parent.param.pprint()


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


def test_reckless_otherwise_same(mode, yaml_loader):
    if not mode.startswith("reckless_"):
        pytest.skip(f"'{mode}' not reckless")
    safe_mode = mode[9:]

    class P(param.Parameterized):
        action = param.Action(_default_action, allow_None=True)
        array = param.Array(np.array([1.0, 2.0]))
        boolean = param.Boolean(True, allow_None=True)
        callable = param.Callable(_default_action, allow_None=True)
        class_selector = param.ClassSelector(
            class_=int, is_instance=False, allow_None=True
        )
        color = param.Color("#FFFFFF", allow_None=True)
        composite = param.Composite(attribs=["action", "array"], allow_None=True)
        try:
            data_frame = param.DataFrame(
                pd.DataFrame({"A": 1.0, "B": np.arange(5)}), allow_None=True
            )
        except TypeError:
            data_frame = param.DataFrame(pd.DataFrame({"A": 1.0, "B": np.arange(5)}))
        date = param.Date(datetime.now(), allow_None=True)
        date_range = param.DateRange(
            (datetime.now() - timedelta(days=1), datetime.now() + timedelta(days=1)),
            allow_None=True,
        )
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
            item_type=_CallableObject,
            allow_None=True,
        )
        integer = param.Integer(10, allow_None=True)
        list_ = param.List([1, 2, 3], allow_None=True, item_type=int)
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
            assert p_a.param.pprint() == p_b.param.pprint()


def test_deserialization_action(temp_dir, mode, capsys):
    class Foo(param.Parameterized):
        my_int = param.Integer(1)
        my_bool = param.Boolean(False)
        my_mag = param.Magnitude(None)

    foo_0 = Foo(name="0", my_bool=True)
    foo_1 = Foo(name="1", my_int=2)
    assert foo_0.param.pprint() != foo_1.param.pprint() != Foo().param.pprint()
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
    assert options.p.param.pprint() == foo_0.param.pprint()
    arg.nargs = "?"
    options = parser.parse_args(["--p", f"{temp_dir}/1.{mode}"])
    assert options.p.param.pprint() == foo_1.param.pprint()
    arg.nargs = "*"
    options = parser.parse_args(["--p"])
    assert options.p == []
    options = parser.parse_args(["--p", f"{temp_dir}/0.{mode}", f"{temp_dir}/1.{mode}"])
    assert len(options.p) == 2
    assert options.p[0].param.pprint() == foo_0.param.pprint()
    assert options.p[1].param.pprint() == foo_1.param.pprint()

    with open(f"{temp_dir}/0.{mode}", "w") as f:
        if mode.endswith("yaml"):
            f.write("my_int: 'snarf'\n")
        elif mode.endswith("json"):
            f.write(r'{"my_int": "snarf"}')
        else:
            assert False, f"{mode} check missing"

    with pytest.raises(SystemExit):
        parser.parse_args(["--p", f"{temp_dir}/0.{mode}"])
    assert capsys.readouterr().err.index("my_int") >= 0


def test_serialization_action(temp_dir, mode, capsys, yaml_loader):
    class Bar(param.Parameterized):
        dict_ = param.Dict(None)
        list_ = param.List(None, item_type=int)

    bar_0 = Bar(name="0", dict_={"a": "b", "c": [1, 2, 3]})
    bar_1 = Bar(name="1", list_=[-1, 2, 4])
    assert bar_0.param.pprint() != bar_1.param.pprint() != Bar().param.pprint()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--b",
        action=SerializationAction,
        type=Bar,
        const=(mode, {"dict_", "list_"}),
        default=sys.stdout,  # need to do this or pytest won't wrap it
    )
    parser.add_argument("--b0", action=SerializationAction, type=bar_0, const=mode)
    parser.add_argument("--b1", action=SerializationAction, type=bar_1, const=mode)
    temp_file_0 = f"{temp_dir}/0.{mode}"
    temp_file_1 = f"{temp_dir}/1.{mode}"

    with pytest.raises(SystemExit):
        parser.parse_args(["--b"])
    txt, err = capsys.readouterr()
    assert not err
    bar_ = Bar(**Bar.param.deserialize_parameters(txt, mode=mode))
    assert bar_.param.pprint() == Bar().param.pprint()

    with pytest.raises(SystemExit):
        parser.parse_args(["--b0", temp_file_0])
    with open(temp_file_0) as f:
        txt = f.read()
        bar_0_ = Bar(**Bar.param.deserialize_parameters(txt, mode=mode))
    assert bar_0_.param.pprint() == bar_0.param.pprint()

    with pytest.raises(SystemExit):
        parser.parse_args(["--b1", temp_file_1])
    with open(temp_file_1) as f:
        txt = f.read()
        bar_1_ = Bar(**Bar.param.deserialize_parameters(txt, mode=mode))
    assert bar_1_.param.pprint() == bar_1.param.pprint()


def test_add_deserialization_group_to_parser(temp_dir, yaml_loader, mode):
    file_format = mode.split("_")[-1]
    reckless = "reckless" in mode

    class Baz(param.Parameterized):
        int = param.Integer(-1)

    bazs, temps = [], []
    for i in range(3):
        temp_file = f"{temp_dir}/{i}.{file_format}"
        baz = Baz(name=f"baz{i}", int=i)
        with open(temp_file, "w") as f:
            f.write(baz.param.serialize_parameters(mode=mode))
        bazs.append(baz)
        temps.append(temp_file)

    parser = argparse.ArgumentParser()
    add_deserialization_group_to_parser(parser, Baz, "p", reckless=reckless)
    options = parser.parse_args([])
    assert options.p is None

    parser = argparse.ArgumentParser()
    add_deserialization_group_to_parser(parser, bazs[0], "p", reckless=reckless)
    options = parser.parse_args([])
    assert options.p is bazs[0]

    for i, (baz, temp_file) in enumerate(zip(bazs, temps)):
        options = parser.parse_args([f"--read-{file_format}", temp_file])
        assert options.p.param.pprint() == baz.param.pprint()


def test_add_serialization_group_to_parser(temp_dir, yaml_loader, mode):
    file_format = mode.split("_")[-1]
    reckless = "reckless" in mode

    class Boop(param.Parameterized):
        int = param.Integer(-1)

    parser = argparse.ArgumentParser()
    add_serialization_group_to_parser(parser, Boop, reckless=reckless)

    temp_file = f"{temp_dir}/temp.{file_format}"
    with pytest.raises(SystemExit):
        parser.parse_args([f"--print-{file_format}", temp_file])
    with open(temp_file) as f:
        txt = f.read()
    boop = Boop(**Boop.param.deserialize_parameters(txt, mode=mode))
    assert boop.param.pprint() == Boop().param.pprint()

    boop.int = 5
    assert boop.param.pprint() != Boop().param.pprint()
    parser = argparse.ArgumentParser()
    add_serialization_group_to_parser(parser, boop, reckless=reckless)
    with pytest.raises(SystemExit):
        parser.parse_args([f"--print-{file_format}", temp_file])
    with open(temp_file) as f:
        txt = f.read()
    boop_ = Boop(**Boop.param.deserialize_parameters(txt, mode=mode))
    assert boop.param.pprint() == boop_.param.pprint()
