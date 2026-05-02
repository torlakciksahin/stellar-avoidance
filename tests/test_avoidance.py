"""Tests for config, criteria, loader, and export."""

import numpy as np
import pandas as pd
import pytest
import os
import json

from stellar_avoidance.config import (
    load_config, get_active_criteria, get_spectral_boundaries,
    print_config_summary, _validate_config,
)
from stellar_avoidance.criteria import (
    classify_spectral_type, evaluate_criterion,
    evaluate_composite_criterion, apply_criteria,
)
from stellar_avoidance.loader import load_catalog, compute_derived_columns
from stellar_avoidance.export import save_results, write_provenance


SPECTRAL_BOUNDARIES = {
    'O': 30000, 'B': 10000, 'A': 7500,
    'F0-F4': 6600, 'F5-F9': 6000,
    'G': 5200, 'K': 3700,
}


# -- Config --

class TestConfig:
    def test_load_default(self):
        config = load_config()
        assert len(config['criteria']) == 7

    def test_load_explicit_path(self):
        from stellar_avoidance.config import DEFAULT_CONFIG
        config = load_config(str(DEFAULT_CONFIG))
        assert 'criteria' in config

    def test_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_config('/nonexistent.yaml')

    def test_validate_missing_criteria(self):
        with pytest.raises(ValueError, match="criteria"):
            _validate_config({'metadata': {}})

    def test_validate_empty_criteria(self):
        with pytest.raises(ValueError):
            _validate_config({'criteria': []})

    def test_validate_bad_operator(self):
        with pytest.raises(ValueError, match="bad operator"):
            _validate_config({'criteria': [
                {'code': 'X', 'name': 'T', 'column': 'c', 'operator': 'bad', 'threshold': 1}
            ]})

    def test_validate_in_needs_list(self):
        with pytest.raises(ValueError, match="'in' needs"):
            _validate_config({'criteria': [
                {'code': 'X', 'name': 'T', 'column': 'c', 'operator': 'in', 'threshold': 'string'}
            ]})

    def test_active_criteria(self, torlakcik_config):
        codes = [c['code'] for c in get_active_criteria(torlakcik_config)]
        assert codes == ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7']

    def test_spectral_boundaries(self, torlakcik_config):
        b = get_spectral_boundaries(torlakcik_config)
        assert b['O'] == 30000
        assert b['K'] == 3700

    def test_print_summary(self, torlakcik_config, capsys):
        print_config_summary(torlakcik_config)
        out = capsys.readouterr().out
        assert 'R1' in out and 'R7' in out


# -- Spectral type --

class TestSpectralType:
    def test_classification(self):
        teff = pd.Series([40000, 12000, 8000, 7000, 6300, 5500, 4500, 3000])
        result = classify_spectral_type(teff, SPECTRAL_BOUNDARIES)
        assert list(result) == ['O', 'B', 'A', 'F0-F4', 'F5-F9', 'G', 'K', 'M']

    def test_nan_teff(self):
        teff = pd.Series([np.nan, 5500])
        result = classify_spectral_type(teff, SPECTRAL_BOUNDARIES)
        assert result.iloc[0] == 'Unknown'
        assert result.iloc[1] == 'G'


# -- Criterion evaluation --

class TestCriterionEval:
    def _df(self, **kwargs):
        return pd.DataFrame(kwargs)

    def test_gt(self):
        mask = evaluate_criterion(
            self._df(mass=[1.0, 1.5, 2.0, np.nan]),
            {'code': 'R1', 'column': 'mass', 'operator': 'gt', 'threshold': 1.5}
        )
        assert list(mask) == [False, False, True, False]

    def test_lt(self):
        mask = evaluate_criterion(
            self._df(age=[1.0, 3.0, 5.0, np.nan]),
            {'code': 'R2', 'column': 'age', 'operator': 'lt', 'threshold': 3.0}
        )
        assert list(mask) == [True, False, False, False]

    def test_ge(self):
        mask = evaluate_criterion(
            self._df(nss=[0, 1, 2, np.nan]),
            {'code': 'R5', 'column': 'nss', 'operator': 'ge', 'threshold': 1}
        )
        assert list(mask) == [False, True, True, False]

    def test_in(self):
        mask = evaluate_criterion(
            self._df(sp=['O', 'G', 'M']),
            {'code': 'R3', 'column': 'sp', 'operator': 'in', 'threshold': ['O', 'B']}
        )
        assert list(mask) == [True, False, False]

    def test_is_true(self):
        mask = evaluate_criterion(
            self._df(flag=[True, False, np.nan]),
            {'code': 'T', 'column': 'flag', 'operator': 'is_true'}
        )
        assert list(mask) == [True, False, False]

    def test_missing_column(self):
        mask = evaluate_criterion(
            self._df(a=[1, 2]),
            {'code': 'T', 'column': 'nonexistent', 'operator': 'gt', 'threshold': 0}
        )
        assert mask.sum() == 0

    def test_composite_or(self):
        df = self._df(r=[0.005, 0.02], f=['NOT_AVAILABLE', 'VARIABLE'])
        crit = {
            'code': 'R6',
            'sub_criteria': [
                {'column': 'r', 'operator': 'gt', 'threshold': 0.01},
                {'column': 'f', 'operator': 'eq', 'threshold': 'VARIABLE'},
            ],
        }
        mask = evaluate_composite_criterion(df, crit)
        assert list(mask) == [False, True]


