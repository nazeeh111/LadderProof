"""Independent analytic circuit/catalog oracle, not a second search wrapper."""
import copy
from fractions import Fraction as F
from itertools import product
import random
import unittest
from ladderproof import Budget, analyze, chosen_certificate, make_design, search, parse_catalog
from ladderproof.errors import Invalid


def request(tolerance='1/10', threshold='1/5'):
    design=make_design(2,tolerance,'1')
    return {'format':'ladderproof.catalog.v1','design':design,
            'minimum_step_volts':threshold,
            'catalog':[{'id':r['id'],'options':[{'tolerance':tolerance,'cost':'0'},{'tolerance':'0','cost':'1'}]} for r in design['resistors']]}


def exact_two_bit_minimum(nominals,tolerances,vref):
    # Direct Kirchhoff two-equation polynomial solution (Cramer's rule).
    # No solver, Thevenin reduction, certificate aggregation or search call.
    smallest=None
    for signs in product((-1,1),repeat=4):
        b0,b1,s,t=[nominal*(1+sign*tol) for nominal,sign,tol in zip(nominals,signs,tolerances)]
        determinant=(b0+s)*(b1+t)+b1*t
        high=(s*(b1+t)+b1*t)/determinant
        low=b0*t/determinant
        step=min(low,high-low)*vref
        smallest=step if smallest is None else min(smallest,step)
    return smallest


def oracle(data):
    nominal=[F(r['nominal']) for r in data['design']['resistors']]
    reference=F(data['design']['vref'])
    threshold=F(data['minimum_step_volts']) if 'minimum_step_volts' in data else (F(data['minimum_dnl_lsb'])+1)*reference/4
    feasible=[]
    for indices in product(*(range(len(r['options'])) for r in data['catalog'])):
        options=[r['options'][i] for r,i in zip(data['catalog'],indices)]
        minimum=exact_two_bit_minimum(nominal,[F(o['tolerance']) for o in options],reference)
        if minimum>=threshold:
            feasible.append((sum((F(o['cost']) for o in options),F(0)),indices,minimum))
    return min(feasible,key=lambda row:row[:2]) if feasible else None


