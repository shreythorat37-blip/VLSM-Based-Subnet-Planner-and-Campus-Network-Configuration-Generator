"""Command-line interface for CampusNet Studio."""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from core import plan_vlsm, simulate_queue
from integrations.wireshark import analyze_capture
from ns2_analysis import analyze_ns2_trace


def _departments(values: list[str]) -> list[dict[str, Any]]:
    result = []
    for item in values:
        if '=' not in item:
            raise ValueError(f'Invalid department {item!r}; use NAME=HOSTS, for example CSE=120.')
        name, raw_hosts = item.rsplit('=', 1)
        try:
            hosts = int(raw_hosts)
        except ValueError:
            raise ValueError(f'Host count in {item!r} must be a whole number.') from None
        result.append({'name': name, 'hosts': hosts})
    if not result:
        raise ValueError('Provide at least one --department NAME=HOSTS.')
    return result


def _flatten(row: dict[str, Any]) -> dict[str, Any]:
    flat = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                flat[f'{key}_{subkey}'] = subvalue
        elif isinstance(value, (list, tuple)):
            flat[key] = json.dumps(value)
        else:
            flat[key] = value
    return flat


def _emit(data: Any, output: str | None, output_format: str) -> None:
    if output_format == 'json':
        rendered = json.dumps(data, indent=2)
        if output:
            destination = Path(output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered + '\n', encoding='utf-8')
        else:
            print(rendered)
        return
    if isinstance(data, dict) and isinstance(data.get('rows'), list):
        records = data['rows']
    elif isinstance(data, list):
        records = data
    else:
        records = [data]
    flat_rows = [_flatten(row) for row in records]
    fieldnames = list(dict.fromkeys(key for row in flat_rows for key in row))
    import io
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    writer.writerows(flat_rows)
    rendered = stream.getvalue()
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding='utf-8', newline='')
    else:
        sys.stdout.write(rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='campusnet', description='Plan subnets and analyze CampusNet experiment outputs.')
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan', help='Create and export a VLSM plan.')
    plan.add_argument('--base', required=True, help='Private base IPv4 network, for example 192.168.0.0/23.')
    plan.add_argument('--department', action='append', default=[], metavar='NAME=HOSTS', help='Repeat once per department.')
    plan.add_argument('--format', choices=('json', 'csv'), default='json')
    plan.add_argument('--output', help='Output file. Prints to the terminal if omitted.')

    sim = commands.add_parser('simulate', help='Run the Python queue model.')
    sim.add_argument('--algorithm', choices=('DropTail', 'RED'), default='DropTail')
    sim.add_argument('--duration', type=float, default=20.0)
    sim.add_argument('--arrival-rate', type=float, default=800.0)
    sim.add_argument('--bandwidth', type=float, default=5.0, help='Link rate in Mbps.')
    sim.add_argument('--queue-limit', type=int, default=50)
    sim.add_argument('--packet-size', type=int, default=1000, help='Packet size in bytes.')
    sim.add_argument('--seed', type=int, default=7)
    sim.add_argument('--red-min', type=int, default=10)
    sim.add_argument('--red-max', type=int, default=30)
    sim.add_argument('--format', choices=('json', 'csv'), default='json')
    sim.add_argument('--output')

    trace = commands.add_parser('analyze-ns2', help='Calculate metrics from a classic NS2 trace.')
    trace.add_argument('trace_file')
    trace.add_argument('--source-node', type=int, default=0)
    trace.add_argument('--destination-node', type=int, default=3)
    trace.add_argument('--duration', type=float, help='Use the simulation observation duration in seconds.')
    trace.add_argument('--format', choices=('json', 'csv'), default='json')
    trace.add_argument('--output')

    pcap = commands.add_parser('analyze-pcap', help='Summarize a Wireshark pcap/pcapng using TShark.')
    pcap.add_argument('capture_file')
    pcap.add_argument('--tshark', help='Full path to tshark.exe if it is not on PATH.')
    pcap.add_argument('--filter', dest='display_filter', help='Optional Wireshark display filter, for example "dhcp || dns".')
    pcap.add_argument('--format', choices=('json', 'csv'), default='json')
    pcap.add_argument('--output')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == 'plan':
            result = plan_vlsm(args.base, _departments(args.department))
        elif args.command == 'simulate':
            result = simulate_queue(args.algorithm, args.duration, args.arrival_rate, args.bandwidth,
                                    args.queue_limit, args.packet_size, args.seed, args.red_min, args.red_max)
        elif args.command == 'analyze-ns2':
            result = analyze_ns2_trace(args.trace_file, args.source_node, args.destination_node, args.duration)
        elif args.command == 'analyze-pcap':
            result = analyze_capture(args.capture_file, args.tshark, args.display_filter)
        else:
            parser.error('Unknown command.')
        _emit(result, args.output, args.format)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        parser.exit(2, f'error: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
