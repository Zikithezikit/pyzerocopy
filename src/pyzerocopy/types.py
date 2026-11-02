"""Type markers (uint32_t, float32, Array...) and their resolved descriptors."""

from __future__ import annotations

import struct
from enum import Enum
from typing import Any

from .exceptions import PackingError, ReadOnlyError
from .view import View


class Endian(str, Enum):
    NATIVE = "="
    LITTLE = "<"
    BIG = ">"
    NETWORK = "!"


class _Scalar:
    """Annotation marker for a primitive; resolved per-struct into a _Prim."""

    __slots__ = ("code", "size", "name")

    def __init__(self, code: str, size: int, name: str) -> None:
        self.code, self.size, self.name = code, size, name

    def __mul__(self, count: int) -> Array:
        return Array(count, self)

    __rmul__ = __mul__

    def __repr__(self) -> str:
        return self.name


class Array:
    """Fixed-size array marker: ``Array(4, uint16_t)``, ``uint8_t * 4`` or ``Array(3)`` with ``list[T]``."""

    __slots__ = ("count", "elem")

    def __init__(self, count: int, elem: Any = None) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise TypeError("Array(N, ...) requires a positive integer N")
        self.count, self.elem = count, elem


uint8_t = _Scalar("B", 1, "uint8_t")
int8_t = _Scalar("b", 1, "int8_t")
uint16_t = _Scalar("H", 2, "uint16_t")
int16_t = _Scalar("h", 2, "int16_t")
uint32_t = _Scalar("I", 4, "uint32_t")
int32_t = _Scalar("i", 4, "int32_t")
uint64_t = _Scalar("Q", 8, "uint64_t")
int64_t = _Scalar("q", 8, "int64_t")
float32 = _Scalar("f", 4, "float32")
float64 = _Scalar("d", 8, "float64")


def _write_error(mv: memoryview, exc: Exception, what: str) -> Exception:
    if mv.readonly:
        return ReadOnlyError("cannot write to read-only memory")
    return PackingError(f"cannot store as {what}: {exc}")


# Resolved element descriptors share one protocol: size, align, get(mv, off), set(mv, off, value).


class _Prim:
    __slots__ = ("size", "align", "name", "unpack", "_pack")

    def __init__(self, scalar: _Scalar, endian: str) -> None:
        st = struct.Struct(endian + scalar.code)
        self.size = self.align = scalar.size
        self.name = scalar.name
        self.unpack = st.unpack_from
        self._pack = st.pack_into

    def get(self, mv: memoryview, off: int) -> Any:
        return self.unpack(mv, off)[0]

    def set(self, mv: memoryview, off: int, value: Any) -> None:
        try:
            self._pack(mv, off, value)
        except (struct.error, OverflowError, TypeError) as exc:
            raise _write_error(mv, exc, self.name) from None


class _Arr:
    __slots__ = ("elem", "count", "size", "align", "name")

    def __init__(self, elem: Any, count: int) -> None:
        self.elem, self.count = elem, count
        self.size, self.align = elem.size * count, elem.align
        self.name = f"{getattr(elem, 'name', 'struct')}[{count}]"

    def get(self, mv: memoryview, off: int) -> View:
        return View(self.elem, mv[off : off + self.size])

    def set(self, mv: memoryview, off: int, values: Any) -> None:
        values = list(values)
        if len(values) != self.count:
            raise PackingError(f"expected {self.count} elements, got {len(values)}")
        # shortcut: not atomic, a bad element leaves earlier ones written; upgrade if callers need rollback
        for i, v in enumerate(values):
            self.elem.set(mv, off + i * self.elem.size, v)
