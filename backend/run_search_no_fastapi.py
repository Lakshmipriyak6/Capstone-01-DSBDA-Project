import sys
import os
import heapq

# Ensure backend directory is on path to import dataset_pipeline
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dataset_pipeline import CSVIndexer
from app.dataset_service import dataset_service


def score_row(row: dict, query: str) -> float:
    q = query.lower()
    ctx = (row.get('context') or '').lower()
    ques = (row.get('question') or '').lower()
    ans = (row.get('answer') or '').lower()
    c = ctx.count(q)
    qn = ques.count(q)
    a = ans.count(q)
    return float(qn) * 3.0 + float(a) * 2.0 + float(c) * 1.0


def run_search(query: str, top_k: int = 5):
    csv_path = dataset_service.csv_path
    indexer = CSVIndexer(str(csv_path), index_path=str(csv_path) + '.idx.json')
    indexer.build_index()

    heap = []
    counter = 0
    for chunk in indexer.iter_chunks(1000):
        for row in chunk:
            sc = score_row(row, query)
            if sc <= 0:
                continue
            item = (sc, counter, {'context': row.get('context', ''), 'question': row.get('question', ''), 'answer': row.get('answer', ''), 'score': sc})
            counter += 1
            if len(heap) < top_k:
                heapq.heappush(heap, item)
            else:
                if item[0] > heap[0][0]:
                    heapq.heapreplace(heap, item)

    results = [h[2] for h in sorted(heap, key=lambda x: (-x[0], x[1]))]
    return {'query': query, 'results': results}


if __name__ == '__main__':
    out = run_search('Beyonce', top_k=5)
    import json

    print(json.dumps(out, indent=2))
