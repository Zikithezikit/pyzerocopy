# Changelog

All notable changes are listed here. Format based on [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

## 0.1.0

### Added
- `Struct` classes declared with annotations, with `endian=` and `packed=` options.
- `Struct.view(data, offset=0, count=None)` for zero-copy access to any C-contiguous buffer.
- Record proxies, zero-copy slicing and iteration.
- Integer and float primitives, fixed-size arrays and nested structs.
- `PackingError`, `ReadOnlyError` and read-only buffer protection.
