"""End-to-end pipeline tests."""

import json
import os
import pandas as pd
import pytest

from stellar_avoidance.pipeline import run_pipeline, calculate_statistics
from stellar_avoidance.config import load_config


class TestPipeline:
    def test_csv_input(self, synthetic_catalog_csv, output_dir):
        results = run_pipeline(
            input_path=synthetic_catalog_csv,
            output_dir=output_dir,
            formats=['csv'],
            verbose=False,
        )
        assert len(results['catalog']) == 1000
        assert 'statistics' in results
        assert 'provenance' in results

    def test_fits_input(self, synthetic_catalog_fits, output_dir):
        results = run_pipeline(
            input_path=synthetic_catalog_fits,
            output_dir=output_dir,
            formats=['csv'],
            verbose=False,
        )
        assert len(results['catalog']) == 1000

    def test_max_rows(self, synthetic_catalog_csv, output_dir):
        results = run_pipeline(
            input_path=synthetic_catalog_csv,
            output_dir=output_dir,
            max_rows=50,
            formats=['csv'],
            verbose=False,
        )
        assert len(results['catalog']) == 50

    def test_decision_columns(self, synthetic_catalog_csv, output_dir):
        results = run_pipeline(
            input_path=synthetic_catalog_csv,
            output_dir=output_dir,
            formats=['csv'],
            verbose=False,
        )
        df = results['catalog']
        assert 'spectral_type' in df.columns
        assert 'decision' in df.columns
        assert 'reason_code' in df.columns

    def test_output_files(self, synthetic_catalog_csv, output_dir):
        run_pipeline(
            input_path=synthetic_catalog_csv,
            output_dir=output_dir,
            formats=['csv', 'fits'],
            verbose=False,
        )
        assert os.path.exists(os.path.join(output_dir, 'avoidance_catalog.csv'))
        assert os.path.exists(os.path.join(output_dir, 'avoidance_catalog_retained.csv'))
        assert os.path.exists(os.path.join(output_dir, 'avoidance_catalog.fits'))
        assert os.path.exists(os.path.join(output_dir, 'provenance.json'))

    def test_provenance_content(self, synthetic_catalog_csv, output_dir):
        run_pipeline(
            input_path=synthetic_catalog_csv,
            output_dir=output_dir,
            formats=['csv'],
            verbose=False,
        )
        with open(os.path.join(output_dir, 'provenance.json'), encoding='utf-8') as f:
            prov = json.load(f)
        assert prov['pipeline'] == 'stellar-avoidance'
        assert 'n_excluded' in prov
        assert 'start_time' in prov
        assert set(prov['criteria']) == {'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'}

    def test_excluded_plus_retained(self, synthetic_catalog_csv, output_dir):
        results = run_pipeline(
            input_path=synthetic_catalog_csv,
            output_dir=output_dir,
            formats=['csv'],
            verbose=False,
        )
        stats = results['statistics']
        assert stats['excluded_count'] + stats['retained_count'] == stats['total_stars']

    def test_all_r_codes_appear(self, synthetic_catalog_csv, output_dir):
        results = run_pipeline(
            input_path=synthetic_catalog_csv,
            output_dir=output_dir,
            formats=['csv'],
            verbose=False,
        )
        df = results['catalog']
        excluded = df[df['decision'] == 'EXCLUDE']
        all_reasons = set()
        for rc in excluded['reason_code'].dropna():
            for part in rc.split(';'):
                if part:
                    all_reasons.add(part)
        for code in ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7']:
            assert code in all_reasons, f"{code} didn't flag any star"


class TestStatistics:
    def test_basic_counts(self, torlakcik_config):
        df = pd.DataFrame({
            'decision': ['EXCLUDE', 'EXCLUDE', 'RETAIN', 'RETAIN', 'RETAIN'],
            'reason_code': ['R1', 'R2;R3', '', '', ''],
            'spectral_type': ['A', 'B', 'G', 'K', 'M'],
        })
        stats = calculate_statistics(df, torlakcik_config)
        assert stats['total_stars'] == 5
        assert stats['excluded_count'] == 2
        assert stats['retained_count'] == 3

    def test_per_criterion(self, torlakcik_config):
        df = pd.DataFrame({
            'decision': ['EXCLUDE', 'EXCLUDE', 'RETAIN'],
            'reason_code': ['R1', 'R2;R3', ''],
            'spectral_type': ['A', 'B', 'G'],
        })
        stats = calculate_statistics(df, torlakcik_config)
        assert stats['R1_count'] == 1
        assert stats['R2_count'] == 1
