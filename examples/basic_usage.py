from pyzerocopy import Endian, Struct, float32, uint32_t


class Particle(Struct, endian=Endian.LITTLE):
    x: float32
    y: float32
    z: float32
    mass: float32
    id: uint32_t


data = bytearray(Particle.sizeof() * 1000)
particles = Particle.view(data)  # no copy

particle = particles[0]
particle.x = 10.5  # writes into `data`
subset = particles[10:100]  # shares `data`
subset[0].id = 42

assert particles[10].id == 42 and data[:4] == bytes.fromhex("00002841")
print(particle, len(subset), particles.memory.obj is data)
binary = subset.to_bytes()  # copies the bytes
