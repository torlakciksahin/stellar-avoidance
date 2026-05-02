"""YAML config loader and validator."""

import yaml
import os
from pathlib import Path

VALID_OPERATORS = {'gt', 'lt', 'ge', 'le', 'eq', 'ne', 'in', 'is_true', 'is_false', 'notna'}
REQUIRED_FIELDS = {'code', 'name', 'column', 'operator'}
SUB_REQUIRED_FIELDS = {'column', 'operator'}

DEFAULT_CONFIG = Path(__file__).parent.parent / 'configs' / 'torlakcik_default.yaml'


def load_config(config_path=None):
    """Load a YAML config. Falls back to the bundled default if path is None."""
    if config_path is None:
        config_path = str(DEFAULT_CONFIG)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    _validate_config(config)
    return config


def _validate_config(config):
    if 'criteria' not in config:
        raise ValueError("Config must contain a 'criteria' key")

    criteria = config['criteria']
    if not isinstance(criteria, list) or len(criteria) == 0:
        raise ValueError("'criteria' must be a non-empty list")

    for i, crit in enumerate(criteria):
        is_composite = (
            'sub_criteria' in crit
            and isinstance(crit['sub_criteria'], list)
            and len(crit['sub_criteria']) > 0
        )

        if is_composite:
            for j, sub in enumerate(crit['sub_criteria']):
                missing = SUB_REQUIRED_FIELDS - set(sub.keys())
                if missing:
                    raise ValueError(
                        f"Criterion {i} ({crit.get('code', '?')}), "
                        f"sub {j}: missing {missing}"
                    )
                if sub['operator'] not in VALID_OPERATORS:
                    raise ValueError(
                        f"{crit['code']} sub {j}: bad operator '{sub['operator']}'"
                    )
                if sub['operator'] == 'in' and not isinstance(sub.get('threshold'), list):
                    raise ValueError(f"{crit['code']} sub {j}: 'in' needs a list")
                if sub['operator'] in ('gt', 'lt', 'ge', 'le') and not isinstance(sub.get('threshold'), (int, float)):
                    raise ValueError(f"{crit['code']} sub {j}: needs numeric threshold")
            continue

        missing = REQUIRED_FIELDS - set(crit.keys())
        if missing:
            raise ValueError(f"Criterion {i} ({crit.get('code', '?')}): missing {missing}")

        if crit['operator'] not in VALID_OPERATORS:
            raise ValueError(f"{crit['code']}: bad operator '{crit['operator']}'")

        if crit['operator'] == 'in' and not isinstance(crit.get('threshold'), list):
            raise ValueError(f"{crit['code']}: 'in' needs a list")

        if crit['operator'] in ('gt', 'lt', 'ge', 'le') and not isinstance(crit.get('threshold'), (int, float)):
            raise ValueError(f"{crit['code']}: '{crit['operator']}' needs numeric threshold")


def get_active_criteria(config):
    return [c for c in config['criteria'] if c.get('active', True)]


def get_spectral_boundaries(config):
    return config.get('spectral_boundaries', {})


def print_config_summary(config):
    print()
    meta = config.get('metadata', {})
    if meta:
        print(f"  Config: {meta.get('name', '?')} v{meta.get('version', '?')}")
        print(f"  Author: {meta.get('author', '?')}")

    criteria = get_active_criteria(config)
    print(f"  Active criteria: {len(criteria)}")
    for crit in criteria:
        col = crit.get('column', '(composite)')
        op = crit.get('operator', 'OR')
        thresh = crit.get('threshold', '-')
        print(f"    {crit['code']}: {crit['name']}  [{col} {op} {thresh}]")
        if 'sub_criteria' in crit:
            for sub in crit['sub_criteria']:
                print(f"      or: {sub['column']} {sub['operator']} {sub.get('threshold', '-')}")
    print()
