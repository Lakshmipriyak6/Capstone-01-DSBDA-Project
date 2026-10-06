import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.metrics.pairwise import cosine_similarity

from app.database import get_db
from app.models import Document, DocumentChunk, ChatMessage
from app.security import get_current_user
from app.models import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_user_documents(db: Session, user: User) -> list[Document]:
    return db.query(Document).filter(Document.user_id == user.id).order_by(Document.upload_date.asc()).all()


def _fit_document_tfidf(texts: list[str]):
    if not texts or not any(text.strip() for text in texts):
        return None, None
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
    try:
        return vectorizer, vectorizer.fit_transform(texts)
    except ValueError:
        return None, None


@router.get("/overview")
def analytics_overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = _get_user_documents(db, current_user)
    total_documents = len(docs)
    total_pages = sum(d.page_count or 0 for d in docs)
    total_words = sum(d.word_count or 0 for d in docs)
    total_chars = sum(d.char_count or 0 for d in docs)
    total_chunks = db.query(DocumentChunk).join(Document).filter(Document.user_id == current_user.id).count()
    total_questions = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).count()

    avg_doc_length = 0
    if total_documents:
        avg_doc_length = total_words / max(1, total_documents)

    most_recent = None
    if docs:
        d = max(docs, key=lambda x: x.upload_date)
        most_recent = {"id": d.id, "title": d.title, "upload_date": d.upload_date, "word_count": d.word_count}

    most_queried = None
    q = db.query(ChatMessage.document_id, func:=None)
    # find most queried document
    try:
        from sqlalchemy import func as sa_func
        res = db.query(ChatMessage.document_id, sa_func.count(ChatMessage.id).label("cnt")).filter(ChatMessage.user_id == current_user.id).group_by(ChatMessage.document_id).order_by(sa_func.count(ChatMessage.id).desc()).first()
        if res:
            doc = db.query(Document).filter(Document.id == res.document_id, Document.user_id == current_user.id).first()
            if doc:
                most_queried = {"id": doc.id, "title": doc.title, "questions": int(res.cnt)}
    except Exception:
        most_queried = None

    # categories distribution
    categories = Counter((d.category or "Unknown") for d in docs)

    # document word-count histogram
    word_count_histogram = [
        {"range": label, "count": 0}
        for label in ("0-499", "500-999", "1,000-2,499", "2,500-4,999", "5,000+")
    ]
    for doc in docs:
        word_count = max(0, doc.word_count or 0)
        if word_count < 500:
            bin_index = 0
        elif word_count < 1000:
            bin_index = 1
        elif word_count < 2500:
            bin_index = 2
        elif word_count < 5000:
            bin_index = 3
        else:
            bin_index = 4
        word_count_histogram[bin_index]["count"] += 1

    # upload timeline (counts per day)
    timeline = defaultdict(int)
    for d in docs:
        day = d.upload_date.date().isoformat()
        timeline[day] += 1

    return {
        "total_documents": total_documents,
        "total_pages": total_pages,
        "total_words": total_words,
        "total_characters": total_chars,
        "total_chunks": total_chunks,
        "total_questions": total_questions,
        "average_document_length": avg_doc_length,
        "most_recent_document": most_recent,
        "most_queried_document": most_queried,
        "categories": dict(categories),
        "word_count_histogram": word_count_histogram,
        "upload_timeline": dict(sorted(timeline.items())),
    }


