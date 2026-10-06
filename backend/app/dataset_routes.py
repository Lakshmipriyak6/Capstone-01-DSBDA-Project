from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
import heapq

from app.dataset_service import dataset_service
from app.security import get_current_user

# dataset_pipeline is a top-level module (backend/dataset_pipeline.py)
from dataset_pipeline import CSVIndexer


router = APIRouter(prefix="/dataset", tags=["dataset"])


@router.get("/stats")
def get_dataset_stats():
    try:
        return dataset_service.get_stats()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/search")
def search_dataset(
    q: str = Query(..., description="Query string to search in context/question/answer"),
    top_k: int = Query(5, ge=1, le=50, description="Number of top results to return"),
    current_user=Depends(get_current_user),
):
    """Protected search over the indexed CSV. Streams the file and returns top-k matches.

    Relevance is a simple heuristic: counts occurrences (case-insensitive) across
    `context`, `question`, and `answer` fields with light weighting.
    """
    csv_path = dataset_service.csv_path
    try:
        indexer = CSVIndexer(str(csv_path), index_path=str(csv_path) + '.idx.json')
        # build or load existing index (fast if already present)
        indexer.build_index()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset file not found: {csv_path}") from exc

    query = q.strip().lower()
    if not query:
        return {"query": q, "results": []}

    # min-heap of (score, counter, result) to keep top_k
    heap = []
    counter = 0

    def score_row(row: dict) -> float:
        # Simple weighted substring-count scoring (case-insensitive)
        ctx = (row.get('context') or '').lower()
        ques = (row.get('question') or '').lower()
        ans = (row.get('answer') or '').lower()
        c = ctx.count(query)
        qn = ques.count(query)
        a = ans.count(query)
        # weights: question > answer > context
        return float(qn) * 3.0 + float(a) * 2.0 + float(c) * 1.0

    for chunk in CSVIndexer(str(csv_path)).iter_chunks(1000):
        for row in chunk:
            sc = score_row(row)
            if sc <= 0:
                continue
            # keep heap of size top_k
            item = (sc, counter, {'context': row.get('context', ''), 'question': row.get('question', ''), 'answer': row.get('answer', ''), 'score': sc})
            counter += 1
            if len(heap) < top_k:
                heapq.heappush(heap, item)
            else:
                # pushpop to maintain top_k largest by score
                if item[0] > heap[0][0]:
                    heapq.heapreplace(heap, item)

    # extract results ordered by descending score
    results = [h[2] for h in sorted(heap, key=lambda x: (-x[0], x[1]))]
    return {"query": q, "results": results}
