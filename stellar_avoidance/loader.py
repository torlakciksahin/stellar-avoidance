"""Catalog loading and derived column computation."""

import os
import numpy as np
import pandas as pd
from astropy.table import Table


def load_catalog(filepath, column_map=None, max_rows=None):
    """Load FITS, CSV, or parquet. column_map maps standard->your column names."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Catalog not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext in ('.fits', '.fit'):
        print(f"  Loading FITS: {filepath}")
        t = Table.read(filepath)
        df = t.to_pandas()
    elif ext == '.csv':
        print(f"  Loading CSV: {filepath}")
        df = pd.read_csv(filepath)
    elif ext in ('.parquet', '.pq'):
        df = pd.read_parquet(filepath)
    else:
        raise ValueError(f"Unsupported format: {ext}. Use .fits, .csv, or .parquet")

    print(f"  {len(df):,} stars, {len(df.columns)} columns")

    if max_rows is not None:
        df = df.head(max_rows)

    # reverse mapping: {standard: your_name} -> {your_name: standard}
    if column_map:
        reverse_map = {v: k for k, v in column_map.items()}
        existing = {v: k for k, v in reverse_map.items() if v in df.columns}
        if existing:
            df = df.rename(columns=existing)
            print(f"  Mapped columns: {existing}")

    # FITS memory-mapped arrays can cause read-only errors downstream
    for col in df.columns:
        if hasattr(df[col].values, 'copy'):
            df[col] = df[col].values.copy()

    return df


def compute_derived_columns(df, config=None):
    """Compute phot_g_mean_mag, distance_pc, abs_g, bp_rp, age_flame_spec_upper if missing."""
    df = df.copy()

    G_ZEROPOINT = 25.6883657251

    if 'phot_g_mean_mag' not in df.columns and 'phot_g_mean_flux' in df.columns:
        valid = df['phot_g_mean_flux'] > 0
        df.loc[valid, 'phot_g_mean_mag'] = (
            -2.5 * np.log10(df.loc[valid, 'phot_g_mean_flux']) + G_ZEROPOINT
        )
        print(f"  Computed phot_g_mean_mag ({valid.sum():,} stars)")

    if 'distance_pc' not in df.columns and 'parallax' in df.columns:
        valid = df['parallax'] > 0
        df.loc[valid, 'distance_pc'] = 1000.0 / df.loc[valid, 'parallax']
        print(f"  Computed distance_pc ({valid.sum():,} stars)")

    if 'abs_g' not in df.columns and 'parallax' in df.columns and 'phot_g_mean_mag' in df.columns:
        valid = df['parallax'] > 0
        df.loc[valid, 'abs_g'] = (
            df.loc[valid, 'phot_g_mean_mag']
            + 5 * np.log10(df.loc[valid, 'parallax'] / 100)
        )
        print(f"  Computed abs_g ({valid.sum():,} stars)")

    if 'bp_rp' not in df.columns and 'phot_bp_mean_mag' in df.columns and 'phot_rp_mean_mag' in df.columns:
        df['bp_rp'] = df['phot_bp_mean_mag'] - df['phot_rp_mean_mag']
        print(f"  Computed bp_rp")

    # Gaia DR3 inconsistency: some files use _upp, some _upper
    if 'age_flame_spec_upper' not in df.columns and 'age_flame_spec_upp' in df.columns:
        df['age_flame_spec_upper'] = df['age_flame_spec_upp']
        print(f"  Renamed age_flame_spec_upp -> age_flame_spec_upper")

    return df
