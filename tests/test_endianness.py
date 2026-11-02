import struct

import pytest

from pyzerocopy import Endian, Struct, float64, uint32_t


@pytest.mark.parametrize(
    "endian,prefix", [(Endian.LITTLE, "<"), (Endian.BIG, ">"), (Endian.NETWORK, "!"), (Endian.NATIVE, "=")]
)
def test_matches_struct_module(endian, prefix):
    class A(Struct, endian=endian):
        a: uint32_t
        b: float64

    data = bytearray(A.sizeof())
    r = A.view(data)[0]
    r.a, r.b = 0x01020304, 2.5
    assert bytes(data) == struct.pack(prefix + "Id", 0x01020304, 2.5)
    assert (r.a, r.b) == (0x01020304, 2.5)


def test_nested_keeps_own_endian():
    class Inner(Struct, endian=Endian.BIG):
        v: uint32_t

    class Outer(Struct, endian=Endian.LITTLE):
        a: uint32_t
        i: Inner

    data = bytearray(8)
    r = Outer.view(data)[0]
    r.a, r.i.v = 1, 1
    assert bytes(data) == b"\x01\x00\x00\x00\x00\x00\x00\x01"
