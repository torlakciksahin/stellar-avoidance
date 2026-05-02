"""Test fixtures: synthetic Gaia DR3-like catalogs."""

import numpy as np
import pandas as pd
import pytest
import os

from stellar_avoidance.config import load_config


SPECTRAL_BOUNDARIES = {
    'O': 30000, 'B': 10000, 'A': 7500,
    'F0-F4': 6600, 'F5-F9': 6000,
    'G': 5200, 'K': 3700,
}


@pytest.fixture
def torlakcik_config():
    return load_config()


@pytest.fixture
def synthetic_catalog():
    np.random.seed(42)
    n = 1000

    teff = np.concatenate([
        np.random.uniform(30000, 45000, 10),   # O
        np.random.uniform(10000, 30000, 30),   # B
        np.random.uniform(7500, 10000, 40),    # A
        np.random.uniform(6600, 7500, 30),     # F0-F4
        np.random.uniform(6000, 6600, 60),     # F5-F9
        np.random.uniform(5200, 6000, 150),    # G
        np.random.uniform(3700, 5200, 200),    # K
        np.random.uniform(2400, 3700, 480),    # M
    ])
    np.random.shuffle(teff)

    mass = np.where(
        np.random.random(n) < 0.15,
        np.random.uniform(1.5, 5.0, n),
        np.random.uniform(0.1, 1.49, n),
    )

    age_med = np.random.uniform(0.5, 12.0, n)
    age_upper = np.clip(age_med + np.random.uniform(0.5, 2.0, n), age_med, 13.0)
    age_lower = np.clip(age_med - np.random.uniform(0.5, 2.0, n), 0.01, age_med)

    mh = np.where(
        np.random.random(n) < 0.12,
        np.random.uniform(-1.5, -0.41, n),
        np.random.uniform(-0.39, 0.5, n),
    )

    parallax = np.random.uniform(0.5, 50.0, n)
    phot_g_mean_flux = np.random.uniform(100, 1e6, n)
    G_ZP = 25.6883657251
    phot_g_mean_mag = -2.5 * np.log10(phot_g_mean_flux) + G_ZP
    phot_bp_mean_mag = phot_g_mean_mag + np.random.uniform(-0.5, 1.0, n)
    phot_rp_mean_mag = phot_g_mean_mag - np.random.uniform(0.0, 1.5, n)

    non_single_star = np.where(
        np.random.random(n) < 0.08,
        np.random.randint(1, 4, n),
        0,
    )

    range_mag_g_fov = np.where(
        np.random.random(n) < 0.10,
        np.random.uniform(0.02, 0.5, n),
        np.random.uniform(0.0, 0.009, n),
    )
    phot_variable_flag = np.where(
        np.random.random(n) < 0.05, 'VARIABLE', 'NOT_AVAILABLE'
    )

    in_vari_rotation_modulation = np.random.random(n) < 0.03
    in_vari_short_timescale = np.random.random(n) < 0.02

    return pd.DataFrame({
        'source_id': np.arange(n),
        'teff_gspphot': teff,
        'mass_flame_spec': mass,
        'age_flame_spec': age_med,
        'age_flame_spec_lower': age_lower,
        'age_flame_spec_upper': age_upper,
        'mh_gspphot': mh,
        'parallax': parallax,
        'phot_g_mean_flux': phot_g_mean_flux,
        'phot_g_mean_mag': phot_g_mean_mag,
        'phot_bp_mean_mag': phot_bp_mean_mag,
        'phot_rp_mean_mag': phot_rp_mean_mag,
        'bp_rp': phot_bp_mean_mag - phot_rp_mean_mag,
        'non_single_star': non_single_star,
        'range_mag_g_fov': range_mag_g_fov,
        'phot_variable_flag': phot_variable_flag,
        'in_vari_rotation_modulation': in_vari_rotation_modulation,
        'in_vari_short_timescale': in_vari_short_timescale,
    })


@pytest.fixture
def synthetic_catalog_csv(synthetic_catalog, tmp_path):
    path = str(tmp_path / 'test_catalog.csv')
    synthetic_catalog.to_csv(path, index=False)
    return path


@pytest.fixture
def synthetic_catalog_fits(synthetic_catalog, tmp_path):
    from astropy.table import Table
    path = str(tmp_path / 'test_catalog.fits')
    df_copy = synthetic_catalog.copy()
    for col in df_copy.columns:
        if df_copy[col].dtype == 'object':
            df_copy[col] = df_copy[col].astype(str)
        if df_copy[col].dtype == 'bool':
            df_copy[col] = df_copy[col].astype(int)
    Table.from_pandas(df_copy).write(path, overwrite=True)
    return path


@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / 'output'
    d.mkdir()
    return str(d)
