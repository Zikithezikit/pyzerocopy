# pyzerocopy

Zero-copy structured buffers for Python. Declare layouts with class annotations, then read and write fields directly in existing memory.

```python
from pyzerocopy import Struct, Endian, float32, uint32_t


class Particle(Struct, endian=Endian.LITTLE):
    x: float32
    y: float32
    id: uint32_t


data = bytearray(Particle.sizeof() * 1000)
particles = Particle.view(data)  # never copies
particles[0].x = 10.5  # writes into `data`
subset = particles[10:100]  # shares `data`
binary = subset.to_bytes()  # explicit copy, the only one
```

- `Particle.view(mm, offset=16, count=100)` views part of a buffer (e.g. an mmap file with a header).
- Types: `uint8_t..uint64_t`, `int8_t..int64_t`, `float32`, `float64`; arrays (`uint8_t * 4`, `Array(4, uint16_t)`, `Annotated[list[int], Array(...)]`); nested structs.
- Options: `endian=` `LITTLE` (default) / `BIG` / `NATIVE` / `NETWORK`; `packed=True` (default) or `False` for natural C alignment.
- Read-only buffers (`bytes`, read-only `mmap`) can be read; writes raise `ReadOnlyError`. Bad values raise `PackingError`.
- Reading a scalar creates a Python int/float; array fields and nested structs return views, not copies.
- A view pins its exporter (a `bytearray` can't be resized while views exist).

Install: `pip install -e .[dev]`, test: `pytest`, benchmark: `python benchmarks/benchmark_access.py`. Python 3.10+.

## Performance

Measured with `python benchmarks/benchmark_access.py 300000` (Python 3.14, one run, your numbers will differ):
about 480 ns per `view[i].x` read and 520 ns per write; raw `struct.unpack_from` is about 140 ns, so the
proxy costs roughly 3x over hand-rolled offsets in exchange for named fields. Construction is O(1).

## Limits

- No strided slices, no `char`/string fields, no variable-length fields.
- Array assignment (`rec.arr = [...]`) is not atomic: a bad element leaves earlier ones written.
- `bytearray` exporters can't be resized while a view exists (by design: no dangling memory).

## License

MIT
