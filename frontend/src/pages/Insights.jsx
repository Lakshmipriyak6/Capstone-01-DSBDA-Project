import React, { useEffect, useState, useMemo, useRef } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, BarChart, Bar, PieChart, Pie, Cell, Legend } from "recharts";
import ForceGraph2D from 'react-force-graph-2d';
import api from "../utils/api";
import "../App.css";

const colors = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc949"];

export default function InsightsPage() {
  const [overview, setOverview] = useState(null);
  const [topics, setTopics] = useState(null);
  const [similarity, setSimilarity] = useState(null);
  const [clusters, setClusters] = useState(null);
  const [graph, setGraph] = useState(null);
  const [trends, setTrends] = useState(null);
  const [outliers, setOutliers] = useState(null);
  const [activity, setActivity] = useState(null);
  const [analyticsError, setAnalyticsError] = useState("");
  const [datasetQuery, setDatasetQuery] = useState('');
  const [datasetResults, setDatasetResults] = useState(null);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [datasetError, setDatasetError] = useState(null);
  const fgRef = useRef();

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    setAnalyticsError("");
    try {
      const [ov, tp, sim, cl, kg, tr, ot, ac] = await Promise.all([
        api.get("/analytics/overview"),
        api.get("/analytics/topics"),
        api.get("/analytics/similarity"),
        api.get("/analytics/clusters"),
        api.get("/analytics/knowledge-graph"),
        api.get("/analytics/trends"),
        api.get("/analytics/outliers"),
        api.get("/analytics/activity"),
      ]);
      setOverview(ov.data);
      setTopics(tp.data);
      setSimilarity(sim.data);
      setClusters(cl.data);
      setGraph(kg.data);
      setTrends(tr.data);
      setOutliers(ot.data);
      setActivity(ac.data);
    } catch (err) {
      console.error("Analytics fetch failed:", err);
      setAnalyticsError(err?.response?.data?.detail || "Analytics could not be loaded. Please try again.");
    }
  };

  const runDatasetSearch = async (q) => {
    if (!q) return;
    setDatasetLoading(true);
    setDatasetError(null);
    try {
      const res = await api.get('/dataset/search', { params: { q, top_k: 5 } });
      setDatasetResults(res.data.results || []);
    } catch (err) {
      console.error('Dataset search failed', err);
      setDatasetError(err?.response?.data?.detail || err.message || 'Search failed');
      setDatasetResults([]);
    } finally {
      setDatasetLoading(false);
    }
  };

  const discoveries = useMemo(() => {
    if (!overview || !topics || !similarity) return [];
    const items = [];
    if (overview.most_queried_document) items.push({ title: "Most queried document", detail: overview.most_queried_document.title });
    if (overview.most_recent_document) items.push({ title: "Most recent upload", detail: overview.most_recent_document.title });
    if (topics.top_keywords && topics.top_keywords.length) items.push({ title: "Top keyword", detail: topics.top_keywords[0][0] });

    // most similar pair
    if (similarity.pairs && similarity.pairs.length) {
      const best = similarity.pairs.reduce((a, b) => (a.score > b.score ? a : b));
      const a = similarity.documents.find(d => d.id === best.doc_a);
      const b = similarity.documents.find(d => d.id === best.doc_b);
      if (a && b) items.push({ title: "Most similar pair", detail: `${a.title} ↔ ${b.title} (${(best.score*100).toFixed(0)}%)` });
    }

    return items;
  }, [overview, topics, similarity]);

  return (
    <div className="insights-page">
      <header className="panel">
        <h2>DocuMind Insights</h2>
        <p>Discover patterns, relationships and knowledge hidden across your documents.</p>
      </header>
      {analyticsError && (
        <div className="error-box" role="alert">
          {analyticsError}
          <button className="button secondary small" onClick={fetchAll}>Retry analytics</button>
        </div>
      )}

      <section className="panel-grid">
        <div className="stat-card large">
          <h4>Documents</h4>
          <strong>{overview?.total_documents ?? '—'}</strong>
        </div>
        <div className="stat-card large">
          <h4>Pages</h4>
          <strong>{overview?.total_pages ?? '—'}</strong>
        </div>
        <div className="stat-card large">
          <h4>Words</h4>
          <strong>{overview?.total_words ?? '—'}</strong>
        </div>
        <div className="stat-card large">
          <h4>Questions</h4>
          <strong>{overview?.total_questions ?? '—'}</strong>
        </div>
      </section>

      <section className="panel-grid">
        <div className="panel">
          <h3>Line Graph: Documents uploaded over time</h3>
          {overview?.upload_timeline && Object.keys(overview.upload_timeline).length ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={Object.entries(overview.upload_timeline).map(([k,v])=>({date:k,count:v}))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#4e79a7" />
              </LineChart>
            </ResponsiveContainer>
          ) : <div className="empty-state">No uploads yet</div>}
        </div>

        <div className="panel">
          <h3>Top Topics</h3>
          {topics?.topics?.length ? (
            <div className="topics-list">
              {topics.topics.slice(0,10).map(t => (
                <div key={t.topic} className="topic-row">
                  <strong>{t.topic}</strong>
                  <span>{t.document_count} docs</span>
                </div>
              ))}
            </div>
          ) : <div className="empty-state">No topics available</div>}
        </div>
      </section>

      <section className="panel-grid">
        <div className="panel">
          <h3>Bar Graph: Documents by Category</h3>
          {overview?.categories && Object.keys(overview.categories).length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={Object.entries(overview.categories).map(([category, count]) => ({ category, count }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="category" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#4e79a7" />
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="empty-state">No category data available</div>}
        </div>

        <div className="panel">
          <h3>Histogram: Document Word Count</h3>
          {overview?.total_documents > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={overview.word_count_histogram || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="range" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#f28e2b" />
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="empty-state">No documents to group by word count</div>}
        </div>
      </section>

      <section className="panel-grid">
        <div className="panel">
          <h3>Document Relationship Matrix</h3>
          {similarity?.matrix && similarity.matrix.length ? (
            <div className="matrix-scroll">
              <table className="similarity-matrix">
                <thead>
                  <tr>
                    <th></th>
                    {similarity.documents.map(d => <th key={d.id}>{d.title}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {similarity.matrix.map((row, i) => (
                    <tr key={i}>
                      <td className="matrix-label">{similarity.documents[i].title}</td>
                      {row.map((v, j) => (
                        <td key={j} style={{background:`rgba(14,76,122,${v})` , color: v>0.5? '#fff':'#000'}}>{(v*100).toFixed(0)}%</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="empty-state">Add at least 2 documents to compute similarity.</div>}
        </div>

        <div className="panel">
          <h3>Document Clusters</h3>
          {clusters?.clusters?.length ? (
            <div className="clusters-grid">
              {clusters.clusters.map(c => (
                <div key={c.cluster_id} className="cluster-card">
                  <h4>Cluster {c.cluster_id}</h4>
                  <div className="cluster-meta">{c.size} documents</div>
                  <div className="cluster-terms">{c.top_terms.join(', ')}</div>
                </div>
              ))}
            </div>
          ) : <div className="empty-state">Not enough documents for clustering.</div>}
        </div>
      </section>

      <section className="panel">
        <h3>DocuMind Knowledge Graph</h3>
        {graph?.nodes && graph.nodes.length ? (
          <div style={{height: 480}}>
            <ForceGraph2D
              ref={fgRef}
              graphData={graph}
              nodeAutoColorBy="type"
              nodeLabel={n => `${n.label} (${n.type})`}
              linkDirectionalParticles={1}
              linkDirectionalParticleWidth={l => Math.max(0.5, Math.min(4, (l.weight||0)*4))}
              onNodeClick={node => {
                // center on node
                fgRef.current.zoomToFit(400, 50, n => n.id === node.id);
              }}
            />
          </div>
        ) : <div className="empty-state">No graph data. Upload documents to generate a knowledge graph.</div>}
      </section>

      <section className="panel">
        <h3>Dataset Intelligence</h3>
        <p className="muted">Search the bundled dataset (needs authentication) for relevant context, questions and answers.</p>
        <div style={{display:'flex', gap:8, marginBottom:12}}>
          <input value={datasetQuery} onChange={e=>setDatasetQuery(e.target.value)} placeholder="Enter keyword or question" style={{flex:1,padding:'8px'}} />
          <button className="btn" onClick={()=>runDatasetSearch(datasetQuery)} disabled={datasetLoading}>{datasetLoading? 'Searching...':'Search'}</button>
        </div>
        {datasetError && <div className="error">{datasetError}</div>}
        {datasetResults && datasetResults.length ? (
          <div className="dataset-results">
            {datasetResults.map((r, i) => (
              <div key={i} className="result-card">
                <div className="result-score">{(r.score||0).toFixed(1)}</div>
                <div className="result-body">
                  <div className="result-question"><strong>Q:</strong> {r.question}</div>
                  <div className="result-answer"><strong>A:</strong> {r.answer}</div>
                  <div className="result-context muted">{r.context}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (datasetResults && datasetResults.length===0 ? <div className="empty-state">No matching results</div> : null)}
      </section>

      <section className="panel-grid">
        <div className="panel">
          <h3>Knowledge Trends</h3>
          {trends?.trends?.length ? (
            <div className="trends-list">
              {trends.trends.slice(0,6).map(t => (
                <div key={t.topic} className="trend-row">
                  <strong>{t.topic}</strong>
                  <div className="trend-series">{t.series.map(s=>`${s[0]}(${s[1]})`).join(' • ')}</div>
                </div>
              ))}
            </div>
          ) : <div className="empty-state">Insufficient temporal data for trends.</div>}
        </div>

        <div className="panel">
          <h3>Unusual Documents</h3>
          {outliers?.outliers && outliers.outliers.length ? (
            outliers.outliers.map(o => (
              <div key={o.document_id} className="outlier-card">
                <strong>{o.title}</strong>
                <div>Score: {o.outlier_score.toFixed(3)}</div>
                <div className="muted">{o.reason}</div>
              </div>
            ))
          ) : <div className="empty-state">No unusual documents detected.</div>}
        </div>
      </section>

      <section className="panel">
        <h3>Pattern Discovery</h3>
        <div className="discoveries-list">
          {discoveries.length ? discoveries.map(d => (
            <div key={d.title} className="discovery-item"><strong>{d.title}:</strong> {d.detail}</div>
          )) : <div className="empty-state">No discoveries yet.</div>}
        </div>
      </section>
    </div>
  );
}
