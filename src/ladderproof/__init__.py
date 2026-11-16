"""Bounded exact static R-2R tolerance inspection."""
from .budget import Budget
from .design import Design, make_design, parse_design
from .solver import analyze
from .verifier import verify, compare

__version__='0.1.2.dev0'
__all__=['Budget','Design','make_design','parse_design','analyze','verify','compare']

from .catalog import search, chosen_certificate, parse_catalog
__all__ += ["search", "chosen_certificate", "parse_catalog"]
