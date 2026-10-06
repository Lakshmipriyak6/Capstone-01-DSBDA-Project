import argparse
import csv
import random
import re
import unicodedata
import json
from collections import defaultdict


def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    s = unicodedata.normalize("NFKC", s)
    # replace runs of whitespace with single space
    s = re.sub(r"\s+", " ", s)
    # remove control characters (except common whitespace handled above)
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    return s


def sample_rows_for_detection(path, max_samples=5000):
    """Stream the CSV and uniformly sample up to max_samples rows for column analysis."""
    samples = []
    total = 0
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if len(samples) < max_samples:
                samples.append(row)
            else:
                # reservoir sampling
                r = random.randrange(total)
                if r < max_samples:
                    samples[r] = row
    return samples


def detect_text_columns(samples):
    """Given a list of sampled rows (dicts), return candidate text-like columns.

    Heuristics used:
    - Column is not purely numeric in the sample
    - Average length > 50 OR max length > 200
    - Non-empty ratio >= 0.2
    """
    if not samples:
        return []
    cols = list(samples[0].keys())
    stats = {c: {'count': 0, 'non_empty': 0, 'total_len': 0, 'max_len': 0, 'numeric_count': 0, 'unique': set()} for c in cols}
    for row in samples:
        for c in cols:
            v = row.get(c)
            if v is None:
                continue
            stats[c]['count'] += 1
            s = v.strip()
            if s == "":
                continue
            stats[c]['non_empty'] += 1
            L = len(s)
            stats[c]['total_len'] += L
            if L > stats[c]['max_len']:
                stats[c]['max_len'] = L
            # quick numeric test
            if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", s):
                stats[c]['numeric_count'] += 1
            if len(stats[c]['unique']) < 50:
                stats[c]['unique'].add(s)

    candidates = []
    n = len(samples)
    for c in cols:
        cnt = stats[c]['count']
        non_empty = stats[c]['non_empty']
        if cnt == 0:
            continue
        non_empty_ratio = non_empty / cnt
        avg_len = stats[c]['total_len'] / non_empty if non_empty else 0
        max_len = stats[c]['max_len']
        numeric_ratio = stats[c]['numeric_count'] / cnt
        unique_ratio = len(stats[c]['unique']) / max(1, non_empty)
        # Heuristic thresholds
        if numeric_ratio > 0.9:
            continue
        if avg_len > 50 or max_len > 200 or non_empty_ratio > 0.5 and avg_len > 20:
            candidates.append({'column': c, 'non_empty_ratio': non_empty_ratio, 'avg_len': avg_len, 'max_len': max_len, 'unique_ratio': unique_ratio})

    # sort by avg_len desc
    candidates.sort(key=lambda x: x['avg_len'], reverse=True)
    return candidates


def process_and_sample(input_path, output_path, columns, sample_size=5000):
    """Stream the input CSV and produce a cleaned, small sample CSV with selected columns.

    Uses reservoir sampling so the whole file is not loaded into memory.
    """
    reservoir = []
    seen_hashes = set()
    total_candidates = 0
    with open(input_path, newline='', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # build a combined text for dedup and emptiness test
            combined = []
            for c in columns:
                combined.append(clean_text(row.get(c, '')))
            combined_text = "\n".join([x for x in combined if x])
            if not combined_text:
                continue
            total_candidates += 1
            h = hash(combined_text)
            if h in seen_hashes:
                continue
            # consider for reservoir
            if len(reservoir) < sample_size:
                reservoir.append({c: clean_text(row.get(c, '')) for c in columns})
                seen_hashes.add(h)
            else:
                r = random.randrange(total_candidates)
                if r < sample_size:
                    # remove previous hash of replaced item
                    replaced = reservoir[r]
                    rep_combo = "\n".join([replaced.get(c, '') for c in columns])
                    seen_hashes.discard(hash(rep_combo))
                    reservoir[r] = {c: clean_text(row.get(c, '')) for c in columns}
                    seen_hashes.add(h)

    # final write
    with open(output_path, 'w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=columns)
        writer.writeheader()
        for row in reservoir:
            writer.writerow(row)

    summary = {'input_path': input_path, 'output_path': output_path, 'sample_size_requested': sample_size, 'sampled_rows': len(reservoir), 'candidate_rows_seen': total_candidates, 'columns': columns}
    summary_path = output_path + '.summary.json'
    with open(summary_path, 'w', encoding='utf-8') as s:
        json.dump(summary, s, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description='Stream and sample a large CSV into a small development dataset.')
    parser.add_argument('input_csv', help='Path to the large CSV file')
    parser.add_argument('--output', '-o', default='backend/processed_sample.csv', help='Path to write small processed CSV')
    parser.add_argument('--detect-samples', type=int, default=5000, help='Number of rows to sample for column detection')
    parser.add_argument('--sample-size', type=int, default=2000, help='Number of rows to produce in the small dataset')
    parser.add_argument('--top-cols', type=int, default=2, help='Number of top text-like columns to keep (by avg length)')
    args = parser.parse_args()

    print(f"Sampling up to {args.detect_samples} rows from {args.input_csv} for column detection...")
    samples = sample_rows_for_detection(args.input_csv, max_samples=args.detect_samples)
    candidates = detect_text_columns(samples)
    if not candidates:
        print("No text-like columns detected from the sample. Exiting.")
        return

    selected = [c['column'] for c in candidates[:args.top_cols]]
    print(f"Detected candidate text columns (ranked): {[c['column'] for c in candidates[:10]]}")
    print(f"Selected columns to keep: {selected}")

    print(f"Processing full CSV and sampling {args.sample_size} cleaned rows into {args.output}...")
    summary = process_and_sample(args.input_csv, args.output, selected, sample_size=args.sample_size)
    print("Done.")
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
