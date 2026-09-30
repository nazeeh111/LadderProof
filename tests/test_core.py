import copy
from fractions import Fraction
import unittest

try:
    from ladderproof import make_design, parse_design, analyze, verify, compare, Budget
    from ladderproof.errors import Invalid, Refused, VerificationError
except ImportError:
    make_design=parse_design=analyze=verify=compare=Budget=None
    Invalid=Refused=VerificationError=Exception

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(make_design, 'core API has not been implemented')

    def test_ideal_binary_weights_and_same_assignment_steps(self):
        c=analyze(make_design(2,'0','1'))
        self.assertEqual(c['corner_count'],1)
        self.assertEqual(c['results']['nominal'],['0','1/4','1/2','3/4'])
        self.assertEqual([s['min'] for s in c['results']['steps']],['1/4']*3)
        self.assertTrue(c['results']['nondecreasing'])
        self.assertEqual(verify(c)['status'],'verified')

    def test_nonuniform_two_bit_exact_analytic_fixture(self):
        # R branches: 2,4; series:3; termination:4.
        # Right Thevenin resistance is 2, so left weights are 5/7 and 1/7.
        d=make_design(2,'0','1')
        for r,v in zip(d['resistors'],['2','4','3','4']):
            r.update(nominal=v,min=v,max=v)
        c=analyze(d)
        self.assertEqual(c['results']['nominal'],['0','1/7','5/7','6/7'])
        self.assertEqual(c['results']['steps'][1]['min'],'4/7')
        self.assertEqual(verify(c)['status'],'verified')

    def test_six_bit_independent_bounds_success_and_decreasing_witness(self):
        c=analyze(make_design(6,'1/100','1'))
        self.assertEqual(c['corner_count'],4096)
        self.assertEqual(c['results']['worst_transition']['step'],'186147971/34016602567')
        self.assertTrue(c['results']['nondecreasing'])
        f=analyze(make_design(6,'1/20','1'))
        w=f['results']['worst_transition']
        self.assertEqual((w['from'],w['to']),(31,32))
        self.assertEqual(w['step'],'-269227/7660721')
        self.assertEqual(Fraction(w['to_voltage'])-Fraction(w['from_voltage']),Fraction(w['step']))
        self.assertFalse(f['results']['nondecreasing'])
        self.assertEqual(verify(f)['status'],'verified')
        self.assertTrue(compare(f,c)['after']['nondecreasing'])

    def test_rejects_unknown_correlations_and_bad_numeric_data(self):
        for change in [lambda d:d.update(correlations=[]),lambda d:d.update(bits=7),lambda d:d.update(bits=True),
                       lambda d:d.update(vref='nan'),lambda d:d.update(vref='1e99'),lambda d:d.update(vref='0'),
                       lambda d:d['resistors'][0].update(min='0'),lambda d:d['resistors'][0].update(min='99999'),
                       lambda d:d['resistors'][0].update(id='S0'),lambda d:d['resistors'][0].update(min='1/'+('9'*300)),
                       lambda d:d['resistors'].append(copy.deepcopy(d['resistors'][0]))]:
            with self.subTest(change=change):
                d=make_design(2,'1/100','1'); change(d)
                with self.assertRaises(Invalid): parse_design(d)

    def test_verifier_does_not_trust_witness_or_summary(self):
        c=analyze(make_design(3,'1/100','1'))
        changes=[lambda x:x.update(corner_count=1),lambda x:x.update(status='partial'),
                 lambda x:x['results']['steps'][0].update(min='0'),
                 lambda x:x['results']['worst_transition'].update(step='0'),
                 lambda x:x['results']['codes'].pop(),
                 lambda x:x['results']['steps'].append(copy.deepcopy(x['results']['steps'][0])),
                 lambda x:x['design']['resistors'][0].update(max='2100'),
                 lambda x:x['results'].update(nondecreasing=False)]
        for change in changes:
            with self.subTest(change=change):
                altered=copy.deepcopy(c); change(altered)
                with self.assertRaises(VerificationError): verify(altered)

    def test_cancelled_or_expired_analysis_and_verification_refuse(self):
        d=make_design(2,'1/100','1')
        with self.assertRaises(Refused): analyze(d,budget=Budget(cancel=lambda:True))
        with self.assertRaises(Refused): analyze(d,budget=Budget(seconds=0.000000001))
        c=analyze(d)
        with self.assertRaises(Refused): verify(c,budget=Budget(cancel=lambda:True))

if __name__=='__main__': unittest.main()
