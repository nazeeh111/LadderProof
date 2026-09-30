"""Exact nodal solution and exhaustive independent-box extrema."""
from fractions import Fraction as F
from .budget import Budget
from .design import checked_design
from .errors import Invalid

CERTIFICATE_FORMAT='ladderproof.certificate.v1'
ALGORITHM='exact-corners-v1'


def _weights(bits, resistances):
    # Reduced symmetric nodal conductance matrix. The inverse's first row
    # is found by A y = e0; w_i = y_i / B_i gives each input's output weight.
    matrix=[[F(0) for _ in range(bits+1)] for _ in range(bits)]
    for i in range(bits): matrix[i][i]+=1/resistances[i]
    matrix[-1][bits-1]+=1/resistances[-1]
    for i in range(bits-1):
        g=1/resistances[bits+i]
        matrix[i][i]+=g; matrix[i+1][i+1]+=g
        matrix[i][i+1]-=g; matrix[i+1][i]-=g
    matrix[0][-1]=F(1)
    for col in range(bits):
        pivot=matrix[col][col]
        if not pivot: raise Invalid('singular model')
        matrix[col]=[v/pivot for v in matrix[col]]
        for row in range(bits):
            if row==col: continue
            factor=matrix[row][col]
            if factor: matrix[row]=[a-factor*b for a,b in zip(matrix[row],matrix[col])]
    return [matrix[i][-1]/resistances[i] for i in range(bits)]


def _outputs(weights, vref):
    size=1<<len(weights); values=[F(0)]*size
    for code in range(1,size):
        one=code & -code
        values[code]=values[code-one]+vref*weights[len(weights)-one.bit_length()]
    return values


def _assignment(design, mask):
    values=[r.lo for r in design.resistors]
    for bit,i in enumerate(design.uncertain):
        if mask & (1<<bit): values[i]=design.resistors[i].hi
    return values


def analyze(design, *, budget=None):
    budget=budget or Budget()
    budget.check(); d=checked_design(design)
    size=1<<d.bits
    nominal=_outputs(_weights(d.bits,[r.nominal for r in d.resistors]),d.vref)
    codes=[{'code':i,'min':None,'max':None,'min_corner':None,'max_corner':None} for i in range(size)]
    steps=[{'from':i,'to':i+1,'min':None,'max':None,'min_corner':None,'max_corner':None} for i in range(size-1)]
    for mask in range(d.corner_count):
        budget.check()
        values=_outputs(_weights(d.bits,_assignment(d,mask)),d.vref)
        for records,samples in ((codes,values),(steps,[b-a for a,b in zip(values,values[1:])])):
            for record,value in zip(records,samples):
                if record['min'] is None or value<record['min']:
                    record['min']=value; record['min_corner']=mask
                if record['max'] is None or value>record['max']:
                    record['max']=value; record['max_corner']=mask
    budget.check()
    worst=min(steps,key=lambda s:s['min']); mask=worst['min_corner']
    assignment=_assignment(d,mask); output=_outputs(_weights(d.bits,assignment),d.vref)
    witness={'from':worst['from'],'to':worst['to'],'step':str(worst['min']),'corner':mask,
             'from_voltage':str(output[worst['from']]),'to_voltage':str(output[worst['to']]),
             'dnl_lsb':str(worst['min']/(d.vref/F(size))-1),
             'resistors':[{'id':r.id,'value':str(v)} for r,v in zip(d.resistors,assignment)]}
    for record in codes+steps:
        record['min']=str(record['min']); record['max']=str(record['max'])
    result={'nominal':[str(v) for v in nominal],'codes':codes,'steps':steps,
            'worst_transition':witness,'nondecreasing':F(witness['step'])>=0}
    budget.check()
    return {'format':CERTIFICATE_FORMAT,'algorithm':ALGORITHM,'status':'complete',
            'design':d.to_dict(),'corner_count':d.corner_count,'results':result}
