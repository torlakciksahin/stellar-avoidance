"""Export results to CSV/FITS and write provenance JSON."""

import os
import json

import pandas as pd
from astropy.table import Table


def save_results(df, output_dir, formats=None, basename='avoidance_catalog'):
    """Save full catalog + retained-only subset."""
    if formats is None:
        formats = ['csv', 'fits']

    saved = []
    retained = df[df['decision'] == 'RETAIN']

    for subset, suffix in [(df, ''), (retained, '_retained')]:
        if 'csv' in formats:
            path = os.path.join(output_dir, f'{basename}{suffix}.csv')
            subset.to_csv(path, index=False)
            print(f"  Saved: {path}")
            saved.append(path)

        if 'fits' in formats:
            path = os.path.join(output_dir, f'{basename}{suffix}.fits')
            _save_fits(subset, path)
            print(f"  Saved: {path}")
            saved.append(path)

    return saved


def _save_fits(df, path):
    df_copy = df.copy()
    for col in df_copy.columns:
        if df_copy[col].dtype == 'object':
            df_copy[col] = df_copy[col].astype(str)
        if df_copy[col].dtype == 'bool':
            df_copy[col] = df_copy[col].astype('int8')
    t = Table.from_pandas(df_copy)
    t.write(path, overwrite=True)


def write_provenance(provenance, output_dir):
    path = os.path.join(output_dir, 'provenance.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(provenance, f, indent=2, default=str)
    print(f"  Saved: {path}")
