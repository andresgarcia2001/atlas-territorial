"""Measure concurrent map API latency without exposing response bodies."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _percentile(values, percentile):
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_durations(durations):
    durations = list(durations)
    milliseconds = [duration * 1000 for duration in durations]
    return {
        "count": len(milliseconds),
        "p50_ms": _percentile(milliseconds, 0.50),
        "p95_ms": _percentile(milliseconds, 0.95),
        "p99_ms": _percentile(milliseconds, 0.99),
        "min_ms": min(milliseconds, default=0.0),
        "max_ms": max(milliseconds, default=0.0),
    }


def _request_once(url, timeout):
    started = time.monotonic()
    status = None
    response_size = 0
    error = None
    try:
        request = Request(url, headers={"Accept": "application/vnd.mapbox-vector-tile,application/json"})
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            response_size = len(response.read())
    except HTTPError as caught_error:
        status = caught_error.code
        error = "http_error"
    except (URLError, OSError, TimeoutError):
        error = "transport_error"

    return {
        "duration_s": time.monotonic() - started,
        "status": status,
        "response_size": response_size,
        "error": error,
    }


def measure(url, requests, concurrency, timeout=30.0):
    if requests <= 0 or concurrency <= 0:
        raise ValueError("requests and concurrency must be positive")

    results = []
    with ThreadPoolExecutor(max_workers=min(requests, concurrency)) as executor:
        futures = [executor.submit(_request_once, url, timeout) for _ in range(requests)]
        for future in as_completed(futures):
            results.append(future.result())

    durations = [result["duration_s"] for result in results]
    statuses = {}
    errors = {}
    sizes = [result["response_size"] for result in results]
    for result in results:
        status_key = str(result["status"]) if result["status"] is not None else "transport_error"
        statuses[status_key] = statuses.get(status_key, 0) + 1
        if result["error"]:
            errors[result["error"]] = errors.get(result["error"], 0) + 1

    return {
        "url": url,
        "requests": requests,
        "concurrency": concurrency,
        "status_counts": statuses,
        "errors": errors,
        **summarize_durations(durations),
        "response_size": {
            "count": len(sizes),
            "min_bytes": min(sizes, default=0),
            "max_bytes": max(sizes, default=0),
            "avg_bytes": sum(sizes) / len(sizes) if sizes else 0.0,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    print(json.dumps(measure(args.url, args.requests, args.concurrency, args.timeout), indent=2))


if __name__ == "__main__":
    main()
