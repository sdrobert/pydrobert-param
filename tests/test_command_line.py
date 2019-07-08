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
