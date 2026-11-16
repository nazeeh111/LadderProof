"""Bounded finite tolerance selection, outside the unchanged circuit kernels."""
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import product
from .budget import Budget
from .design import checked_design, rational
from .errors import Invalid, Refused
from .solver import analyze
from .verifier import verify

FORMAT = 'ladderproof.catalog.v1'
RESULT = 'ladderproof.catalog-result.v1'


@dataclass(frozen=True)
class Catalog:
    design: object
    options: tuple
    threshold_name: str
    threshold: F

    def to_dict(self):
        return {'format': FORMAT, 'design': self.design.to_dict(),
                'catalog': [{'id': resistor.id, 'options': [{'tolerance': str(t), 'cost': str(c)} for t,c in options]}
                            for resistor,options in zip(self.design.resistors,self.options)],
                self.threshold_name: str(self.threshold)}

    @property
    def minimum_step(self):
        if self.threshold_name == 'minimum_step_volts':
            return self.threshold
        return (self.threshold + 1) * self.design.vref / (1 << self.design.bits)

    def candidate(self, indices):
        data = self.design.to_dict()
        for resistor, options, index in zip(data['resistors'], self.options, indices):
            tolerance = options[index][0]
            nominal = F(resistor['nominal'])
            resistor.update(min=str(nominal*(1-tolerance)), max=str(nominal*(1+tolerance)))
        return checked_design(data)


def _limit(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise Invalid(f'{name} must be an integer from 1 through {maximum}')
    return value


def parse_catalog(value):
    if not isinstance(value,dict):
        raise Invalid('catalog request must be an object')
    thresholds = set(value) & {'minimum_step_volts', 'minimum_dnl_lsb'}
    if len(thresholds) != 1 or set(value) != {'format','design','catalog'} | thresholds or value['format'] != FORMAT:
        raise Invalid('expected catalog format, design, catalog and exactly one minimum_step_volts or minimum_dnl_lsb')
    design = checked_design(value['design'])
    name = thresholds.pop()
    threshold = rational(value[name], name)
    if not -10**6 <= threshold <= 10**6:
        raise Invalid('threshold magnitude must not exceed 1e6 in its declared units')
    raw = value['catalog']
    if not isinstance(raw,list) or len(raw) != len(design.resistors):
        raise Invalid('catalog requires every resistor in design order')
    options = []
    count = 1
    for resistor,item in zip(design.resistors,raw):
        if not isinstance(item,dict) or set(item) != {'id','options'} or item['id'] != resistor.id:
            raise Invalid(f'expected options for {resistor.id}')
        choices = item['options']
        if not isinstance(choices,list) or not 1 <= len(choices) <= 4:
            raise Invalid('each resistor requires one through four options')
        parsed = []
        for choice in choices:
            if not isinstance(choice,dict) or set(choice) != {'tolerance','cost'}:
                raise Invalid('each option requires only tolerance and cost')
            tolerance = rational(choice['tolerance'],'tolerance')
            cost = rational(choice['cost'],'cost')
            if not 0 <= tolerance < 1 or not 0 <= cost <= 10**12:
                raise Invalid('tolerance must be in [0,1); cost must be in [0,1e12] user-defined units')
            # Validate derived ranges once, including the existing exact-size limits.
            data = design.to_dict()
            index = len(options)
            data['resistors'][index].update(min=str(resistor.nominal*(1-tolerance)),max=str(resistor.nominal*(1+tolerance)))
            checked_design(data)
            parsed.append((tolerance,cost))
        options.append(tuple(parsed)); count *= len(parsed)
        if count > 4096:
            raise Invalid('catalog exceeds 4096 combinations')
    return Catalog(design,tuple(options),name,threshold)


def search(request, *, budget=None, max_designs=128, max_corner_solves=1_048_576):
    """First verified feasible item in exact (cost, original-index) order.

    A budget stop returns unfinished, never infeasible. Certificates are complete
    individually; no partially checked candidate can become a selection.
    """
    budget = budget or Budget()
    _limit(max_designs,'max_designs',4096)
    _limit(max_corner_solves,'max_corner_solves',2_097_152)
    catalog = parse_catalog(request)
    ordered = sorted((sum((options[i][1] for options,i in zip(catalog.options,indices)),F(0)),indices)
                     for indices in product(*(range(len(options)) for options in catalog.options)))
    result = {'format':RESULT, 'request':catalog.to_dict(), 'status':'unfinished', 'optimal':False,
              'reason':None, 'selection':None,
              'work':{'total_designs':len(ordered),'attempted_designs':0,'verified_designs':0,
                      'reserved_corner_solves':0,'max_designs':max_designs,'max_corner_solves':max_corner_solves}}
    work = result['work']
    try:
        budget.check()
        for cost,indices in ordered:
            budget.check()
            design = catalog.candidate(indices)
            # Reserve both independent passes before admitting one candidate.
            needed = 2 * design.corner_count
            if work['attempted_designs'] >= max_designs or work['reserved_corner_solves'] + needed > max_corner_solves:
                result['reason'] = 'work-limit'
                return result
            work['attempted_designs'] += 1
            work['reserved_corner_solves'] += needed
            certificate = analyze(design,budget=budget)
            checked = verify(certificate,budget=budget)
            work['verified_designs'] += 1
            if F(checked['worst_transition']['step']) >= catalog.minimum_step:
                result.update(status='optimal',optimal=True,reason='first-feasible-in-cost-order',
                              selection={'indices':list(indices),'cost':str(cost),'certificate':certificate})
                return result
        result.update(status='infeasible',reason='exhausted-catalog')
        return result
    except Refused as exc:
        result['reason'] = str(exc)
        return result


def chosen_certificate(record, *, budget=None):
    """Validate selection binding and feasibility, not a saved optimality claim.

    Search reports are replayable evidence, not a new proof-certificate format.
    Re-run search on their request to re-establish global catalog optimality.
    """
    from .verifier import _bounded_record
    from copy import deepcopy
    _bounded_record(record)
    record = deepcopy(record)
    if not isinstance(record,dict) or record.get('format') != RESULT:
        raise Invalid('expected a catalog search result')
    catalog = parse_catalog(record.get('request'))
    selected = record.get('selection')
    if not isinstance(selected,dict) or set(selected) != {'indices','cost','certificate'}:
        raise Invalid('no complete selection in this search result')
    indices = selected['indices']
    if not isinstance(indices,list) or len(indices) != len(catalog.options) or any(type(i) is not int or not 0 <= i < len(options) for options,i in zip(catalog.options,indices)):
        raise Invalid('invalid selected option indices')
    design = catalog.candidate(indices)
    cost = sum((options[i][1] for options,i in zip(catalog.options,indices)),F(0))
    if selected['cost'] != str(cost):
        raise Invalid('selected cost differs from declared catalog')
    checked = verify(selected['certificate'],budget=budget)
    if selected['certificate']['design'] != design.to_dict() or F(checked['worst_transition']['step']) < catalog.minimum_step:
        raise Invalid('selected certificate does not meet its exact catalog request')
    # Return a fresh detached record, never caller-owned mutable source state.
    return selected['certificate']