# -- Apply criteria --

class TestApplyCriteria:
    def test_adds_columns(self, synthetic_catalog, torlakcik_config):
        df = apply_criteria(synthetic_catalog, torlakcik_config)
        assert 'spectral_type' in df.columns
        assert 'decision' in df.columns
        assert 'reason_code' in df.columns

    def test_retained_empty_reason(self, synthetic_catalog, torlakcik_config):
        df = apply_criteria(synthetic_catalog, torlakcik_config)
        retained = df[df['decision'] == 'RETAIN']
        assert (retained['reason_code'] == '').all()

    def test_excluded_has_reason(self, synthetic_catalog, torlakcik_config):
        df = apply_criteria(synthetic_catalog, torlakcik_config)
        excluded = df[df['decision'] == 'EXCLUDE']
        assert (excluded['reason_code'] != '').all()

    def test_r1_flags_high_mass(self, torlakcik_config):
        df = pd.DataFrame({
            'mass_flame_spec': [0.5, 1.5, 2.0],
            'teff_gspphot': [5500, 5500, 5500],
        })
        result = apply_criteria(df, torlakcik_config)
        r1 = result[result['reason_code'].str.contains('R1', na=False)]
        assert len(r1) == 1  # only mass > 1.5

    def test_r7_m_dwarf_only(self, torlakcik_config):
        df = pd.DataFrame({
            'teff_gspphot': [3500, 5500],  # M, G
            'in_vari_rotation_modulation': [True, True],
        })
        result = apply_criteria(df, torlakcik_config)
        r7 = result[result['reason_code'].str.contains('R7', na=False)]
        assert len(r7) == 1  # only the M dwarf

    def test_solar_type_retained(self, torlakcik_config):
        df = pd.DataFrame({
            'mass_flame_spec': [1.0],
            'age_flame_spec_upper': [8.0],
            'teff_gspphot': [5800],
            'mh_gspphot': [0.0],
            'non_single_star': [0],
            'range_mag_g_fov': [0.001],
            'phot_variable_flag': ['NOT_AVAILABLE'],
        })
        result = apply_criteria(df, torlakcik_config)
        assert result.iloc[0]['decision'] == 'RETAIN'

    def test_multiple_criteria_stack(self, torlakcik_config):
        df = pd.DataFrame({
            'mass_flame_spec': [2.5],       # R1
            'age_flame_spec_upper': [1.5],   # R2
            'teff_gspphot': [20000],          # R3
            'mh_gspphot': [-0.8],             # R4
        })
        result = apply_criteria(df, torlakcik_config)
        reason = result.iloc[0]['reason_code']
        for code in ['R1', 'R2', 'R3', 'R4']:
            assert code in reason


# -- Loader --

class TestLoader:
    def test_csv_roundtrip(self, synthetic_catalog_csv):
        df = load_catalog(synthetic_catalog_csv)
        assert len(df) == 1000
        assert 'teff_gspphot' in df.columns

    def test_fits_load(self, synthetic_catalog_fits):
        df = load_catalog(synthetic_catalog_fits)
        assert len(df) == 1000

    def test_max_rows(self, synthetic_catalog_csv):
        df = load_catalog(synthetic_catalog_csv, max_rows=50)
        assert len(df) == 50

    def test_compute_mag(self):
        G_ZP = 25.6883657251
        flux = np.array([1e5, 5e5])
        df = pd.DataFrame({'phot_g_mean_flux': flux, 'parallax': [10.0, 10.0]})
        result = compute_derived_columns(df)
        expected = -2.5 * np.log10(flux) + G_ZP
        np.testing.assert_allclose(result['phot_g_mean_mag'].values, expected, rtol=1e-5)

    def test_compute_distance(self):
        df = pd.DataFrame({'parallax': [10.0, 5.0]})
        result = compute_derived_columns(df)
        np.testing.assert_allclose(result['distance_pc'].values, [100.0, 200.0])

    def test_negative_parallax_skipped(self):
        df = pd.DataFrame({'parallax': [-1.0, 0.0, 10.0]})
        result = compute_derived_columns(df)
        assert np.isnan(result['distance_pc'].iloc[0])
        assert result['distance_pc'].iloc[2] == 100.0

    def test_age_upper_rename(self):
        df = pd.DataFrame({'age_flame_spec_upp': [3.0, 5.0]})
        result = compute_derived_columns(df)
        assert 'age_flame_spec_upper' in result.columns


# -- Export --

class TestExport:
    def test_csv_output(self, output_dir):
        df = pd.DataFrame({
            'source_id': [1, 2],
            'decision': ['EXCLUDE', 'RETAIN'],
            'reason_code': ['R1', ''],
        })
        saved = save_results(df, output_dir, formats=['csv'])
        assert any('avoidance_catalog.csv' in f for f in saved)
        assert any('retained.csv' in f for f in saved)

    def test_fits_output(self, output_dir):
        df = pd.DataFrame({
            'source_id': [1, 2],
            'decision': ['EXCLUDE', 'RETAIN'],
            'reason_code': ['R1', ''],
        })
        saved = save_results(df, output_dir, formats=['fits'])
        assert any('.fits' in f for f in saved)

    def test_provenance(self, output_dir):
        prov = {'pipeline': 'stellar-avoidance', 'n_excluded': 100}
        write_provenance(prov, output_dir)
        path = os.path.join(output_dir, 'provenance.json')
        with open(path, encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded['n_excluded'] == 100
