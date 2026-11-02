import pytest

from pyzerocopy import Array, Struct, float32, uint8_t, uint16_t, uint32_t, uint64_t


def test_packed_default():
    class A(Struct):
        a: uint8_t
        b: uint32_t
        c: uint16_t

    assert A.sizeof() == 7
    assert [A.__dict__[f].offset for f in A._fields] == [0, 1, 5]


def test_natural_alignment():
    class A(Struct, packed=False):
        a: uint8_t
        b: uint32_t
        c: uint8_t
        d: uint64_t

    assert [A.__dict__[f].offset for f in A._fields] == [0, 4, 8, 16]
    assert A.sizeof() == 24

    class B(Struct, packed=False):
        a: uint32_t
        b: uint8_t

    assert B.sizeof() == 8  # tail padding to struct alignment


def test_array_and_nested_layout():
    class P(Struct):
        x: float32
        y: float32

    class S(Struct):
        a: uint8_t * 3
        b: Array(2, uint16_t)
        c: P
        d: Array(2, P)

    assert S.sizeof() == 3 + 4 + 8 + 16


def test_annotated_and_list_forms():
    from typing import Annotated

    class P(Struct):
        x: Annotated[int, uint16_t]

    class S(Struct):
        a: Annotated[list[int], Array(2, uint16_t)]
        b: Annotated[list[P], Array(3)]

    assert S.sizeof() == 4 + 6


def test_bad_definitions():
    with pytest.raises(TypeError):

        class A(Struct):
            a: int

    with pytest.raises(TypeError):

        class B(Struct):
            pass

    with pytest.raises(ValueError):

        class C(Struct, endian="?"):
            a: uint8_t


def test_no_instance_dict():
    class A(Struct):
        a: uint8_t

    assert not hasattr(A.view(bytearray(1))[0], "__dict__")