@router.get("/topics")
def analytics_topics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = _get_user_documents(db, current_user)
    if not docs:
        return {"topics": [], "message": "No documents available"}

    texts = [d.extracted_text or "" for d in docs]
    ids = [d.id for d in docs]
    vectorizer, tfidf = _fit_document_tfidf(texts)
    if tfidf is None:
        return {"topics": [], "top_keywords": [], "message": "No extractable text available"}
    feature_names = vectorizer.get_feature_names_out()

    # top topics = top tf-idf terms across corpus
    avg_tfidf = np.asarray(tfidf.mean(axis=0)).ravel()
    top_indices = avg_tfidf.argsort()[::-1][:30]
    top_terms = [(feature_names[i], float(avg_tfidf[i])) for i in top_indices]

    # map documents to top keywords
    doc_topics = []
    for doc_idx, doc_vec in enumerate(tfidf):
        row = np.asarray(doc_vec.todense()).ravel()
        top_i = row.argsort()[::-1][:10]
        kws = [feature_names[i] for i in top_i if row[i] > 0]
        doc_topics.append({"document_id": ids[doc_idx], "keywords": kws})

    # frequency of top terms across docs
    freq = Counter()
    for d in doc_topics:
        freq.update(d["keywords"])

    topics = []
    for term, score in top_terms:
        topics.append({"topic": term, "score": score, "document_count": sum(1 for d in doc_topics if term in d["keywords"]), "documents": [d["document_id"] for d in doc_topics if term in d["keywords"]]})

    return {"topics": topics, "top_keywords": freq.most_common(50)}


