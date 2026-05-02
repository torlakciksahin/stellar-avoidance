# stellar-avoidance

SETI target avoidance for stellar catalogs. Define your exclusion criteria in a YAML
file, run the pipeline, and get back a classified catalog with reason codes and a
provenance record.

This is the community software companion to the
[Torlakcık Catalog](https://github.com/torlakciksahin/gaia-seti-avoidance).
The paper-specific repo (`gaia-seti-avoidance`) has the exact analysis, figures,
cross-matches, and sensitivity tests from the publication. This package
(`stellar-avoidance`) is the reusable, catalog-agnostic version -- same R1-R7 logic,
but configurable via YAML for any stellar survey.

## Install

```bash
git clone https://github.com/torlakciksahin/stellar-avoidance.git
cd stellar-avoidance
pip install -e .
```

Requires Python >= 3.9, numpy, pandas, astropy, pyyaml.

## Quick start

### CLI

```bash
# Default Torlakcık criteria (R1-R7) on a Gaia DR3 catalog
stellar-avoidance run gaia_dr3.fits

# Custom config
stellar-avoidance run my_catalog.fits -c my_criteria.yaml

# Non-Gaia column names
stellar-avoidance run catalog.fits --column-map teff_gspphot=TEMP mass_flame_spec=MASS

# Quick test run
stellar-avoidance run catalog.fits --max-rows 10000 --formats csv

# Show config details
stellar-avoidance info
```

### Python

```python
from stellar_avoidance.pipeline import run_pipeline

results = run_pipeline(
    input_path='gaia_dr3.fits',
    output_dir='./output',
)

df = results['catalog']
print(f"Excluded: {results['provenance']['n_excluded']:,}")
print(f"Retained: {results['provenance']['n_retained']:,}")
```

## Criteria

The bundled `configs/torlakcik_default.yaml` reproduces the R1-R7 criteria
from the paper:

| Code | Rule | Column | Op | Threshold |
|------|------|--------|----|-----------|
| R1 | High stellar mass | `mass_flame_spec` | gt | 1.5 Msun |
| R2 | Young age (upper bound) | `age_flame_spec_upper` | lt | 3.0 Gyr |
| R3 | Unfavorable spectral type | `spectral_type` | in | O, B, A, F0-F4 |
| R4 | Low metallicity | `mh_gspphot` | lt | -0.4 dex |
| R5 | Stellar multiplicity | `non_single_star` | ge | 1 |
| R6 | Photometric variability | composite (OR) | - | range > 0.01 or flag=VARIABLE |
| R7 | Active M dwarf | composite + M-only | - | rotation_modulation or short_timescale |

Stars flagged by multiple criteria get semicolon-separated codes (e.g. `R3;R4`).

## Custom criteria

Edit or create a YAML config:

```yaml
metadata:
  name: "My Survey"
  version: "1.0.0"

teff_column: "teff_gspphot"

spectral_boundaries:
  O: 30000
  B: 10000
  A: 7500
  F0-F4: 6600
  F5-F9: 6000
  G: 5200
  K: 3700

criteria:
  - code: R1
    name: "High stellar mass"
    column: "mass_flame_spec"
    operator: gt
    threshold: 1.5
    active: true

  - code: CUSTOM
    name: "My rule"
    column: "my_column"
    operator: ge
    threshold: 5.0
    active: true
```

Composite criteria (OR logic):

```yaml
- code: R6
  name: "Photometric variability"
  sub_criteria:
    - column: "range_mag_g_fov"
      operator: gt
      threshold: 0.01
    - column: "phot_variable_flag"
      operator: eq
      threshold: "VARIABLE"
  active: true
```

M-dwarf restricted criteria:

```yaml
- code: R7
  name: "Active M dwarf"
  sub_criteria:
    - column: "in_vari_rotation_modulation"
      operator: is_true
    - column: "in_vari_short_timescale"
      operator: is_true
  active: true
  m_dwarf_only: true
```

Supported operators: `gt`, `lt`, `ge`, `le`, `eq`, `ne`, `in`, `is_true`,
`is_false`, `notna`.

## Output

| File | Description |
|------|-------------|
| `avoidance_catalog.csv` | Full catalog with decision + reason_code |
| `avoidance_catalog.fits` | Same in FITS format |
| `avoidance_catalog_retained.csv` | Retained stars only |
| `avoidance_catalog_retained.fits` | Retained stars in FITS |
| `provenance.json` | Run metadata (timestamps, config, stats) |

## Verification

Check the software against the Torlakcık Catalog results:

```bash
python verify_torlakcik.py /path/to/gaia_dr3.fits
python verify_torlakcik.py /path/to/gaia_dr3.fits --max-rows 10000
```

Expected on the full Gaia DR3 sample (1,742,306 stars): 964,471 excluded (55.4%),
777,835 retained (44.6%).

For full paper reproduction (figures, Isaacson BL cross-match, sensitivity analysis)
use [gaia-seti-avoidance](https://github.com/torlakciksahin/gaia-seti-avoidance).

## Tests

```bash
pip install -e ".[test]"
pytest tests/ -v
```

Uses synthetic data, no Gaia DR3 file needed.

## Related

- [gaia-seti-avoidance](https://github.com/torlakciksahin/gaia-seti-avoidance) -- Paper-specific pipeline: Gaia DR3 cross-matching, Isaacson BL comparison, sensitivity analysis, and publication figures.

## License

MIT

## Citation

If you use this in your research:

> Torlakcık, Ş. (2026). "Where Not to Look: A Parametric Avoidance Model for SETI Target Selection." *PASP*.

```bibtex
@article{torlakcik2026,
  author  = {Torlakc{\i}k, {\c{S}}ahin},
  title   = {Where Not to Look: A Parametric Avoidance Model for SETI Target Selection},
  journal = {Publications of the Astronomical Society of the Pacific},
  year    = {2026}
}
```
