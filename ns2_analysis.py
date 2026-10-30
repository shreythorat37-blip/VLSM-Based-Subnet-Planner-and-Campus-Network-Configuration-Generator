"""Parse classic NS2 wired trace files and calculate basic delivery metrics."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def analyze_ns2_trace(trace_path: str | Path, source_node: int = 0, dest_node: int = 3,
                      duration_s: float | None = None) -> dict[str, Any]:
    """Summarize classic NS2 trace events for one source-to-destination flow.

    Counts '+' or 's' events at source_node as transmissions and 'r' events at
    dest_node as deliveries. Packet UID is the final field in classic traces.
    """
    path = Path(trace_path)
    sent: dict[str, tuple[float, int]] = {}
    received: dict[str, float] = {}
    dropped = 0
    malformed = 0
    first_time: float | None = None
    last_time: float | None = None
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('#'):
            continue
        try:
            if len(fields) < 12:
                raise ValueError('short trace row')
            event = fields[0]
            timestamp = float(fields[1])
            from_node, to_node = int(fields[2]), int(fields[3])
            packet_size = int(fields[5])
            uid = fields[11]
        except (ValueError, IndexError):
            malformed += 1
            continue
        first_time = timestamp if first_time is None else min(first_time, timestamp)
        last_time = timestamp if last_time is None else max(last_time, timestamp)
        if event in ('+', 's') and from_node == source_node:
            sent.setdefault(uid, (timestamp, packet_size))
        elif event == 'r' and to_node == dest_node:
            received.setdefault(uid, timestamp)
        elif event == 'd':
            dropped += 1

    sent_count = len(sent)
    received_ids = set(sent).intersection(received)
    received_count = len(received_ids)
    lost_count = max(sent_count - received_count, 0)
    observed_duration = duration_s
    if observed_duration is None:
        observed_duration = max((last_time or 0) - (first_time or 0), 0)
    if observed_duration <= 0:
        observed_duration = 0.0
    received_bytes = sum(sent[uid][1] for uid in received_ids)
    delays_ms = [(received[uid] - sent[uid][0]) * 1000 for uid in received_ids]
    return {
        'trace_file': path.name,
        'source_node': source_node,
        'destination_node': dest_node,
        'packets_sent': sent_count,
        'packets_received': received_count,
        'packets_lost': lost_count,
        'trace_drop_events': dropped,
        'packet_delivery_ratio_pct': round(received_count / sent_count * 100, 3) if sent_count else 0.0,
        'packet_loss_pct': round(lost_count / sent_count * 100, 3) if sent_count else 0.0,
        'throughput_mbps': round(received_bytes * 8 / observed_duration / 1_000_000, 6) if observed_duration else 0.0,
        'average_delay_ms': round(sum(delays_ms) / len(delays_ms), 4) if delays_ms else 0.0,
        'observation_duration_s': round(observed_duration, 6),
        'malformed_rows_ignored': malformed,
        'metric_note': 'Classic NS2 trace estimate. Sent/received counts use source/destination node and packet UID.'
    }
