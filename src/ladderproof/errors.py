"""Public error categories used by library and CLI."""
class Invalid(ValueError):
    """Malformed or unsupported declarative input."""

class Refused(RuntimeError):
    """An analysis did not complete within its allowed resources."""

class VerificationError(ValueError):
    """A certificate is malformed or its claims do not match recomputation."""
