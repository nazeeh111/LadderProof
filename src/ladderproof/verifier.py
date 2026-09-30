"""Independent full recomputation by backward Thevenin ladder reductions.

This module deliberately imports no solver or result-aggregation implementation.
It reuses only the admitted-input parser and resource boundary.
"""
from fractions import Fraction
from .budget import Budget
from .design import parse_design
from .errors import Invalid, VerificationError


def _reduce(bits, values):
    # Last bit branch and termination are two voltage sources in parallel.
    # Walk leftward, replacing the right-hand ladder by its Thevenin source.
    branch=values[bits-1]; termination=values[-1]
    equivalent=branch*termination/(branch+termination)
    coefficients=[Fraction(0)]*bits
    coefficients[-1]=termination/(branch+termination)
    for node in range(bits-2,-1,-1):
        path=values[bits+node]+equivalent
        branch=values[node]
        divisor=branch+path
        coefficients=[weight*branch/divisor for weight in coefficients]
        coefficients[node]=path/divisor
        equivalent=branch*path/divisor
    return coefficients


def _code_values(coefficients, reference):
    # Independent direct binary-input sum, rather than incremental output cache.
    n=len(coefficients)
    return [reference*sum((coefficients[j] for j in range(n) if code & (1<<(n-j-1))),Fraction(0))
            for code in range(1<<n)]


def _bounded_record(value):
    # The public library receives already decoded objects, so impose structural
    # limits without serializing an attacker-controlled deeply nested object.
    pending=[(value,0)]; count=0
    while pending:
        current,depth=pending.pop(); count+=1
        if count>10_000 or depth>12: raise VerificationError('certificate exceeds structural limits')
        if isinstance(current,dict):
            if len(current)>256 or any(not isinstance(k,str) or len(k)>120 for k in current):
                raise VerificationError('certificate contains unsupported object keys')
            pending.extend((v,depth+1) for v in current.values())
        elif isinstance(current,list):
            if len(current)>256: raise VerificationError('certificate array exceeds supported model')
            pending.extend((v,depth+1) for v in current)
        elif isinstance(current,str):
            if len(current)>2000: raise VerificationError('certificate text is too large')
        elif type(current) not in (int,bool,type(None)):
            raise VerificationError('certificate contains an unsupported JSON value')
        elif type(current) is int and current.bit_length()>128:
            raise VerificationError('certificate integer is too large')


def verify(certificate, *, budget=None):
    budget=budget or Budget(); budget.check()
    _bounded_record(certificate)
    if not isinstance(certificate,dict) or set(certificate)!={'format','algorithm','status','design','corner_count','results'}:
        raise VerificationError('certificate has missing or extra fields')
    if certificate['format']!='ladderproof.certificate.v1' or certificate['algorithm']!='exact-corners-v1' or certificate['status']!='complete':
        raise VerificationError('unsupported or incomplete certificate')
    try: design=parse_design(certificate['design'])
    except Invalid as exc: raise VerificationError(f'invalid certificate design: {exc}') from exc
    if certificate['design']!=design.to_dict(): raise VerificationError('design must use its canonical exact representation')
    if type(certificate['corner_count']) is not int or certificate['corner_count']!=design.corner_count:
        raise VerificationError('corner count does not cover the complete independent interval box')
    n=design.bits; count=1<<n
    lower_codes=[None]*count; upper_codes=[None]*count; lower_masks=[None]*count; upper_masks=[None]*count
    lower_steps=[None]*(count-1); upper_steps=[None]*(count-1); low_step_masks=[None]*(count-1); high_step_masks=[None]*(count-1)
    uncertain=[i for i,r in enumerate(design.resistors) if r.lo!=r.hi]
    worst_values=None; worst_mask=None; worst_index=None; smallest=None
    for mask in range(1<<len(uncertain)):
        budget.check()
        resistances=[r.lo for r in design.resistors]
        for place,index in enumerate(uncertain):
            resistances[index]=design.resistors[index].hi if mask & (1<<place) else design.resistors[index].lo
        values=_code_values(_reduce(n,resistances),design.vref)
        for code,value in enumerate(values):
            if lower_codes[code] is None or value<lower_codes[code]: lower_codes[code]=value; lower_masks[code]=mask
            if upper_codes[code] is None or value>upper_codes[code]: upper_codes[code]=value; upper_masks[code]=mask
        for code in range(count-1):
            step=values[code+1]-values[code]
            if lower_steps[code] is None or step<lower_steps[code]: lower_steps[code]=step; low_step_masks[code]=mask
            if upper_steps[code] is None or step>upper_steps[code]: upper_steps[code]=step; high_step_masks[code]=mask
    budget.check()
    # Solver's stable tie convention: lowest transition code, then lowest mask.
    worst_index=min(range(count-1),key=lambda i:lower_steps[i]); worst_mask=low_step_masks[worst_index]
    resistances=[r.lo for r in design.resistors]
    for place,index in enumerate(uncertain):
        if worst_mask & (1<<place): resistances[index]=design.resistors[index].hi
    worst_values=_code_values(_reduce(n,resistances),design.vref)
    smallest=lower_steps[worst_index]
    expected={'nominal':[str(v) for v in _code_values(_reduce(n,[r.nominal for r in design.resistors]),design.vref)],
              'codes':[{'code':i,'min':str(lower_codes[i]),'max':str(upper_codes[i]),'min_corner':lower_masks[i],'max_corner':upper_masks[i]} for i in range(count)],
              'steps':[{'from':i,'to':i+1,'min':str(lower_steps[i]),'max':str(upper_steps[i]),'min_corner':low_step_masks[i],'max_corner':high_step_masks[i]} for i in range(count-1)],
              'nondecreasing':smallest>=0,
              'worst_transition':{'from':worst_index,'to':worst_index+1,'step':str(smallest),'corner':worst_mask,
                    'from_voltage':str(worst_values[worst_index]),'to_voltage':str(worst_values[worst_index+1]),
                    'dnl_lsb':str(smallest/(design.vref/Fraction(count))-1),
                    'resistors':[{'id':r.id,'value':str(v)} for r,v in zip(design.resistors,resistances)]}}
    # Python equality equates bool/int; require exact primitive types as well.
    def same(a,b):
        if type(a) is not type(b): return False
        if isinstance(a,dict): return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
        if isinstance(a,list): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
        return a==b
    if not same(certificate['results'],expected):
        raise VerificationError('certificate results do not match independent complete recomputation')
    budget.check()
    return {'status':'verified','corner_count':design.corner_count,'bits':n,
            'nondecreasing':expected['nondecreasing'],'worst_transition':expected['worst_transition']}


def compare(before,after, *, budget=None):
    budget=budget or Budget(seconds=60)
    left=verify(before,budget=budget); right=verify(after,budget=budget)
    if left['bits']!=right['bits']: raise Invalid('comparison requires the same ladder bit count')
    budget.check()
    return {'status':'verified-comparison','before':left,'after':right,
            'minimum_step_change_volts':str(Fraction(right['worst_transition']['step'])-Fraction(left['worst_transition']['step']))}
