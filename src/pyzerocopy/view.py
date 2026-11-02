from __future__ import annotations

import operator
from collections.abc import Iterator
from typing import Any


class View:
    """Zero-copy sequence of fixed-size elements over a memoryview.

    Used both for ``Struct.view(data)`` and for array fields. Indexing and
    slicing never copy the underlying bytes; slices are ``View``s over a
    sliced memoryview of the same exporter. Reading a scalar necessarily
    creates a Python int/float; ``to_bytes()`` is the only method that copies.
    """

    __slots__ = ("_elem", "_mv", "_size", "_len")

    def __init__(self, elem: Any, mv: memoryview) -> None:
        self._elem = elem
        self._mv = mv
        self._size: int = elem.size
        self._len: int = len(mv) // self._size

    @property
    def memory(self) -> memoryview:
        """The underlying memoryview (same exporter, same mutability)."""
        return self._mv

    def __len__(self) -> int:
        return self._len

    def _offset(self, i: Any) -> int:
        i = int(operator.index(i))
        if i < 0:
            i += self._len
        if not 0 <= i < self._len:
            raise IndexError("index out of range")
        return int(i * self._size)

    def __getitem__(self, i: Any) -> Any:
        if isinstance(i, slice):
            start, stop, step = i.indices(self._len)
            if step != 1:
                raise ValueError("strided slices are not supported")
            stop = max(start, stop)
            return View(self._elem, self._mv[start * self._size : stop * self._size])
        return self._elem.get(self._mv, self._offset(i))

    def __setitem__(self, i: Any, value: Any) -> None:
        if isinstance(i, slice):
            raise TypeError("slice assignment is not supported")
        self._elem.set(self._mv, self._offset(i), value)

    def __iter__(self) -> Iterator[Any]:
        get, mv = self._elem.get, self._mv
        for off in range(0, self._len * self._size, self._size):
            yield get(mv, off)

    def to_bytes(self) -> bytes:
        """Explicit copy of the viewed bytes."""
        return bytes(self._mv)

    def __repr__(self) -> str:
        return f"<View of {self._len} x {getattr(self._elem, 'name', type(self._elem).__name__)}>"