class CatalogTests(unittest.TestCase):
    def test_independent_exhaustive_tiny_catalogs(self):
        rng=random.Random(60216)
        for trial in range(36):
            data=request(threshold=rng.choice(['-1/5','0','1/10','1/5','1/4','1/3']))
            for resistor in data['design']['resistors']:
                value=str(rng.randint(10,50));resistor.update(nominal=value,min=value,max=value)
            for resistor in data['catalog']:
                resistor['options']=[{'tolerance':tol,'cost':str(rng.randrange(5))} for tol in ['1/10','1/50','0'][:rng.randint(2,3)]]
            if trial%2:
                data['minimum_dnl_lsb']=str(4*F(data.pop('minimum_step_volts'))-1)
            expected=oracle(data)
            result=search(data,max_designs=256)
            with self.subTest(trial=trial):
                if expected is None:
                    self.assertEqual(result['status'],'infeasible')
                    self.assertIsNone(result['selection'])
                    self.assertFalse(result['optimal'])
                else:
                    self.assertEqual(result['status'],'optimal')
                    self.assertEqual((F(result['selection']['cost']),tuple(result['selection']['indices'])),expected[:2])
                    self.assertEqual(F(result['selection']['certificate']['results']['worst_transition']['step']),expected[2])
                    self.assertEqual(chosen_certificate(result),result['selection']['certificate'])

    def test_mixed_cost_improves_uniform_baseline(self):
        data=request()
        result=search(data)
        expected=oracle(data)
        self.assertEqual(F(result['selection']['cost']),expected[0])
        self.assertLess(expected[0],4)  # Uniform zero tolerance costs four units.
        self.assertLess(F(analyze(data['design'])['results']['worst_transition']['step']),F('1/5'))
        self.assertGreaterEqual(F(result['selection']['certificate']['results']['worst_transition']['step']),F('1/5'))
        for resistor in data['catalog']:resistor['options'][1]['tolerance']='1/100'
        result=search(data)
        self.assertEqual((result['selection']['cost'],result['selection']['indices']),('2',[0,1,1,0]))
        self.assertEqual(F(result['selection']['certificate']['results']['worst_transition']['step']),F(151,731))
        self.assertEqual(F(result['selection']['cost']),oracle(data)[0])

    def test_exact_units_zero_boundary_and_ties(self):
        data=request(tolerance='0',threshold='1/4')
        result=search(data)
        self.assertEqual(result['selection']['indices'],[0]*4)
        normalized=copy.deepcopy(data);normalized.pop('minimum_step_volts');normalized['minimum_dnl_lsb']='0'
        self.assertEqual(search(normalized)['selection'],result['selection'])
        scaled=copy.deepcopy(data);scaled['design']['vref']='33/10';scaled['minimum_step_volts']='33/40'
        self.assertEqual(search(scaled)['selection']['indices'],[0]*4)
        impossible=copy.deepcopy(data);impossible['minimum_step_volts']='250000000001/1000000000000'
        self.assertEqual(search(impossible)['status'],'infeasible')
        zero=request(tolerance='0',threshold='0')
        for r,value in zip(zero['design']['resistors'],['3','1','1','1']):r.update(nominal=value,min=value,max=value)
        self.assertEqual(search(zero)['selection']['certificate']['results']['worst_transition']['step'],'0')

    def test_work_deadline_and_cancel_never_claim_infeasibility(self):
        for options in [{'max_designs':1},{'max_corner_solves':1},{'budget':Budget(cancel=lambda:True)},{'budget':Budget(seconds=1e-9)}]:
            result=search(request(),**options)
            self.assertEqual(result['status'],'unfinished')
            self.assertFalse(result['optimal'])
            self.assertIsNone(result['selection'])
        calls=[0]
        def cancel():calls[0]+=1;return calls[0]>7
        result=search(request(),budget=Budget(cancel=cancel))
        self.assertEqual(result['status'],'unfinished')
        self.assertEqual(result['work']['attempted_designs'],1)
        self.assertEqual(result['work']['verified_designs'],0)

    def test_catalog_refusals_and_selection_binding(self):
        changes=[lambda d:d.update(minimum_dnl_lsb='0'),lambda d:d['catalog'].pop(),
                 lambda d:d['catalog'][0].update(id='T'),lambda d:d['catalog'][0]['options'][0].update(cost=True),
                 lambda d:d['catalog'][0]['options'][0].update(tolerance='1'),
                 lambda d:d['catalog'][0]['options'][0].update(cost='-1'),lambda d:d.update(extra=True)]
        for change in changes:
            data=request();change(data)
            with self.assertRaises(Invalid):parse_catalog(data)
        for kwargs in [{'max_designs':True},{'max_corner_solves':0},{'max_designs':4097}]:
            with self.assertRaises(Invalid):search(request(),**kwargs)
        data=request();result=search(data)
        for change in [lambda r:r['selection'].update(cost='100'),lambda r:r['selection']['indices'].__setitem__(0,True),
                       lambda r:r['request'].update(minimum_step_volts='1'),
                       lambda r:r['selection']['certificate']['design'].update(title='changed')]:
            altered=copy.deepcopy(result);change(altered)
            with self.assertRaises((Invalid,ValueError)):chosen_certificate(altered)
        chosen=chosen_certificate(result);chosen['design']['title']='detached'
        self.assertNotEqual(chosen['design'],result['selection']['certificate']['design'])
        too_many=request();too_many['design']=make_design(6,'0','1')
        too_many['catalog']=[{'id':r['id'],'options':[{'tolerance':'0','cost':'1'}]*4} for r in too_many['design']['resistors']]
        with self.assertRaises(Invalid):parse_catalog(too_many)

class CatalogCLITests(unittest.TestCase):
    def test_export_choose_reopen_compare_and_refusal_preservation(self):
        import json
        import tempfile
        from pathlib import Path
        from test_cli import run
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);data=request();source=root/'catalog.json';source.write_text(json.dumps(data))
            report=root/'selection.json';certificate=root/'chosen.json';baseline=root/'baseline.json';design=root/'design.json'
            self.assertEqual(run('catalog',source,'--output',report).returncode,0)
            self.assertEqual(run('choose',report,'--output',certificate).returncode,0)
            self.assertEqual(run('verify',certificate).returncode,0)
            design.write_text(json.dumps(data['design']))
            self.assertEqual(run('analyze',design,'--output',baseline).returncode,0)
            comparison=run('compare',baseline,certificate)
            self.assertEqual(comparison.returncode,0,comparison.stderr)
            self.assertGreater(F(json.loads(comparison.stdout)['minimum_step_change_volts']),0)
            saved=report.read_bytes()
            refusal=run('catalog',source,'--max-designs','1','--output',report,'--force')
            self.assertEqual(refusal.returncode,3,refusal.stderr)
            self.assertEqual(report.read_bytes(),saved)
            fresh=root/'unfinished.json'
            refusal=run('catalog',source,'--max-corner-solves','1','--output',fresh)
            self.assertEqual(refusal.returncode,3)
            self.assertEqual(json.loads(fresh.read_text())['status'],'unfinished')
            self.assertEqual(run('choose',fresh).returncode,2)
