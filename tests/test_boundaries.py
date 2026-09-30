"""These fixtures catch strictness, shared-coordinate and topology/order mistakes."""
import copy
from fractions import Fraction as F
import random
import unittest
from ladderproof import Budget, analyze, make_design, parse_design, verify
from ladderproof.errors import Invalid, Refused, VerificationError

class BoundaryTests(unittest.TestCase):
    def test_zero_step_is_nondecreasing_and_worst_may_be_non_major_carry(self):
        d=make_design(2,'0','1')
        for r,value in zip(d['resistors'],['3','1','1','1']): r.update(nominal=value,min=value,max=value)
        c=analyze(d)
        self.assertEqual(c['results']['nominal'],['0','1/3','1/3','2/3'])
        self.assertEqual(c['results']['worst_transition']['step'],'0')
        self.assertTrue(verify(c)['nondecreasing'])
        d=make_design(3,'0','1')
        for r,value in zip(d['resistors'],['1','100','2','1','1','2']): r.update(nominal=value,min=value,max=value)
        c=analyze(d)
        self.assertEqual((c['results']['worst_transition']['from'],c['results']['worst_transition']['to']),(1,2))
        self.assertEqual(c['results']['worst_transition']['step'],'-12/101')
        self.assertEqual(verify(c)['status'],'verified')

    def test_fixed_intervals_have_no_redundant_corner_coordinates(self):
        d=make_design(3,'0','1')
        d['resistors'][2]['min']='1980'; d['resistors'][2]['max']='2020'
        d['resistors'][5]['min']='1980'; d['resistors'][5]['max']='2020'
        c=analyze(d)
        self.assertEqual(c['corner_count'],4)
        for s in c['results']['steps']: self.assertLess(s['min_corner'],4)
        self.assertEqual(verify(c)['corner_count'],4)

    def test_nonuniform_measured_intervals_verify_and_reference_scales_exactly(self):
        rng=random.Random(90210)
        d=make_design(5,'1/100','1')
        for r in d['resistors']:
            nominal=rng.randint(50,5000)
            r.update(nominal=str(nominal),min=str(nominal-3),max=str(nominal+11))
        c=analyze(d)
        self.assertEqual(verify(c)['status'],'verified')
        scaled=copy.deepcopy(d); scaled['vref']='3.3'
        result=analyze(scaled)
        for old,new in zip(c['results']['steps'],result['results']['steps']):
            self.assertEqual(F(new['min']),F(old['min'])*F(33,10))
            self.assertEqual(new['min_corner'],old['min_corner'])

    def test_verifier_rejects_type_spoofing_and_unbounded_shapes(self):
        c=analyze(make_design(2,'0','1'))
        bad=copy.deepcopy(c); bad['results']['codes'][0]['code']=False
        with self.assertRaises(VerificationError): verify(bad)
        bad=copy.deepcopy(c); bad['corner_count']=True
        with self.assertRaises(VerificationError): verify(bad)
        circular={}; circular['design']=circular
        with self.assertRaises(VerificationError): verify(circular)
        bad=copy.deepcopy(c); bad['results']['codes']=[{}]*257
        with self.assertRaises(VerificationError): verify(bad)
        bad=copy.deepcopy(c); bad['results']['nominal'][0]='9'*2001
        with self.assertRaises(VerificationError): verify(bad)

    def test_mid_analysis_cancel_cannot_return_a_partial_certificate(self):
        calls=[0]
        def cancel():
            calls[0]+=1
            return calls[0]>=5
        with self.assertRaises(Refused): analyze(make_design(4,'1/100','1'),budget=Budget(cancel=cancel))
        self.assertEqual(calls[0],5)

    def test_model_and_exact_precision_boundaries(self):
        valid=make_design(2,'0','0.000000001')
        valid['resistors'][0].update(nominal='0.000000001',min='0.000000001',max='0.000000001')
        self.assertEqual(parse_design(valid).vref,F(1,10**9))
        for number in ['0.0000000000001','18446744073709551616','1/0','1/18446744073709551616',True,1.5]:
            d=make_design(2,'0','1'); d['resistors'][0]['min']=number
            with self.subTest(number=number),self.assertRaises(Invalid): parse_design(d)
        for seconds in [float('nan'),float('inf'),0,-1,121,True]:
            with self.subTest(seconds=seconds),self.assertRaises(Invalid): Budget(seconds=seconds)

if __name__=='__main__': unittest.main()
