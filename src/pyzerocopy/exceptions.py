class PyZeroCopyError(Exception):
    """Base class for all pyzerocopy errors."""


class PackingError(PyZeroCopyError, ValueError):
    """A value does not fit its field (wrong type, out of range, wrong array length)."""


class ReadOnlyError(PyZeroCopyError, TypeError):
    """A write was attempted through a view over read-only memory."""
