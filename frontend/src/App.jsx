import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, CheckCircle2, ClipboardList, FileText, Play, ShieldCheck } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '');

function App() {
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState('');
  const [claimJson, setClaimJson] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/test-cases`)
      .then((res) => res.json())
      .then((data) => {
        setCases(data);
        setSelected(data[0]?.case_id || '');
        setClaimJson(JSON.stringify(data[0]?.input || {}, null, 2));
      });
  }, []);

  const selectedCase = useMemo(
    () => cases.find((item) => item.case_id === selected),
    [cases, selected],
  );

  const parsedClaim = useMemo(() => {
    try {
      return JSON.parse(claimJson || '{}');
    } catch {
      return null;
    }
  }, [claimJson]);

  const traceSummary = result
    ? `${result.trace.filter((item) => item.status === 'SUCCESS').length}/${result.trace.length} agents succeeded`
    : 'No run yet';

  function loadCase(caseId) {
    const testCase = cases.find((item) => item.case_id === caseId);
    setSelected(caseId);
    setResult(null);
    setClaimJson(JSON.stringify(testCase?.input || {}, null, 2));
  }

  async function submit() {
    setLoading(true);
    setResult(null);
    const response = await fetch(`${API}/api/claims/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: claimJson,
    });
    setResult(await response.json());
    setLoading(false);
  }

  return (
    <main className="app">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">P</div>
          <div>
            <h1>Claims Review Console</h1>
            <p>Agent pipeline, policy rules, and audit trace in one reviewer workflow.</p>
          </div>
        </div>
        <nav className="nav-metrics" aria-label="Pipeline summary">
          <span><FileText size={14} /> {cases.length || 0} eval cases</span>
          <span><Activity size={14} /> {parsedClaim?.claim_category || 'No category'}</span>
          <span className={result ? `nav-decision ${result.decision.toLowerCase()}` : 'nav-decision'}>
            {result?.decision || 'Ready'}
          </span>
        </nav>
        <button className="run-button" onClick={submit} disabled={loading}>
          <Play size={16} />
          {loading ? 'Processing' : 'Run Claim'}
        </button>
      </header>

      <section className="summary-rail">
        <div>
          <span>Selected Case</span>
          <strong>{selectedCase ? `${selectedCase.case_id} · ${selectedCase.case_name}` : 'Custom claim'}</strong>
        </div>
        <div>
          <span>Member</span>
          <strong>{parsedClaim?.member_id || 'N/A'}</strong>
        </div>
        <div>
          <span>Trace Health</span>
          <strong>{traceSummary}</strong>
        </div>
      </section>

      <section className="workspace">
        <div className="panel input-panel">
          <div className="panel-title">
            <div>
              <ClipboardList size={18} />
              <span>Claim Submission</span>
            </div>
            <small>Editable JSON input</small>
          </div>
          <label>
            Test case
            <select value={selected} onChange={(event) => loadCase(event.target.value)}>
              {cases.map((item) => (
                <option key={item.case_id} value={item.case_id}>
                  {item.case_id} - {item.case_name}
                </option>
              ))}
            </select>
          </label>
          {selectedCase && <p className="case-copy">{selectedCase.description}</p>}
          <label>
            Claim JSON
            <textarea value={claimJson} onChange={(event) => setClaimJson(event.target.value)} />
          </label>
        </div>

        <div className="panel result-panel">
          <div className="panel-title">
            <div>
              <ShieldCheck size={18} />
              <span>Decision Review</span>
            </div>
            <small>{result ? result.claim_id : 'Awaiting run'}</small>
          </div>
          {!result && (
            <div className="empty-state">
              <ShieldCheck size={34} />
              <strong>No decision yet</strong>
              <p>Run the selected claim to inspect payout, evidence, confidence, and agent trace.</p>
            </div>
          )}
          {result && (
            <>
              <div className={`decision ${result.decision.toLowerCase()}`}>
                <span>{result.decision === 'BLOCKED' ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}</span>
                <div>
                  <strong>{result.decision}</strong>
                  <p>{result.reason}</p>
                </div>
              </div>
              <div className="metrics">
                <div>
                  <span>{result.decision === 'BLOCKED' ? 'Claim Amount' : 'Approved Amount'}</span>
                  <strong>{result.decision === 'BLOCKED' ? 'N/A' : `Rs ${result.approved_amount}`}</strong>
                </div>
                <div>
                  <span>{result.decision === 'BLOCKED' ? 'Validation Confidence' : 'Confidence'}</span>
                  <strong>{Math.round(result.confidence_score * 100)}%</strong>
                </div>
              </div>
              {result.next_action && <p className="next-action">{result.next_action}</p>}
              <h2>Evidence</h2>
              <ul className="evidence">
                {result.evidence.slice(0, 14).map((item, index) => <li key={index}>{item}</li>)}
              </ul>
              <h2>Agent Trace</h2>
              <div className="trace">
                {result.trace.map((event, index) => (
                  <details key={`${event.agent}-${index}`} open={index < 2}>
                    <summary>
                      <span className={`status ${event.status.toLowerCase()}`}>{event.status}</span>
                      {event.agent}
                    </summary>
                    <p>{event.summary}</p>
                    {event.checks.map((check, checkIndex) => (
                      <div className="check" key={checkIndex}>
                        <strong>{check.rule_id || 'CHECK'}: {check.result}</strong>
                        <span>{check.details}</span>
                      </div>
                    ))}
                  </details>
                ))}
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