@router.get("/similarity")
def analytics_similarity(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = [doc for doc in _get_user_documents(db, current_user) if (doc.extracted_text or "").strip()]
    if len(docs) < 2:
        return {"matrix": [], "documents": [], "message": "Need at least 2 documents to compute similarity"}

    texts = [d.extracted_text or "" for d in docs]
    ids = [d.id for d in docs]
    titles = [d.title for d in docs]

    vectorizer, tfidf = _fit_document_tfidf(texts)
    if tfidf is None:
        return {"matrix": [], "documents": [], "message": "No analyzable document text"}
    sim = cosine_similarity(tfidf)

    matrix = sim.tolist()
    pairs = []
    n = len(docs)
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append({"doc_a": ids[i], "doc_b": ids[j], "score": float(sim[i][j])})

    return {"matrix": matrix, "documents": [{"id": ids[i], "title": titles[i]} for i in range(len(docs))], "pairs": pairs}


@router.get("/clusters")
def analytics_clusters(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = [doc for doc in _get_user_documents(db, current_user) if (doc.extracted_text or "").strip()]
    if len(docs) < 3:
        return {"clusters": [], "message": "Not enough documents for clustering (need >=3)"}

    texts = [d.extracted_text or "" for d in docs]
    ids = [d.id for d in docs]

    vectorizer, tfidf = _fit_document_tfidf(texts)
    if tfidf is None:
        return {"clusters": [], "message": "No analyzable document text"}

    # choose k = min(8, sqrt(n_docs)) heuristic
    n_docs = len(docs)
    k = max(2, min(8, int(np.sqrt(n_docs)) or 2))
    try:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(tfidf)
        labels = kmeans.labels_
    except Exception:
        return {"clusters": [], "message": "Clustering failed"}

    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        clusters[int(label)].append(ids[idx])

    # representative keywords per cluster
    terms = vectorizer.get_feature_names_out()
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    cluster_defs = []
    for cluster_id, members in clusters.items():
        top_terms = [terms[ind] for ind in order_centroids[cluster_id, :8]]
        cluster_defs.append({"cluster_id": int(cluster_id), "size": len(members), "documents": members, "top_terms": top_terms})

    return {"clusters": cluster_defs}


@router.get("/knowledge-graph")
def analytics_knowledge_graph(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = _get_user_documents(db, current_user)
    nodes = []
    edges = []
    if not docs:
        return {"nodes": [], "edges": [], "message": "No documents"}

    # document nodes
    for d in docs:
        nodes.append({"id": f"doc_{d.id}", "label": d.title, "type": "document", "metadata": {"id": d.id, "word_count": d.word_count, "category": d.category}})

    # topic nodes (use top_terms)
    term_docs = defaultdict(list)
    for d in docs:
        try:
            terms = json.loads(d.top_terms) if d.top_terms else []
        except Exception:
            terms = []
        for t in terms[:12]:
            term_docs[t].append(d.id)

    for term, doc_ids in term_docs.items():
        nodes.append({"id": f"topic_{term}", "label": term, "type": "topic", "metadata": {"document_count": len(doc_ids)}})
        for doc_id in doc_ids:
            edges.append({"source": f"doc_{doc_id}", "target": f"topic_{term}", "relationship": "has_topic", "weight": 1})

    # related documents edges by similarity
    text_docs = [doc for doc in docs if (doc.extracted_text or "").strip()]
    if len(text_docs) >= 2:
        texts = [d.extracted_text or "" for d in text_docs]
        _, tfidf = _fit_document_tfidf(texts)
        if tfidf is not None:
            sim = cosine_similarity(tfidf)
            n = len(text_docs)
            for i in range(n):
                for j in range(i + 1, n):
                    score = float(sim[i][j])
                    if score > 0.45:
                        edges.append({"source": f"doc_{text_docs[i].id}", "target": f"doc_{text_docs[j].id}", "relationship": "similar", "weight": score})

    return {"nodes": nodes, "edges": edges}


@router.get("/trends")
def analytics_trends(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = _get_user_documents(db, current_user)
    if not docs:
        return {"trends": [], "message": "No documents"}

    # aggregate topics by month
    term_month = defaultdict(lambda: defaultdict(int))
    for d in docs:
        month = d.upload_date.strftime("%Y-%m")
        try:
            terms = json.loads(d.top_terms) if d.top_terms else []
        except Exception:
            terms = []
        for t in terms[:10]:
            term_month[t][month] += 1

    trends = []
    for term, months in term_month.items():
        series = sorted(months.items())
        trends.append({"topic": term, "series": series})

    return {"trends": trends}


@router.get("/outliers")
def analytics_outliers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = [doc for doc in _get_user_documents(db, current_user) if (doc.extracted_text or "").strip()]
    if len(docs) < 5:
        return {"outliers": [], "message": "Not enough documents for outlier detection (need >=5)"}

    texts = [d.extracted_text or "" for d in docs]
    ids = [d.id for d in docs]
    _, tfidf = _fit_document_tfidf(texts)
    if tfidf is None:
        return {"outliers": [], "message": "No analyzable document text"}
    try:
        iso = IsolationForest(contamination=0.1, random_state=42).fit(tfidf.toarray())
        scores = iso.decision_function(tfidf.toarray())
        preds = iso.predict(tfidf.toarray())
    except Exception:
        return {"outliers": [], "message": "Outlier detection failed"}

    outliers = []
    for idx, score in enumerate(scores):
        if preds[idx] == -1:
            d = docs[idx]
            outliers.append({"document_id": ids[idx], "title": d.title, "outlier_score": float(-score), "reason": "Low similarity to corpus or unusual vocabulary"})

    return {"outliers": outliers}


@router.get("/activity")
def analytics_activity(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_questions = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).count()
    recent = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).order_by(ChatMessage.created_at.desc()).limit(20).all()
    questions_over_time = defaultdict(int)
    topic_counter = Counter()
    for msg in recent:
        day = msg.created_at.date().isoformat()
        questions_over_time[day] += 1
        # crude topic extraction from question
        tokens = [t for t in (msg.question or "").lower().split() if len(t) > 3]
        topic_counter.update(tokens[:5])

    most_queried_docs = db.query(ChatMessage.document_id, sa_func:=None)
    try:
        from sqlalchemy import func as sa_func
        res = db.query(ChatMessage.document_id, sa_func.count(ChatMessage.id).label("cnt")).filter(ChatMessage.user_id == current_user.id).group_by(ChatMessage.document_id).order_by(sa_func.count(ChatMessage.id).desc()).limit(5).all()
        most_docs = []
        for item in res:
            doc = db.query(Document).filter(Document.id == item.document_id, Document.user_id == current_user.id).first()
            if doc:
                most_docs.append({"document_id": doc.id, "title": doc.title, "count": int(item.cnt)})
    except Exception:
        most_docs = []

    return {"total_questions": total_questions, "questions_over_time": dict(sorted(questions_over_time.items())), "recent_activity": [{"question": m.question, "answer": m.answer, "document_id": m.document_id, "created_at": m.created_at} for m in recent], "most_queried_documents": most_docs, "most_asked_topics": topic_counter.most_common(20)}
