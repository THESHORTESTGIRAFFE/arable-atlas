"""Prepare authentic soil maps before a demo; no API key or AI calls required."""
import argparse
import json
from pathlib import Path
from soil_provider import prefetch_region


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lat', type=float, required=True)
    parser.add_argument('--lon', type=float, required=True)
    parser.add_argument('--radius-km', type=float, default=10, help='Half-width of native-grid square (0.25–50 km)')
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--refresh', action='store_true', help='Replace an existing download of this exact region')
    args = parser.parse_args()
    try:
        result = prefetch_region(args.lat, args.lon, args.radius_km, args.cache_dir, args.refresh)
    except (ValueError, OverflowError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0 if all(p['status'] == 'downloaded' for p in result['properties'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
