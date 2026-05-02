"""Criterion evaluation. Vectorized pandas/numpy, handles composite OR and m_dwarf_only."""

import numpy as np
import pandas as pd

from .config import get_active_criteria, get_spectral_boundaries


def classify_spectral_type(teff_series, boundaries):
    """Map Teff values to spectral type strings. NaN -> 'Unknown'."""
    result = pd.Series('Unknown', index=teff_series.index, dtype='object')
    valid = teff_series.notna()
    t = teff_series[valid]

    # sort high-to-low for np.select
    ordered = sorted(
        [(k, v) for k, v in boundaries.items() if k != 'M'],
        key=lambda x: x[1],
        reverse=True
    )

    conditions = []
    choices = []
    for name, temp in ordered:
        conditions.append(t >= temp)
        choices.append(name)

    if conditions:
        result[valid] = np.select(conditions, choices, default='M')
    else:
        result[valid] = 'M'

    return result


def evaluate_criterion(df, criterion):
    """Return a boolean mask where True means the star fails this criterion."""
    col = criterion['column']
    op = criterion['operator']
    threshold = criterion.get('threshold')

    if col not in df.columns:
        return pd.Series(False, index=df.index)

    series = df[col]

    if op == 'gt':
        return series.notna() & (series > threshold)
    elif op == 'lt':
        return series.notna() & (series < threshold)
    elif op == 'ge':
        return series.notna() & (series >= threshold)
    elif op == 'le':
        return series.notna() & (series <= threshold)
    elif op == 'eq':
        return series == threshold
    elif op == 'ne':
        return series != threshold
    elif op == 'in':
        return series.isin(threshold)
    elif op == 'is_true':
        return series.where(series.notna(), False).astype(bool)
    elif op == 'is_false':
        return ~(series.where(series.notna(), True).astype(bool))
    elif op == 'notna':
        return series.notna()
    else:
        raise ValueError(f"Unknown operator: {op}")


def evaluate_composite_criterion(df, criterion):
    """OR of sub-conditions."""
    sub_criteria = criterion.get('sub_criteria', [])
    if not sub_criteria:
        return pd.Series(False, index=df.index)

    combined = pd.Series(False, index=df.index)
    for sub in sub_criteria:
        combined = combined | evaluate_criterion(df, sub)
    return combined


def apply_criteria(df, config, spectral_type_col=None):
    """Run all active criteria on df. Adds spectral_type, decision, reason_code columns."""
    df = df.copy()
    criteria = get_active_criteria(config)

    # spectral classification
    boundaries = get_spectral_boundaries(config)
    if boundaries:
        teff_col = config.get('teff_column', 'teff_gspphot')
        if teff_col in df.columns and spectral_type_col is None:
            print("  Classifying spectral types...")
            df['spectral_type'] = classify_spectral_type(df[teff_col], boundaries)
        elif spectral_type_col and spectral_type_col in df.columns:
            df['spectral_type'] = df[spectral_type_col]

    print(f"  Applying {len(criteria)} criteria...")
    reason_masks = {}

    for crit in criteria:
        code = crit['code']

        if 'sub_criteria' in crit:
            mask = evaluate_composite_criterion(df, crit)
        else:
            mask = evaluate_criterion(df, crit)

        # restrict to M dwarfs if flagged
        if crit.get('m_dwarf_only', False) and 'spectral_type' in df.columns:
            mask = mask & (df['spectral_type'] == 'M')

        reason_masks[code] = mask
        n = mask.sum()
        print(f"    {code} ({crit['name']}): {n:,} flagged")

    # build semicolon-separated reason codes
    reason_code_parts = []
    for crit in criteria:
        code = crit['code']
        mask = reason_masks.get(code, pd.Series(False, index=df.index))
        part = np.where(mask, code, '')
        reason_code_parts.append(part)

    stacked = np.stack(reason_code_parts, axis=0)
    reason_codes = []
    for i in range(len(df)):
        codes = [stacked[j, i] for j in range(len(criteria)) if stacked[j, i] != '']
        reason_codes.append(';'.join(codes))

    df['reason_code'] = reason_codes
    df['decision'] = np.where(df['reason_code'] == '', 'RETAIN', 'EXCLUDE')

    excluded = (df['decision'] == 'EXCLUDE').sum()
    retained = (df['decision'] == 'RETAIN').sum()
    total = len(df)
    print(f"  Result: {excluded:,} excluded ({100*excluded/total:.1f}%), "
          f"{retained:,} retained ({100*retained/total:.1f}%)")

    return df
