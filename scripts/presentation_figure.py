#!/usr/bin/env python3
"""Rebuild the README figure from the included exact five-percent witness.

Requires Matplotlib for presentation only. Uses the existing independent verifier's
Thevenin reduction for each code; does not change or resample the certificate.
"""
from pathlib import Path
from fractions import Fraction
import csv
import hashlib
import json
import sys
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ladderproof.verifier import _reduce, _code_values
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

source = ROOT / 'examples/six-bit-five-percent.certificate.json'
certificate = json.loads(source.read_text())
witness = certificate['results']['worst_transition']
assert certificate['design']['bits'] == 6 and Fraction(certificate['design']['vref']) == 1
assert witness['from'] == 31 and witness['to'] == 32 and Fraction(witness['step']) < 0
step_label = (f"{witness['from']} → {witness['to']}\n{float(Fraction(witness['step']) * 1000):.2f} mV").replace('-', '−')
values = _code_values(_reduce(6, [Fraction(r['value']) for r in witness['resistors']]), Fraction(certificate['design']['vref']))
assert values[31] == Fraction(witness['from_voltage'])
assert values[32] == Fraction(witness['to_voltage'])
assert values[32] - values[31] == Fraction(witness['step'])
output = ROOT / 'docs/presentation'
output.mkdir(parents=True, exist_ok=True)
with (output / 'five-percent-witness.csv').open('w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['digital_code', 'output_volts_exact', 'output_volts_decimal'])
    writer.writerows((i, str(value), format(float(value), '.12g')) for i, value in enumerate(values))

ink, muted, paper, accent, grid = '#172b36', '#48606d', '#fbfaf5', '#a52d30', '#dce2e3'
with plt.rc_context({'font.family': ['DejaVu Sans', 'Arial', 'sans-serif'], 'font.size': 14, 'text.color': ink,
                     'axes.labelcolor': ink, 'xtick.color': muted, 'ytick.color': muted,
                     'axes.edgecolor': muted, 'svg.fonttype': 'none', 'svg.hashsalt': 'LadderProof-witness-v1'}):
    for mobile in [False, True]:
        plt.rcParams['font.size'] = 16 if mobile else 14
        fig, axes = plt.subplots(2 if mobile else 1, 1 if mobile else 2,
                                 figsize=(5.5, 8.6) if mobile else (12, 5.7),
                                 layout='constrained', facecolor=paper)
        fig.get_layout_engine().set(w_pad=0.08, h_pad=0.10)
        fig.suptitle('One falling step\ndisproves monotonicity' if mobile else 'One falling step disproves monotonicity', fontsize=19 if mobile else 23, fontweight='bold')
        all_codes = list(range(64))
        for ax, codes, label in zip(axes, [all_codes, list(range(28, 36))], ['Whole transfer', 'Detail: codes 28–35']):
            ax.set_facecolor(paper)
            ax.plot(codes, [float(values[i]) for i in codes], color=ink, linewidth=1.8,
                    marker='o', markersize=3 if len(codes) > 8 else 5, zorder=2, gid='whole-transfer' if len(codes) > 8 else 'detail-transfer')
            ax.plot([31, 32], [float(values[31]), float(values[32])], color=accent,
                    linewidth=3, marker='s', markersize=7, zorder=3)
            ax.set(title=label, xlabel='Digital code', ylabel='Output (V)')
            ax.spines[['top', 'right']].set_visible(False)
            ax.grid(axis='y', color=grid, linewidth=.8)
        axes[0].set(xlim=(-1, 64), ylim=(0, 1), xticks=[0, 16, 31, 48, 63])
        axes[1].set(xlim=(27.6, 35.4), ylim=(.4, .6), xticks=[28, 31, 32, 35], yticks=[.4, .45, .5, .55, .6])
        axes[1].annotate(step_label, xy=(31.5, .493), xytext=(28.2, .565),
                         color=accent, fontsize=14, fontweight='bold',
                         arrowprops={'arrowstyle': '-', 'color': accent, 'connectionstyle': 'angle,angleA=0,angleB=90,rad=4'})
        fig.supxlabel('Ideal static 6-bit R-2R\nIndependent ±5% intervals · 1 V reference' if mobile else 'Ideal static 6-bit R-2R · independent ±5% intervals · 1 V reference', fontsize=12 if mobile else 13)
        stem = 'falling-step-mobile' if mobile else 'falling-step'
        fig.savefig(output / (stem + '.svg'), facecolor=paper, metadata={'Date': None, 'Title': 'LadderProof exact static worst-case witness'})
        svg_path = output / (stem + '.svg')
        svg_text = svg_path.read_text()
        svg_text = svg_text.replace('<svg ', '<svg role="img" aria-labelledby="' + stem + '-title ' + stem + '-desc" ', 1)
        root_start = svg_text.index('>', svg_text.index('<svg ')) + 1
        svg_text = svg_text[:root_start] + '<title id="' + stem + '-title">One falling step disproves monotonicity</title><desc id="' + stem + '-desc">The exact ideal six-bit five-percent witness has a 35.14 millivolt decrease from code 31 to 32; the detail panel uses an explicitly labeled local voltage scale.</desc>' + svg_text[root_start:]
        svg_path.write_text(svg_text)
        # Reopen the exported SVG and check all plotted line vertices against
        # the admitted arrays transformed through the actual Matplotlib axes.
        xml = ET.fromstring(svg_text)
        ns = {'s': 'http://www.w3.org/2000/svg'}
        for ax, codes, gid in zip(axes, [all_codes, list(range(28, 36))], ['whole-transfer', 'detail-transfer']):
            path = xml.find('.//s:g[@id="' + gid + '"]/s:path', ns)
            coordinates = [float(x) for x in re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', path.attrib['d'])]
            expected = ax.transData.transform([(i, float(values[i])) for i in codes])
            scale = 72 / fig.dpi
            expected = [(x * scale, (fig.bbox.height - y) * scale) for x, y in expected]
            assert len(coordinates) == len(expected) * 2
            assert all(abs(coordinates[2*i] - xy[0]) < .00001 and abs(coordinates[2*i+1] - xy[1]) < .00001 for i, xy in enumerate(expected)), gid
        fig.savefig(output / (stem + '.png'), facecolor=paper, dpi=160, metadata={'Software': 'Matplotlib ' + matplotlib.__version__})
        plt.close(fig)

manifest = {'source': str(source.relative_to(ROOT)), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'matplotlib': matplotlib.__version__, 'font_policy': ['DejaVu Sans', 'Arial', 'sans-serif'], 'quantity': 'static output voltage at integer input code',
            'units': 'volts; annotated step converted to millivolts by multiplying by 1000',
            'scope': 'one attaining resistor assignment, not per-code interval extrema or physical measurements',
            'transformations': ['Exact Thevenin reduction at each of 64 integer codes', 'Fraction to float only for plot positions', 'Detail panel displays codes 28 through 35 with labeled local voltage axis', 'No smoothing, sampling, fitted curve, confidence interval or stochastic data'],
            'worst_transition': witness,
            'outputs': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.suffix in ['.svg', '.png', '.csv']}}
(output / 'figure-provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')
