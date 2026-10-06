import json
import os
from dataset_pipeline import CSVIndexer


def main():
    csv_path = os.path.join('dataset', 'DocuMind_AI_SQuAD2_Dataset.csv')
    indexer = CSVIndexer(csv_path, index_interval=1000)

    print('Building or loading index...')
    meta = indexer.build_index()
    print(json.dumps({'total_rows': meta['total_rows'], 'index_interval': meta['index_interval'], 'index_path': indexer.index_path}, indent=2))

    # fetch a few sample rows
    samples_to_check = [0, 1, 100, 1000, min(50000, meta['total_rows']-1), meta['total_rows']-1]
    samples = {}
    for idx in samples_to_check:
        if idx < 0 or idx >= meta['total_rows']:
            samples[idx] = None
            continue
        row = indexer.get_row_by_number(idx)
        # only include small preview of row fields
        if row is None:
            samples[idx] = None
        else:
            samples[idx] = {k: (v[:200] + '...') if v and len(v) > 200 else v for k, v in row.items()}

    print('Sample rows (previews):')
    print(json.dumps(samples, indent=2))

    # basic streaming check: count rows using iter_chunks but stop early
    cnt = 0
    for chunk in indexer.iter_chunks(10000):
        cnt += len(chunk)
        if cnt >= 20000:
            break
    print(f'Streamed approximately {cnt} rows in quick check (stopped early at 20000).')


if __name__ == '__main__':
    main()
