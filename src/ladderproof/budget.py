"""Bounded cooperative execution; KeyboardInterrupt remains native cancellation."""
import math
from time import monotonic
from .errors import Invalid, Refused

class Budget:
    def __init__(self, seconds=30.0, cancel=None):
        if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not 0 < seconds <= 120:
            raise Invalid('seconds must be finite, greater than zero and at most 120')
        if cancel is not None and not callable(cancel):
            raise Invalid('cancel must be a callable or None')
        self.deadline=monotonic()+seconds
        self.cancel=cancel

    def check(self):
        if self.cancel is not None and self.cancel():
            raise Refused('computation cancelled; no complete certificate produced')
        if monotonic() >= self.deadline:
            raise Refused('deadline reached; no complete certificate produced')
