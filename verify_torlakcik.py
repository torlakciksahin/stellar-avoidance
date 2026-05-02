#!/usr/bin/env python3
"""
Verify stellar-avoidance reproduces the Torlakcık Catalog results.

Expected (1,742,306 Gaia DR3 stars, R1-R7):
  Excluded: 964,471 (55.4%)
  Retained: 777,835 (44.6%)

Usage:
    python verify_torlakcik.py /path/to/gaia_dr3_catalog.fits
    python verify_torlakcik.py /path/to/gaia_dr3_catalog.fits --max-rows 10000
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stellar_avoidance.pipeline import run_pipeline
from stellar_avoidance.config import load_config, get_active_criteria

EXPECTED = {
    'total_stars': 1_742_306,
    'excluded_count': 964_471,
    'retained_count': 777_835,
    'excluded_fraction': 0.554,
    'retained_fraction': 0.446,
    'active_criteria': ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'],
}

FRACTION_TOL = 0.005
COUNT_TOL = 5000


def check(label, actual, expected, tol=0):
    diff = abs(actual - expected)
    if diff <= tol:
        print(f"  [PASS] {label}: {actual} (expected {expected}, diff={diff})")
        return True
    else:
        print(f"  [FAIL] {label}: {actual} (expected {expected}, diff={diff}, tol={tol})")
        return False


def main():
    parser = argparse.ArgumentParser(description='Verify against Torlakcık Catalog')
    parser.add_argument('input', help='Gaia DR3 catalog (FITS/CSV)')
    parser.add_argument('--max-rows', type=int, default=None, help='Quick mode: limit rows')
    parser.add_argument('-o', '--output-dir', default='./verify_output')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: {args.input} not found")
        sys.exit(1)

    quick = args.max_rows is not None
    print(f"\nVerifying ({'quick' if quick else 'full'} mode)...")

    print("\n[1/4] Config")
    config = load_config()
    active = get_active_criteria(config)
    codes = [c['code'] for c in active]
    ok = check("Active criteria", codes, EXPECTED['active_criteria'])

    print("\n[2/4] Running pipeline")
    results = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        max_rows=args.max_rows,
        formats=['csv', 'fits'],
        verbose=True,
    )

    print("\n[3/4] Results")
    prov = results['provenance']
    stats = results['statistics']
    all_ok = ok

    if quick:
        print("  (Skipping count checks in quick mode)")
        df = results['catalog']
        for col in ['decision', 'reason_code', 'spectral_type']:
            if col in df.columns:
                print(f"  [PASS] Column '{col}' exists")
            else:
                print(f"  [FAIL] Column '{col}' missing")
                all_ok = False

        excluded = df[df['decision'] == 'EXCLUDE']
        reasons = set()
        for rc in excluded['reason_code'].dropna():
            for part in rc.split(';'):
                if part:
                    reasons.add(part)
        if set(codes).issubset(reasons):
            print(f"  [PASS] All R1-R7 appear in reason codes")
        else:
            print(f"  [WARN] Missing: {set(codes) - reasons}")
    else:
        all_ok &= check("Total stars", prov['n_input_stars'], EXPECTED['total_stars'], COUNT_TOL)
        all_ok &= check("Excluded", prov['n_excluded'], EXPECTED['excluded_count'], COUNT_TOL)
        all_ok &= check("Retained", prov['n_retained'], EXPECTED['retained_count'], COUNT_TOL)
        all_ok &= check("Excl fraction", prov['excluded_fraction'], EXPECTED['excluded_fraction'], FRACTION_TOL)

        print("\n  Per-criterion:")
        for code in EXPECTED['active_criteria']:
            k = f'{code}_count'
            if k in stats:
                print(f"    {code}: {stats[k]:,} ({100*stats.get(f'{code}_fraction', 0):.1f}%)")

    print("\n[4/4] Output files")
    for fname in ['avoidance_catalog.csv', 'avoidance_catalog.fits',
                  'avoidance_catalog_retained.csv', 'avoidance_catalog_retained.fits',
                  'provenance.json']:
        fpath = os.path.join(args.output_dir, fname)
        if os.path.exists(fpath):
            kb = os.path.getsize(fpath) / 1024
            print(f"  [PASS] {fname} ({kb:.0f} KB)")
        else:
            print(f"  [FAIL] {fname} missing")
            all_ok = False

    if all_ok:
        print(f"\nVerification PASSED {'(quick mode -- run full for count checks)' if quick else ''}")
    else:
        print(f"\nVerification FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
