"""CLI for stellar-avoidance."""

import argparse
import sys

from .pipeline import run_pipeline
from .config import load_config, print_config_summary


def main():
    parser = argparse.ArgumentParser(
        prog='stellar-avoidance',
        description='SETI target avoidance for stellar catalogs',
    )

    sub = parser.add_subparsers(dest='command')

    run_p = sub.add_parser('run', help='Run the avoidance pipeline')
    run_p.add_argument('input', metavar='INPUT', help='Catalog file (FITS/CSV/parquet)')
    run_p.add_argument('-c', '--config', default=None, help='YAML config (default: bundled Torlakcık criteria)')
    run_p.add_argument('-o', '--output-dir', default='./output', help='Output directory')
    run_p.add_argument('--max-rows', type=int, default=None, help='Limit rows loaded')
    run_p.add_argument('--formats', nargs='+', default=['csv', 'fits'], choices=['csv', 'fits'])
    run_p.add_argument('--column-map', nargs='+', default=None, help='key=value pairs')

    info_p = sub.add_parser('info', help='Show config details')
    info_p.add_argument('config_path', nargs='?', default=None, help='YAML config path')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == 'info':
        config = load_config(args.config_path)
        print_config_summary(config)
        return

    if args.command == 'run':
        column_map = None
        if args.column_map:
            column_map = {}
            for pair in args.column_map:
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    column_map[k] = v

        results = run_pipeline(
            input_path=args.input,
            config_path=args.config,
            output_dir=args.output_dir,
            column_map=column_map,
            max_rows=args.max_rows,
            formats=args.formats,
            verbose=True,
        )

        prov = results['provenance']
        print(f"\n  {prov['n_input_stars']:,} stars -> "
              f"{prov['n_excluded']:,} excluded, {prov['n_retained']:,} retained "
              f"({prov['duration_seconds']:.1f}s)")


if __name__ == '__main__':
    main()
