import mmap

import pytest

from pyzerocopy import Array, PackingError, ReadOnlyError, Struct, float32, int8_t, uint8_t, uint32_t


class Inner(Struct):
    a: uint8_t
    b: uint32_t


class Particle(Struct):
    x: float32
    id: uint32_t
    small: int8_t
    arr: uint8_t * 4
    inner: Inner
    inners: Array(2, Inner)


def test_view_shares_memory_and_exporter():
    data = bytearray(Particle.sizeof() * 10)
    view = Particle.view(data)
    assert view.memory.obj is data
    assert len(view) == 10
    view[3].id = 123
    assert int.from_bytes(data[3 * Particle.sizeof() + 4 :][:4], "little") == 123
    data[3 * Particle.sizeof() + 4] = 7  # external write is visible
    assert view[3].id == 7


def test_slices_share_memory():
    data = bytearray(Particle.sizeof() * 10)
    view = Particle.view(data)
    sub = view[2:5]
    assert len(sub) == 3 and sub.memory.obj is data
    sub[0].x = 1.5
    assert view[2].x == 1.5
    sub2 = sub[1:]
    sub2[0].id = 9
    assert view[3].id == 9
    assert len(view[8:100]) == 2 and len(view[5:2]) == 0
    assert len(view[-2:]) == 2


def test_no_copy_on_construction():
    data = bytearray(Particle.sizeof())
    view = Particle.view(data)
    data[0:4] = b"\x00\x00\xc0\x3f"
    assert view[0].x == 1.5
    with pytest.raises(BufferError):
        data.extend(b"x")  # the view pins the exporter


def test_arrays_and_nested_are_views():
    data = bytearray(Particle.sizeof())
    p = Particle.view(data)[0]
    p.arr[2] = 200
    p.inner.b = 5
    p.inners[1].a = 3
    p.arr = [1, 2, 3, 4]
    assert list(p.arr) == [1, 2, 3, 4]
    assert p.inner.b == 5 and p.inners[1].a == 3
    assert p.arr.memory.obj is data
    with pytest.raises(PackingError):
        p.arr = [1, 2]
    p.inners[0] = p.inner  # explicit in-buffer copy
    assert p.inners[0].b == 5


def test_read_only_rejects_writes():
    view = Particle.view(bytes(Particle.sizeof()))
    p = view[0]
    assert p.x == 0
    for write in (lambda: setattr(p, "id", 1), lambda: p.arr.__setitem__(0, 1), lambda: setattr(p.inner, "b", 1)):
        with pytest.raises(ReadOnlyError):
            write()


def test_validation():
    p = Particle.view(bytearray(Particle.sizeof()))[0]
    for bad in (-1, 2**32, 1.5, "a", None):
        with pytest.raises(PackingError):
            p.id = bad
    with pytest.raises(PackingError):
        p.x = 1e40
    with pytest.raises(PackingError):
        p.inner = "nope"
    assert p.id == 0


def test_bounds():
    view = Particle.view(bytearray(Particle.sizeof() * 2))
    for i in (2, -3):
        with pytest.raises(IndexError):
            view[i]
    assert view[-1].id == 0
    with pytest.raises(IndexError):
        view[0].arr[4]
    with pytest.raises(ValueError):
        Particle.view(bytearray(Particle.sizeof() + 1))
    with pytest.raises(ValueError):
        view[::2]


def test_to_bytes_is_explicit_copy():
    data = bytearray(range(Inner.sizeof()))
    v = Inner.view(data)
    copy = v.to_bytes()
    data[0] = 99
    assert copy[0] == 0 and v[0].to_bytes()[0] == 99


def test_iteration_and_other_exporters():
    data = bytearray(Inner.sizeof() * 3)
    for i, r in enumerate(Inner.view(data)):
        r.a = i
    assert [r.a for r in Inner.view(data)] == [0, 1, 2]
    mm = mmap.mmap(-1, Inner.sizeof() * 2)
    Inner.view(mm)[1].b = 4
    assert Inner.view(mm)[1].b == 4
    mm_view = Inner.view(mm)
    del mm_view
    mm.close()


def test_released_memory_raises_instead_of_crashing():
    view = Inner.view(bytearray(Inner.sizeof()))
    p = view[0]
    view.memory.release()
    with pytest.raises(ValueError):
        p.a
    with pytest.raises(ValueError):
        p.a = 1


def test_offset_and_count():
    data = bytearray(8 + Inner.sizeof() * 3)
    v = Inner.view(data, offset=8)
    assert len(v) == 3
    v[0].a = 5
    assert data[8] == 5
    assert len(Inner.view(data, offset=8, count=2)) == 2
    for kw in ({"offset": 9}, {"offset": 99}, {"offset": 8, "count": 4}, {"count": -1}):
        with pytest.raises(ValueError):
            Inner.view(data, **kw)
