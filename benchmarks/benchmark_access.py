"""pyzerocopy vs structed vs raw struct. Run: python benchmarks/benchmark_access.py [N]"""

import struct
import sys
import time

from pyzerocopy import Endian, Struct, float32, uint32_t

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000


class Particle(Struct, endian=Endian.LITTLE):
    x: float32
    y: float32
    z: float32
    mass: float32
    id: uint32_t


def timeit(label, fn, ops):
    t = time.perf_counter()
    fn()
    dt = time.perf_counter() - t
    print(f"{label:<34}{ops / dt / 1e6:8.2f} Mops/s {dt / ops * 1e9:9.0f} ns/op")


def main():
    size = Particle.sizeof()
    data = bytearray(size * N)
    print(f"records={N} record_size={size}B python={sys.version.split()[0]}")

    t = time.perf_counter()
    view = Particle.view(data)
    print(f"{'pyzerocopy construction':<34}{(time.perf_counter() - t) * 1e6:8.1f} us (independent of N)")

    def zc_index_read():
        for i in range(N):
            view[i].x

    def zc_iter_read():
        for r in view:
            r.x

    def zc_write():
        for i in range(N):
            view[i].x = 1.5

    def zc_slice():
        for _ in range(N):
            view[10:100]

    st = struct.Struct("<ffffI")

    def struct_read():
        for i in range(N):
            st.unpack_from(data, i * size)[0]

    def struct_write():
        pk = struct.Struct("<f").pack_into
        for i in range(N):
            pk(data, i * size, 1.5)

    timeit("pyzerocopy view[i].x read", zc_index_read, N)
    timeit("pyzerocopy iterate + .x read", zc_iter_read, N)
    timeit("pyzerocopy view[i].x = v write", zc_write, N)
    timeit("pyzerocopy view[a:b] slice", zc_slice, N)
    timeit("struct.unpack_from (baseline)", struct_read, N)
    timeit("struct.pack_into (baseline)", struct_write, N)

    try:
        import structed

        class SP(structed.Struct, endian=structed.Endian.LITTLE):
            x: structed.float32
            y: structed.float32
            z: structed.float32
            mass: structed.float32
            id: structed.uint32_t

        blob = bytes(data)

        def structed_read():
            for i in range(N):
                SP.unpack_from(blob, i * size).x

        timeit("structed unpack_from(...).x (copy)", structed_read, N)
    except ImportError:
        print("structed not installed; skipped")

    try:
        import numpy as np

        arr = np.frombuffer(
            data, dtype=np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("mass", "<f4"), ("id", "<u4")])
        )

        def np_read():
            for i in range(N):
                arr[i]["x"]

        timeit("numpy structured arr[i]['x']", np_read, N)
    except ImportError:
        print("numpy not installed; skipped")


main()
