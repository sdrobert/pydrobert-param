'''Tests for pydrobert.param.command_line'''

import os

from pydrobert.param import command_line


def test_combine_ini_files(temp_dir):
    path_a = os.path.join(temp_dir, 'a.ini')
    path_b = os.path.join(temp_dir, 'b.ini')
    path_c = os.path.join(temp_dir, 'c.ini')
    with open(path_a, 'w') as f:
        f.write('''\
; here's a comment up here
[first]
; here's another
foo = a  ; inline comment
bar = this  ; don't take this
\tcontinues

[a second]
foo = d
''')
    with open(path_b, 'w') as f:
        f.write('''\
[third]
foo = b
baz = zoop

[first]
foo = another
\tmultiline
''')
    assert not command_line.combine_ini_files([path_a, path_c])
    with open(path_c, 'r') as f:
        assert f.read().strip() == '''\
[first]
foo = a
bar = this
\tcontinues

[a second]
foo = d'''
    assert not command_line.combine_ini_files([path_a, path_b, path_c])
    with open(path_c, 'r') as f:
        assert f.read().strip() == '''\
[first]
foo = another
\tmultiline
bar = this
\tcontinues

[a second]
foo = d

[third]
foo = b
baz = zoop'''


def test_combine_json_files(temp_dir):
    paths = dict(
        (x, os.path.join(temp_dir, x + '.json'))
        for x in 'abcdef'
    )
    with open(paths['a'], 'w') as f:
        f.write('null\n')
    with open(paths['b'], 'w') as f:
        f.write('''\
[
\t"foo",
\t{
\t\t"bar": "baz"
\t}
]''')
    with open(paths['c'], 'w') as f:
        f.write('''\
[
\t{
\t\t"bar": "bum"
\t}
]''')
    with open(paths['d'], 'w') as f:
        f.write('''\
{
\t"a": {
\t\t"b": 1,
\t\t"a": [
\t\t\t1,
\t\t\t2,
\t\t\t3
\t\t]
\t},
\t"c": 1
}
''')
    with open(paths['e'], 'w') as f:
        f.write('''\
{
\t"d": {
\t\t"foo": "bar"
\t},
\t"a": null
}
''')
    for path in list(paths.values())[:-1]:
        assert not command_line.combine_json_files([path, paths['f']])
        with open(path) as f, open(paths['f']) as g:
            assert f.read().strip() == g.read().strip()
    assert command_line.combine_json_files(
        [paths['a'], paths['b'], paths['f']])
    assert not command_line.combine_json_files(
        [paths['b'], paths['c'], paths['f'], '--compact', '--quiet'])
    with open(paths['f']) as f:
        assert f.read().strip() == '["foo", {"bar": "baz"}, {"bar": "bum"}]'
    assert not command_line.combine_json_files(
        [paths['d'], paths['e'], paths['f'], '--compact'])
    with open(paths['f']) as f:
        assert f.read().strip() == '{"a": null, "c": 1, "d": {"foo": "bar"}}'
