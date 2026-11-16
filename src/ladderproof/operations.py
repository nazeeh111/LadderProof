"""One operation boundary for CLI and isolated HTTP workers."""
from .errors import Invalid


def execute(operation, payload, *, budget):
    from . import analyze, verify, compare
    from .catalog import search, chosen_certificate
    if operation == 'analyze':
        return analyze(payload['design'],budget=budget)
    if operation == 'verify':
        return verify(payload['certificate'],budget=budget)
    if operation == 'compare':
        return compare(payload['before'],payload['after'],budget=budget)
    if operation == 'catalog':
        return search(payload['request'],budget=budget,max_designs=payload.get('max_designs',128),
                      max_corner_solves=payload.get('max_corner_solves',1_048_576))
    if operation == 'choose':
        return chosen_certificate(payload['selection'],budget=budget)
    raise Invalid('unsupported operation')
