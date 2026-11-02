from __future__ import annotations

import inspect
from typing import Annotated, Any, get_args, get_origin

from .exceptions import PackingError
from .types import Array, Endian, _Arr, _Prim, _Scalar, _write_error
from .view import View


class _Nested:
    """Element descriptor for a Struct class (used for views, arrays and nested fields)."""

    __slots__ = ("cls", "size", "align", "name")

    def __init__(self, cls: Any, size: int, align: int) -> None:
        self.cls, self.size, self.align, self.name = cls, size, align, cls.__name__

    def get(self, mv: memoryview, off: int) -> Any:
        return self.cls(mv, off)

    def set(self, mv: memoryview, off: int, value: Any) -> None:
        if type(value) is not self.cls:
            raise PackingError(f"expected a {self.name} record, got {type(value).__name__}")
        src = value.memory
        try:
            mv[off : off + self.size] = src  # in-buffer memcpy, overlap-safe
        except TypeError as exc:
            raise _write_error(mv, exc, self.name) from None


class _Field:
    """Data descriptor: reads/writes straight from the record's memoryview."""

    __slots__ = ("name", "offset", "t")

    def __init__(self, name: str, offset: int, t: Any) -> None:
        self.name, self.offset, self.t = name, offset, t

    def __get__(self, obj: Any, owner: Any = None) -> Any:
        if obj is None:
            return self
        return self.t.get(obj._mv, obj._off + self.offset)

    def __set__(self, obj: Any, value: Any) -> None:
        self.t.set(obj._mv, obj._off + self.offset, value)


class _PrimField(_Field):
    """Hot-path variant: skips one call layer for scalar reads."""

    __slots__ = ("unpack",)

    def __init__(self, name: str, offset: int, t: _Prim) -> None:
        super().__init__(name, offset, t)
        self.unpack = t.unpack

    def __get__(self, obj: Any, owner: Any = None) -> Any:
        if obj is None:
            return self
        return self.unpack(obj._mv, obj._off + self.offset)[0]


def _resolve(ann: Any, endian: str, where: str) -> Any:
    base = None
    if get_origin(ann) is Annotated:
        base, *meta = get_args(ann)
        ann = next((m for m in meta if isinstance(m, (_Scalar, Array))), base)
    if isinstance(ann, _Scalar):
        return _Prim(ann, endian)
    if isinstance(ann, Array):
        elem = ann.elem
        if elem is None:
            args = get_args(base) if get_origin(base) is list else ()
            if not args:
                raise TypeError(f"{where}: Array({ann.count}) needs an element type or list[T]")
            elem = args[0]
        return _Arr(_resolve(elem, endian, where), ann.count)
    if isinstance(ann, StructMeta) and hasattr(ann, "_elem"):
        return ann._elem  # nested structs keep their own endian
    raise TypeError(f"{where}: unsupported field type {ann!r}")


class StructMeta(type):
    def __new__(
        mcs, name: str, bases: tuple[type, ...], ns: dict[str, Any], endian: Endian = Endian.LITTLE, packed: bool = True
    ) -> StructMeta:
        ns.setdefault("__slots__", ())  # records must not carry a per-instance __dict__
        return super().__new__(mcs, name, bases, ns)

    def __init__(
        cls, name: str, bases: tuple[type, ...], ns: dict[str, Any], endian: Endian = Endian.LITTLE, packed: bool = True
    ) -> None:
        super().__init__(name, bases, ns)
        if not any(isinstance(b, StructMeta) for b in bases):
            return  # the Struct base class itself
        prefix = Endian(endian).value
        offset, max_align = 0, 1
        for fname, ann in inspect.get_annotations(cls, eval_str=True).items():
            t = _resolve(ann, prefix, f"{name}.{fname}")
            if not packed:
                offset = -(-offset // t.align) * t.align
            field = (_PrimField if isinstance(t, _Prim) else _Field)(fname, offset, t)
            setattr(cls, fname, field)
            offset += t.size
            max_align = max(max_align, t.align)
        if offset == 0:
            raise TypeError(f"{name}: a Struct needs at least one field")
        if not packed:
            offset = -(-offset // max_align) * max_align
        cls._elem = _Nested(cls, offset, max_align if not packed else 1)
        cls._fields = tuple(k for k, v in vars(cls).items() if isinstance(v, _Field))


class Struct(metaclass=StructMeta):
    """Declare a binary layout with annotations; ``view`` it over existing memory.

    Instances are lightweight record proxies (two slots: memoryview + offset),
    not copies: field reads/writes go straight to the underlying buffer.

        class Particle(Struct, endian=Endian.LITTLE):
            x: float32
            id: uint32_t
    """

    __slots__ = ("_mv", "_off")
    _elem: _Nested  # set per subclass by StructMeta
    _fields: tuple[str, ...]

    def __init__(self, mv: memoryview, off: int = 0) -> None:
        self._mv, self._off = mv, off

    @classmethod
    def sizeof(cls) -> int:
        return cls._elem.size

    @classmethod
    def view(cls, data: Any, offset: int = 0, count: int | None = None) -> View:
        """Zero-copy view of ``data`` (any C-contiguous buffer) as a sequence of records.

        The view keeps ``data`` alive; a bytearray stays pinned (cannot be
        resized) while views exist. ``offset`` skips a header; ``count`` limits
        the records (default: the rest of the buffer, which must be a whole
        number of records). Raises ValueError on a bad offset/count/length.
        """
        if cls is Struct:
            raise TypeError("view() must be called on a Struct subclass")
        mv = memoryview(data)
        if not mv.c_contiguous:
            raise ValueError("buffer must be C-contiguous")
        if mv.format != "B" or mv.ndim != 1:
            mv = mv.cast("B")  # still zero-copy, same exporter
        size = cls._elem.size
        if not 0 <= offset <= len(mv):
            raise ValueError(f"offset {offset} outside buffer of {len(mv)} bytes")
        if count is None:
            if (len(mv) - offset) % size:
                raise ValueError(f"{len(mv) - offset} bytes is not a multiple of {cls.__name__}.sizeof() = {size}")
            count = (len(mv) - offset) // size
        elif count < 0 or offset + count * size > len(mv):
            raise ValueError(f"{count} records at offset {offset} exceed buffer of {len(mv)} bytes")
        return View(cls._elem, mv[offset : offset + count * size])

    @property
    def memory(self) -> memoryview:
        """This record's bytes as a zero-copy memoryview slice."""
        return self._mv[self._off : self._off + self._elem.size]

    def to_bytes(self) -> bytes:
        """Explicit copy of this record's bytes."""
        return bytes(self.memory)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f'{f}={getattr(self, f)!r}' for f in self._fields)})"
