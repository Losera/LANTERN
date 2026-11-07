"""The explicit-unknown sentinel, kept in its own module so anything may use it.

docs/evaluation.md: "Any missing value remains explicitly unknown." That rules
out the usual conveniences. ``0`` for an unmeasured token count, ``""`` for an
unrecorded revision, or ``None`` doing double duty as both "absent" and
"legitimately null" all turn a gap into a datum, and a datum survives into the
export looking like a measurement.

So gaps get a distinct type. Two deliberate design choices:

* :class:`Unknown` does **not** define ``__bool__``, so it is truthy. A falsy
  sentinel would make ``value or 0`` quietly substitute a default -- exactly
  the bug this module exists to prevent.
* It does not define arithmetic or comparison, so an unknown runtime cannot be
  summed or ranked by accident. A ``TypeError`` at the point of misuse is the
  cheapest possible verification.

On the wire an unknown serialises as ``null`` *and* is named in the record's
``unknown`` list, so a reader never has to guess whether a null meant "missing"
or "measured as nothing".
"""

from __future__ import annotations

from typing import Any, Final


class Unknown:
    """A value that was not observed. Singleton; use :data:`UNKNOWN`."""

    __slots__ = ()
    _instance: "Unknown | None" = None

    def __new__(cls) -> "Unknown":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNKNOWN"

    def __str__(self) -> str:
        return "unknown"

    def __reduce__(self):
        return (Unknown, ())


#: The single unknown value. Compare with ``isinstance(x, Unknown)`` or ``is``.
UNKNOWN: Final[Unknown] = Unknown()


def encode(value: Any) -> Any:
    """Convert a value for JSON, mapping :data:`UNKNOWN` to ``null``."""
    return None if isinstance(value, Unknown) else value


def is_known(value: Any) -> bool:
    """True when a value was actually observed."""
    return not isinstance(value, Unknown)


__all__ = ["Unknown", "UNKNOWN", "encode", "is_known"]
