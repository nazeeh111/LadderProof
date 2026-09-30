"""Exact declarative model with explicitly bounded input and topology."""
from dataclasses import dataclass
from fractions import Fraction
import re
from .errors import Invalid

FORMAT='ladderproof.design.v1'
MODEL='ideal-static-r2r-voltage'
MAX_INPUT_BYTES=1_048_576
NUMBER=re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]{1,12})?|[0-9]+/[0-9]+)\Z',re.ASCII)


def rational(value, label='number'):
    if not isinstance(value,str) or not 1 <= len(value) <= 80 or not NUMBER.fullmatch(value):
        raise Invalid(f'{label} must be an exact integer, decimal (at most 12 places), or fraction string')
    try:
        result=Fraction(value)
    except (ValueError,ZeroDivisionError) as exc:
        raise Invalid(f'{label} is not a finite rational') from exc
    if result.numerator.bit_length()>64 or result.denominator.bit_length()>64:
        raise Invalid(f'{label} numerator and denominator must each fit 64 bits')
    return result

@dataclass(frozen=True)
class Resistor:
    id: str
    nominal: Fraction
    lo: Fraction
    hi: Fraction

@dataclass(frozen=True)
class Design:
    bits: int
    vref: Fraction
    resistors: tuple
    title: str='R-2R ladder'

    @property
    def uncertain(self):
        return tuple(i for i,r in enumerate(self.resistors) if r.lo!=r.hi)

    @property
    def corner_count(self):
        return 1 << len(self.uncertain)

    def to_dict(self):
        return {'format':FORMAT,'model':MODEL,'title':self.title,'bits':self.bits,'vref':str(self.vref),
                'resistors':[{'id':r.id,'nominal':str(r.nominal),'min':str(r.lo),'max':str(r.hi)} for r in self.resistors]}


def parse_design(data):
    if not isinstance(data,dict): raise Invalid('design must be a JSON object')
    required={'format','model','bits','vref','resistors'}
    if not required <= data.keys() or data.keys()-required-{'title'}:
        raise Invalid('design has missing or unsupported fields; correlations and arbitrary topologies are unsupported')
    if data['format']!=FORMAT or data['model']!=MODEL:
        raise Invalid('unsupported design format or circuit model')
    n=data['bits']
    if type(n) is not int or not 2 <= n <= 6: raise Invalid('bits must be an integer from 2 through 6')
    title=data.get('title','R-2R ladder')
    if not isinstance(title,str) or len(title)>120 or any(ord(c)<32 for c in title):
        raise Invalid('title must be at most 120 characters without control characters')
    vref=rational(data['vref'],'vref')
    if not Fraction(1,10**9) <= vref <= 10**6: raise Invalid('vref must be from 1e-9 through 1e6 volts')
    raw=data['resistors']; ids=[f'B{i}' for i in range(n)]+[f'S{i}' for i in range(n-1)]+['T']
    if not isinstance(raw,list) or len(raw)!=2*n: raise Invalid(f'exactly {2*n} ordered resistors are required')
    parsed=[]
    for item,expected in zip(raw,ids):
        if not isinstance(item,dict) or set(item)!={'id','nominal','min','max'} or item['id']!=expected:
            raise Invalid(f'expected resistor {expected} with only id, nominal, min and max fields')
        nominal=rational(item['nominal'],f'{expected}.nominal')
        lo=rational(item['min'],f'{expected}.min'); hi=rational(item['max'],f'{expected}.max')
        if not Fraction(1,10**9) <= lo <= nominal <= hi <= 10**12:
            raise Invalid(f'{expected} requires 1e-9 <= min <= nominal <= max <= 1e12 ohms')
        parsed.append(Resistor(expected,nominal,lo,hi))
    return Design(n,vref,tuple(parsed),title)


def make_design(bits=6,tolerance='1/100',vref='1'):
    if type(bits) is not int or not 2<=bits<=6: raise Invalid('bits must be an integer from 2 through 6')
    t=rational(tolerance,'tolerance')
    if not 0<=t<1: raise Invalid('tolerance must be nonnegative and smaller than one')
    ids=[f'B{i}' for i in range(bits)]+[f'S{i}' for i in range(bits-1)]+['T']
    values=[Fraction(2000)]*bits+[Fraction(1000)]*(bits-1)+[Fraction(2000)]
    d={'format':FORMAT,'model':MODEL,'title':f'{bits}-bit R-2R ladder','bits':bits,'vref':vref,
       'resistors':[{'id':i,'nominal':str(r),'min':str(r*(1-t)),'max':str(r*(1+t))} for i,r in zip(ids,values)]}
    return parse_design(d).to_dict()


def checked_design(value):
    # Even manually constructed dataclasses must pass the public contract.
    return parse_design(value.to_dict() if isinstance(value,Design) else value)
