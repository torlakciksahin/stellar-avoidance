"""Pipeline: load -> derive -> criteria -> stats -> export."""

import os
import datetime

import pandas as pd

from .config import load_config, get_active_criteria, print_config_summary
from .loader import load_catalog, compute_derived_columns
from .criteria import apply_criteria
from .export import save_results, write_provenance


def run_pipeline(input_path, config_path=None, output_dir='./output',
                 column_map=None, max_rows=None, formats=None, verbose=True):
    """Run the full avoidance pipeline end-to-end."""
    start_time = datetime.datetime.now(datetime.timezone.utc)
    if formats is None:
        formats = ['csv', 'fits']

    if verbose:
        print("\n[1/6] Loading config...")
    config = load_config(config_path)
    if verbose:
        print_config_summary(config)

    if verbose:
        print("[2/6] Loading catalog...")
    df = load_catalog(input_path, column_map=column_map, max_rows=max_rows)

    if verbose:
        print("[3/6] Computing derived columns...")
    df = compute_derived_columns(df, config)

    if verbose:
        print("[4/6] Applying avoidance criteria...")
    df = apply_criteria(df, config)

    if verbose:
        print("[5/6] Calculating statistics...")
    stats = calculate_statistics(df, config)
    if verbose:
        _print_statistics(stats)

    if verbose:
        print("[6/6] Saving results...")
    os.makedirs(output_dir, exist_ok=True)
    saved_files = save_results(df, output_dir, formats=formats)

    end_time = datetime.datetime.now(datetime.timezone.utc)
    provenance = {
        'pipeline': 'stellar-avoidance',
        'version': '1.0.0',
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'duration_seconds': (end_time - start_time).total_seconds(),
        'input_path': os.path.abspath(input_path),
        'config_path': os.path.abspath(config_path) if config_path else 'bundled_default',
        'output_dir': os.path.abspath(output_dir),
        'output_files': [os.path.abspath(f) for f in saved_files],
        'n_input_stars': len(df),
        'n_excluded': int(stats['excluded_count']),
        'n_retained': int(stats['retained_count']),
        'excluded_fraction': float(stats['excluded_fraction']),
        'retained_fraction': float(stats['retained_fraction']),
        'criteria': [c['code'] for c in get_active_criteria(config)],
    }
    write_provenance(provenance, output_dir)

    if verbose:
        print(f"\n  Done in {provenance['duration_seconds']:.1f}s")
        print(f"  Output: {output_dir}")

    return {
        'catalog': df,
        'statistics': stats,
        'provenance': provenance,
        'config': config,
    }


def calculate_statistics(df, config):
    """Overall and per-criterion exclusion stats, plus spectral type breakdown."""
    total = len(df)
    excluded = df[df['decision'] == 'EXCLUDE']
    retained = df[df['decision'] == 'RETAIN']

    stats = {
        'total_stars': total,
        'excluded_count': len(excluded),
        'retained_count': len(retained),
        'excluded_fraction': len(excluded) / total if total > 0 else 0,
        'retained_fraction': len(retained) / total if total > 0 else 0,
    }

    criteria = get_active_criteria(config)
    for crit in criteria:
        code = crit['code']
        count = excluded[excluded['reason_code'].str.contains(code, na=False)].shape[0]
        stats[f'{code}_count'] = count
        stats[f'{code}_fraction'] = count / total if total > 0 else 0
        stats[f'{code}_name'] = crit['name']

    if 'spectral_type' in df.columns:
        sp_stats = {}
        for sp_type in df['spectral_type'].unique():
            sp_total = len(df[df['spectral_type'] == sp_type])
            sp_excl = len(df[(df['spectral_type'] == sp_type) & (df['decision'] == 'EXCLUDE')])
            sp_stats[sp_type] = {
                'total': sp_total,
                'excluded': sp_excl,
                'retained': sp_total - sp_excl,
                'exclusion_rate': sp_excl / sp_total if sp_total > 0 else 0,
            }
        stats['spectral_type_breakdown'] = sp_stats

    return stats


def _print_statistics(stats):
    print(f"\n  Exclusion statistics:")
    print(f"    Total:   {stats['total_stars']:,}")
    print(f"    Excluded: {stats['excluded_count']:,} ({100*stats['excluded_fraction']:.1f}%)")
    print(f"    Retained: {stats['retained_count']:,} ({100*stats['retained_fraction']:.1f}%)")

    for key in sorted(stats.keys()):
        if key.endswith('_count') and not key.startswith('spectral'):
            code = key.replace('_count', '')
            count = stats[key]
            frac = stats.get(f'{code}_fraction', 0)
            name = stats.get(f'{code}_name', code)
            print(f"    {code}: {count:,} ({100*frac:.1f}%) - {name}")

    if 'spectral_type_breakdown' in stats:
        print(f"    By spectral type:")
        for sp in ['O', 'B', 'A', 'F0-F4', 'F5-F9', 'G', 'K', 'M', 'Unknown']:
            if sp in stats['spectral_type_breakdown']:
                info = stats['spectral_type_breakdown'][sp]
                print(f"      {sp}: {100*info['exclusion_rate']:.1f}% excluded (N={info['total']:,})")
