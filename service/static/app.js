const pretty = (value) => JSON.stringify(value, null, 2);

const SCENARIOS = {
  'Prime Borrower': { credit_score: 780, orig_ltv: 65, orig_dti: 25, orig_upb: 350000, orig_interest_rate: 6.5 },
  'Borderline':     { credit_score: 700, orig_ltv: 85, orig_dti: 40, orig_upb: 350000, orig_interest_rate: 6.5 },
  'High Risk':      { credit_score: 620, orig_ltv: 97, orig_dti: 49, orig_upb: 350000, orig_interest_rate: 7.4 },
};

const jobPayloadTemplates = {
  "seed-demo": {
    output_dir: "data/raw/fannie_mae/combined",
    filename: "demo_2025Q1.csv",
    n_loans: 120,
    months: 6,
    seed: 42,
    overwrite: true,
  },
  pipeline: { source: "fannie-mae", model: "sklearn-logreg" },
  train: { model: "sklearn-logreg" },
  monitor: {
    reference_path: "data/processed/fannie_mae/features/features.parquet",
    current_path: "data/processed/fannie_mae/features/features.parquet",
    score_ref_col: "orig_ltv",
    score_cur_col: "orig_ltv",
    output_dir: "reports/monitoring",
  },
};

async function readJson(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return body;
}

function setOutput(id, data, isError = false) {
  const el = document.getElementById(id);
  el.textContent = typeof data === "string" ? data : pretty(data);
  el.classList.toggle("error", isError);
}

async function fetchNarrative(contextType, data) {
  try {
    const result = await fetch("/ai/interpret", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context_type: contextType, data }),
    }).then(readJson);
    return result.narrative || null;
  } catch {
    return null; // narrative is non-critical — degrade silently
  }
}

function setNarrative(id, narrative) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = narrative || "";
  el.hidden = !narrative;
}

function renderForecastChart(rows, threshold) {
  const chartEl = document.getElementById("forecastChart");
  const summaryEl = document.getElementById("forecastSummary");
  if (!Array.isArray(rows) || rows.length === 0) {
    chartEl.textContent = "No forecast points available.";
    summaryEl.textContent = "No exceedance summary yet.";
    return;
  }

  const parsed = rows
    .map((r, i) => ({
      i,
      ds: String(r.ds || ""),
      yhat: Number(r.yhat),
      yhatLower: Number(r.yhat_lower),
      yhatUpper: Number(r.yhat_upper),
    }))
    .filter((r) => Number.isFinite(r.yhat));

  if (parsed.length === 0) {
    chartEl.textContent = "Forecast response did not include numeric yhat values.";
    summaryEl.textContent = "No exceedance summary yet.";
    return;
  }

  const width = 760;
  const height = 320;
  const left = 48;
  const right = 16;
  const top = 28;
  const bottom = 40;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const xDenom = Math.max(1, parsed.length - 1);
  const x = (idx) => left + (idx / xDenom) * plotW;
  const y = (v) => top + (1 - Math.max(0, Math.min(1, v))) * plotH;

  const points = parsed.map((p, idx) => `${x(idx).toFixed(2)},${y(p.yhat).toFixed(2)}`).join(" ");
  const exceed = parsed.filter((p) => p.yhat >= threshold);
  const firstExceed = exceed.length ? exceed[0].ds : null;

  const circles = parsed.map((p, idx) => {
    const fill = p.yhat >= threshold ? "#b42318" : "#006d77";
    return `<circle cx="${x(idx).toFixed(2)}" cy="${y(p.yhat).toFixed(2)}" r="3.3" fill="${fill}" />`;
  }).join("");

  const labels = [
    parsed[0]?.ds || "",
    parsed[Math.floor((parsed.length - 1) / 2)]?.ds || "",
    parsed[parsed.length - 1]?.ds || "",
  ];

  chartEl.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Forecast yhat chart with threshold">
      <rect x="${left}" y="${top}" width="${plotW}" height="${plotH}" fill="#ffffff" stroke="#d9d2c4" />
      <line x1="${left}" x2="${left + plotW}" y1="${y(threshold).toFixed(2)}" y2="${y(threshold).toFixed(2)}" stroke="#b42318" stroke-dasharray="6 4" />
      <text x="${left + 6}" y="${(y(threshold) - 6).toFixed(2)}" fill="#b42318" font-size="11">threshold ${threshold.toFixed(2)}</text>
      <polyline fill="none" stroke="#006d77" stroke-width="2.4" points="${points}" />
      ${circles}
      <text x="${left}" y="${height - 10}" fill="#425160" font-size="11">${labels[0]}</text>
      <text x="${(left + plotW / 2 - 28).toFixed(2)}" y="${height - 10}" fill="#425160" font-size="11">${labels[1]}</text>
      <text x="${(left + plotW - 58).toFixed(2)}" y="${height - 10}" fill="#425160" font-size="11">${labels[2]}</text>
    </svg>
  `;

  if (firstExceed) {
    summaryEl.textContent = `${exceed.length} of ${parsed.length} points exceed ${threshold.toFixed(2)}. First exceedance: ${firstExceed}.`;
  } else {
    summaryEl.textContent = `No points exceed ${threshold.toFixed(2)}.`;
  }
}

function getRiskTier(pd) {
  if (pd < 0.25) return { label: 'Low',       cls: 'badge-success' };
  if (pd < 0.50) return { label: 'Moderate',  cls: 'badge-warning' };
  if (pd < 0.75) return { label: 'High',      cls: 'badge-danger'  };
  return               { label: 'Very High',  cls: 'badge-danger'  };
}

function renderScoreGauge(containerEl, pd) {
  const r = 70, cx = 100, cy = 90;
  const circ = Math.PI * r;
  const safe = Math.min(1, Math.max(0, pd));
  const dashOffset = circ * (1 - safe);
  const color = pd < 0.25 ? 'var(--success)' : pd < 0.5 ? 'var(--warning)' : 'var(--danger)';
  const pct = Math.round(pd * 100);
  containerEl.innerHTML = `
    <svg viewBox="0 0 200 100" role="img" aria-label="Risk gauge: ${pct}%">
      <path d="M ${cx - r},${cy} A ${r},${r} 0 0,1 ${cx + r},${cy}"
            fill="none" stroke="var(--line)" stroke-width="14" stroke-linecap="round"/>
      <path d="M ${cx - r},${cy} A ${r},${r} 0 0,1 ${cx + r},${cy}"
            fill="none" stroke="${color}" stroke-width="14" stroke-linecap="round"
            stroke-dasharray="${circ.toFixed(2)}" stroke-dashoffset="${dashOffset.toFixed(2)}"/>
      <text x="${cx}" y="${cy - 12}" text-anchor="middle" fill="var(--ink)"
            font-size="26" font-weight="700" font-family="inherit">${pct}%</text>
    </svg>`;
}

function renderRiskBadge(badgeEl, pd) {
  const tier = getRiskTier(pd);
  badgeEl.className = `badge ${tier.cls}`;
  badgeEl.textContent = tier.label;
}

function renderFactorBars(containerEl, factors) {
  if (!factors || factors.length === 0) {
    containerEl.innerHTML = '<p class="chart-summary">No factor data available.</p>';
    return;
  }
  const maxAbs = Math.max(...factors.map(f => Math.abs(f.value)), 0.001);
  const rows = factors.map(f => {
    const pct = (Math.abs(f.value) / maxAbs * 50).toFixed(1);
    const dir = f.value > 0 ? 'right' : 'left';
    const cls = f.value > 0 ? 'bar-risk' : 'bar-safe';
    return `<div class="factor-row">
      <span class="factor-label">${f.name}</span>
      <div class="factor-track">
        <div class="factor-bar ${cls} factor-bar--${dir}" style="width:${pct}%"></div>
      </div>
    </div>`;
  }).join('');
  containerEl.innerHTML = `<div class="factor-bars">${rows}</div>`;
}

function renderScorePanel(payload) {
  const gaugeEl   = document.getElementById('scoreGauge');
  const badgeEl   = document.getElementById('scoreBadge');
  const factorsEl = document.getElementById('scoreFactors');
  const panelEl   = document.getElementById('scorePanel');
  const errEl     = document.getElementById('scoreError');
  renderScoreGauge(gaugeEl, payload.pd);
  renderRiskBadge(badgeEl, payload.pd);
  renderFactorBars(factorsEl, payload.top_factors);
  panelEl.hidden = false;
  errEl.hidden = true;
}

async function loadStatus() {
  try {
    const [health, metadata] = await Promise.all([
      fetch("/health").then(readJson),
      fetch("/metadata").then(readJson),
    ]);
    document.getElementById("healthBadge").textContent = `API: ${health.status}`;
    document.getElementById("modeBadge").textContent = `Mode: ${metadata.mode}`;
  } catch (error) {
    document.getElementById("healthBadge").textContent = "API: error";
  }
}

function initForecastForm() {
  const form = document.getElementById("forecastForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const source = form.source.value.trim();
    const horizon = Number(form.horizon.value);
    const alertThreshold = Number(form.alertThreshold.value);
    try {
      const payload = await fetch("/forecast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, model: "prophet", horizon }),
      }).then(readJson);
      renderForecastChart(payload.forecast || [], alertThreshold);
      setNarrative("forecastNarrative", null); // clear previous
      const forecastData = { forecast: payload.forecast || [], threshold: alertThreshold };
      fetchNarrative("forecast", forecastData).then((narrative) => setNarrative("forecastNarrative", narrative));
    } catch (error) {
      const summaryEl = document.getElementById("forecastSummary");
      summaryEl.textContent = `Error: ${error.message}`;
      summaryEl.classList.add("error");
      renderForecastChart([], alertThreshold);
      setNarrative("forecastNarrative", null);
    }
  });
}

function initScoreForm() {
  const form = document.getElementById("scoreForm");

  form.querySelectorAll('[data-scenario]').forEach(btn => {
    btn.addEventListener('click', () => {
      form.features.value = pretty(SCENARIOS[btn.dataset.scenario]);
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const features = JSON.parse(form.features.value);
      const threshold = Number(form.threshold.value);
      const payload = await fetch("/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ features, threshold }),
      }).then(readJson);
      renderScorePanel(payload);
      setNarrative("scoreNarrative", null); // clear previous
      fetchNarrative("score", payload).then((narrative) => setNarrative("scoreNarrative", narrative));
    } catch (error) {
      document.getElementById('scorePanel').hidden = true;
      const scoreErrEl = document.getElementById('scoreError');
      scoreErrEl.textContent = error.message;
      scoreErrEl.hidden = false;
      setNarrative("scoreNarrative", null);
    }
  });
}

function initBatchForm() {
  const form = document.getElementById("batchForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const records = JSON.parse(form.records.value);
      const payload = await fetch("/batch_score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ records }),
      }).then(readJson);
      portfolioSort = { col: 'pd', dir: 'desc' }; // reset sort on new results
      renderPortfolioTable(payload.results || []);
      renderDonutChart(payload.results || []);
      setNarrative("batchNarrative", null);
      fetchNarrative("batch", payload).then(n => setNarrative("batchNarrative", n));
    } catch (error) {
      const container = document.getElementById('portfolioTable');
      if (container) container.innerHTML = `<p class="mono error">${error.message}</p>`;
      setNarrative("batchNarrative", null);
    }
  });
}

function renderJobs(el, payload) {
  const jobs = Array.isArray(payload.jobs) ? payload.jobs : (payload.id ? [payload] : []);
  if (!jobs.length) {
    el.innerHTML = '<p class="chart-summary">No jobs yet.</p>';
    return;
  }
  const statusCls = s => s === 'complete' ? 'badge-success' : s === 'running' ? 'badge-warning' : s === 'failed' ? 'badge-danger' : '';
  const fmt = iso => iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
  const dur = j => {
    if (!j.started_at) return '—';
    const s = Math.round((new Date(j.finished_at || Date.now()) - new Date(j.started_at)) / 1000);
    return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
  };
  el.innerHTML = `<table class="data-table">
    <thead><tr><th>Type</th><th>Status</th><th>Started</th><th>Duration</th></tr></thead>
    <tbody>${jobs.map(j => `<tr>
      <td>${j.job_type}</td>
      <td><span class="badge ${statusCls(j.status)}">${j.status}</span></td>
      <td>${fmt(j.started_at || j.created_at)}</td>
      <td>${dur(j)}</td>
    </tr>`).join('')}</tbody>
  </table>`;
}

function renderModels(el, payload) {
  if (!payload || (!payload.models && !payload.version_id)) {
    el.innerHTML = '<p class="chart-summary">No model catalog loaded yet.</p>';
    return;
  }
  // ActiveModelResponse from POST /models/activate — show inline then refreshModels() fills catalog
  if (payload.version_id && !payload.models) {
    el.innerHTML = `<p class="chart-summary"><span class="badge badge-success">Activated</span> ${payload.name} — <code>${payload.version_id.slice(0, 8)}</code></p>`;
    return;
  }
  const { models = [], active = null } = payload;
  el.innerHTML = `
    ${active ? `<p class="chart-summary" style="margin-bottom:8px"><span class="badge badge-success">Active</span> ${active.name} — <code>${active.version_id?.slice(0, 8) ?? '—'}</code></p>` : ''}
    <table class="data-table">
      <thead><tr><th>Model</th><th>Versions</th><th>Latest ID</th></tr></thead>
      <tbody>${models.map(m => `<tr>
        <td>${m.name}${active?.name === m.name ? ' <span class="badge badge-success" style="font-size:0.7rem;padding:1px 6px;margin-left:4px">active</span>' : ''}</td>
        <td>${m.version_count}</td>
        <td><code>${m.latest_version_id?.slice(0, 8) ?? '—'}</code></td>
      </tr>`).join('')}</tbody>
    </table>`;
}

async function refreshJobs() {
  const el = document.getElementById("jobsView");
  try {
    const payload = await fetch("/jobs?limit=20").then(readJson);
    renderJobs(el, payload);
  } catch (error) {
    el.innerHTML = `<p class="chart-summary error">${error.message}</p>`;
  }
}

function initJobsForm() {
  const form = document.getElementById("jobForm");
  const typeEl = form.jobType;
  const payloadEl = form.payload;
  const refreshBtn = document.getElementById("refreshJobsBtn");

  typeEl.addEventListener("change", () => {
    const template = jobPayloadTemplates[typeEl.value] || {};
    payloadEl.value = pretty(template);
  });

  refreshBtn.addEventListener("click", refreshJobs);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const jobType = typeEl.value;
      const payload = JSON.parse(payloadEl.value);
      const created = await fetch(`/jobs/${jobType}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(readJson);
      refreshJobs();
    } catch (error) {
      document.getElementById("jobsView").innerHTML = `<p class="chart-summary error">${error.message}</p>`;
    }
  });

  refreshJobs();
  setInterval(refreshJobs, 4000);
}

async function refreshModels() {
  const el = document.getElementById("modelsView");
  try {
    const payload = await fetch("/models").then(readJson);
    renderModels(el, payload);
  } catch (error) {
    el.innerHTML = `<p class="chart-summary error">${error.message}</p>`;
  }
}

function initModelForm() {
  const form = document.getElementById("modelForm");
  const refreshBtn = document.getElementById("refreshModelsBtn");
  refreshBtn.addEventListener("click", refreshModels);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const name = form.modelName.value;
      const versionId = form.versionId.value.trim();
      const body = versionId ? { name, version_id: versionId } : { name };
      const payload = await fetch("/models/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then(readJson);
      renderModels(document.getElementById("modelsView"), payload);
      refreshModels();
    } catch (error) {
      document.getElementById("modelsView").innerHTML = `<p class="chart-summary error">${error.message}</p>`;
    }
  });

  refreshModels();
}

function getDriftClass(psi) {
  // MON-02 display thresholds from requirements (NOT the backend PSI_ALERT=0.25 constant)
  if (psi < 0.1)  return 'badge-success';
  if (psi <= 0.2) return 'badge-warning';
  return 'badge-danger';
}

function renderDriftIndicators(driftFeatures) {
  const container = document.getElementById('driftIndicators');
  if (!container) return;
  if (!driftFeatures || Object.keys(driftFeatures).length === 0) {
    container.innerHTML = '<p class="chart-summary">No drift data available.</p>';
    return;
  }
  const badges = Object.entries(driftFeatures).map(([name, data]) => {
    const cls = getDriftClass(data.psi || 0);
    const psiLabel = (data.psi || 0).toFixed(3);
    return `<span class="badge ${cls} drift-feature-badge" title="PSI: ${psiLabel}">${name}</span>`;
  }).join('');
  container.innerHTML = `
    <p class="chart-summary drift-legend">Feature drift (PSI): <span class="drift-key drift-ok">green &lt;0.1</span> &middot; <span class="drift-key drift-warn">yellow 0.1&ndash;0.2</span> &middot; <span class="drift-key drift-alert">red &gt;0.2</span></p>
    <div class="drift-badges">${badges}</div>`;
}

function renderAucRow(perfDrift) {
  const container = document.getElementById('modelAucRow');
  if (!container) return;
  if (!perfDrift || perfDrift.latest_auc == null) {
    container.innerHTML = '<p class="chart-summary">AUC: Not yet available (labels pending)</p>';
    return;
  }
  const auc = perfDrift.latest_auc.toFixed(2);
  const trend = perfDrift.trend || 'unknown';
  const trendBadge = trend === 'improving'
    ? '<span class="badge badge-success">Improving</span>'
    : trend === 'degrading'
      ? '<span class="badge badge-danger">Degrading</span>'
      : '<span class="badge">Stable</span>';
  container.innerHTML = `<p class="chart-summary">AUC: <strong>${auc}</strong> ${trendBadge}</p>`;
}

function renderMonitoringPanel(payload) {
  if (!payload || !payload.available) {
    const container = document.getElementById('driftIndicators');
    if (container) container.innerHTML = '<p class="chart-summary">No monitoring data yet. Run a monitoring job to see results.</p>';
    const aucContainer = document.getElementById('modelAucRow');
    if (aucContainer) aucContainer.innerHTML = '';
    return;
  }
  renderDriftIndicators(payload.drift_features);
  renderAucRow(payload.perf_drift);
}

async function loadMonitoring() {
  try {
    const monitoringPayload = await fetch("/monitoring/summary").then(readJson);
    renderMonitoringPanel(monitoringPayload);
    setNarrative("monitoringNarrative", null); // clear previous
    if (monitoringPayload.available) {
      fetchNarrative("monitoring", monitoringPayload)
        .then((narrative) => setNarrative("monitoringNarrative", narrative));
    }
  } catch (error) {
    const container = document.getElementById('driftIndicators');
    if (container) container.innerHTML = `<p class="mono error">${error.message}</p>`;
    setNarrative("monitoringNarrative", null);
  }
}

function initMonitoringSection() {
  const refreshBtn = document.getElementById("refreshMonitoringBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadMonitoring);
  }
  loadMonitoring();
}

function setStepState(stepIndex, state) {
  const steps = document.querySelectorAll('.demo-step');
  if (steps[stepIndex]) steps[stepIndex].dataset.state = state;
}

async function pollJobById(jobId, intervalMs = 3000, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await fetch(`/jobs/${jobId}`).then(readJson);
    if (job.status === 'succeeded') return job;
    if (job.status === 'failed') throw new Error(job.error || 'Job failed');
    await new Promise(res => setTimeout(res, intervalMs));
  }
  throw new Error(`Timeout: job ${jobId} did not complete within ${timeoutMs / 1000}s`);
}

async function submitJobWithRetry(jobType, payload, stepIndex) {
  setStepState(stepIndex, 'active');
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const created = await fetch(`/jobs/${jobType}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).then(readJson);
      await pollJobById(created.id);
      setStepState(stepIndex, 'done');
      return;
    } catch (err) {
      if (attempt === 0) continue; // silent retry
      throw err; // surface on second failure
    }
  }
}

function showDemoError(stepIndex, err) {
  setStepState(stepIndex, 'failed');
  // Grey out remaining steps
  const steps = document.querySelectorAll('.demo-step');
  for (let i = stepIndex + 1; i < steps.length; i++) {
    steps[i].dataset.state = 'pending';
  }

  // Inject error summary below the checklist
  const checklist = document.getElementById('demoChecklist');
  const existing = document.getElementById('demoErrorSummary');
  if (existing) existing.remove();

  const summary = document.createElement('div');
  summary.id = 'demoErrorSummary';
  summary.className = 'demo-error-summary';
  const shortMsg = err.message ? err.message.split('\n')[0].slice(0, 120) : 'Step failed';
  summary.innerHTML = `
    <details>
      <summary>Step failed: ${shortMsg}</summary>
      <pre>${err.message || ''}</pre>
    </details>
    <button type="button" id="restartDemoBtn">Restart from beginning</button>
  `;
  checklist.after(summary);

  // Wire restart button
  document.getElementById('restartDemoBtn').addEventListener('click', () => {
    summary.remove();
    startDemo();
  });
}

async function runFullDemo() {
  const btn = document.getElementById('runDemoBtn');
  const complete = document.getElementById('demoComplete');

  // Step 0: Seed demo data
  try {
    await submitJobWithRetry('seed-demo', jobPayloadTemplates['seed-demo'], 0);
  } catch (err) {
    showDemoError(0, err);
    btn.disabled = false;
    btn.textContent = 'Run Full Demo';
    return;
  }

  // Step 1: Train pipeline
  try {
    await submitJobWithRetry('pipeline', jobPayloadTemplates['pipeline'], 1);
  } catch (err) {
    showDemoError(1, err);
    btn.disabled = false;
    btn.textContent = 'Run Full Demo';
    return;
  }

  // Step 2: Activate model (sklearn-rf, latest version)
  setStepState(2, 'active');
  try {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await fetch('/models/activate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'sklearn-rf' }),
        }).then(readJson);
        break;
      } catch (err) {
        if (attempt === 0) continue;
        throw err;
      }
    }
    setStepState(2, 'done');
  } catch (err) {
    showDemoError(2, err);
    btn.disabled = false;
    btn.textContent = 'Run Full Demo';
    return;
  }

  // Step 3: Score loan (Prime Borrower scenario)
  setStepState(3, 'active');
  try {
    let scorePayload;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        scorePayload = await fetch('/score', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ features: SCENARIOS['Prime Borrower'], threshold: 0.5 }),
        }).then(readJson);
        break;
      } catch (err) {
        if (attempt === 0) continue;
        throw err;
      }
    }
    renderScorePanel(scorePayload);
    setNarrative('scoreNarrative', null);
    fetchNarrative('score', scorePayload).then(n => setNarrative('scoreNarrative', n));
    setStepState(3, 'done');
  } catch (err) {
    showDemoError(3, err);
    btn.disabled = false;
    btn.textContent = 'Run Full Demo';
    return;
  }

  // Step 4: Run forecast
  setStepState(4, 'active');
  try {
    let forecastPayload;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        forecastPayload = await fetch('/forecast', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: 'fannie-mae', model: 'prophet', horizon: 24 }),
        }).then(readJson);
        break;
      } catch (err) {
        if (attempt === 0) continue;
        throw err;
      }
    }
    renderForecastChart(forecastPayload.forecast || [], 0.5);
    setNarrative('forecastNarrative', null);
    fetchNarrative('forecast', { forecast: forecastPayload.forecast || [], threshold: 0.5 }).then(n => setNarrative('forecastNarrative', n));
    setStepState(4, 'done');
  } catch (err) {
    showDemoError(4, err);
    btn.disabled = false;
    btn.textContent = 'Run Full Demo';
    return;
  }

  // Completion
  complete.hidden = false;
  btn.disabled = false;
  btn.textContent = 'Run Again';

  // Auto-scroll to portfolio section after DOM update
  const portfolioEl = document.getElementById('portfolioTable');
  if (portfolioEl) {
    requestAnimationFrame(() => portfolioEl.closest('section')?.scrollIntoView({ behavior: 'smooth' }));
  }
}

function startDemo() {
  const btn = document.getElementById('runDemoBtn');
  const complete = document.getElementById('demoComplete');
  const errorSummary = document.getElementById('demoErrorSummary');

  // Reset all steps to pending
  document.querySelectorAll('.demo-step').forEach(step => {
    step.dataset.state = 'pending';
  });

  // Clear completion and error
  complete.hidden = true;
  if (errorSummary) errorSummary.remove();

  btn.disabled = true;
  btn.textContent = 'Running...';

  runFullDemo();
}

function initDemoButton() {
  const btn = document.getElementById('runDemoBtn');
  if (!btn) return;
  btn.addEventListener('click', startDemo);
}

let portfolioSort = { col: 'pd', dir: 'desc' };

function renderPortfolioTable(results) {
  const container = document.getElementById('portfolioTable');
  if (!container) return;
  if (!results || results.length === 0) {
    container.innerHTML = '<p class="chart-summary">No results.</p>';
    return;
  }

  const colMap = {
    loan: (r, i) => i + 1,
    pd: (r) => r.pd,
    tier: (r) => getRiskTier(r.pd).label,
    factor: (r) => (r.top_factors && r.top_factors[0]) ? r.top_factors[0].name : '—',
  };

  const sorted = [...results].sort((a, b) => {
    const aVal = colMap[portfolioSort.col](a, results.indexOf(a));
    const bVal = colMap[portfolioSort.col](b, results.indexOf(b));
    const dir = portfolioSort.dir === 'asc' ? 1 : -1;
    return aVal > bVal ? dir : aVal < bVal ? -dir : 0;
  });

  const headers = [
    { key: 'loan', label: 'Loan #' },
    { key: 'pd',   label: 'PD Score (%)' },
    { key: 'tier', label: 'Risk Tier' },
    { key: 'factor', label: 'Top Risk Factor' },
  ];

  const theadCells = headers.map(h => {
    const isActive = portfolioSort.col === h.key;
    const ariaSort = isActive ? (portfolioSort.dir === 'asc' ? 'ascending' : 'descending') : 'none';
    return `<th data-col="${h.key}" scope="col" aria-sort="${ariaSort}">${h.label}</th>`;
  }).join('');

  const tbodyRows = sorted.map((r, i) => {
    const loanNum = results.indexOf(r) + 1;
    const pdPct = (r.pd * 100).toFixed(1) + '%';
    const tier = getRiskTier(r.pd);
    const factor = (r.top_factors && r.top_factors[0]) ? r.top_factors[0].name : '—';
    return `<tr>
      <td>${loanNum}</td>
      <td>${pdPct}</td>
      <td><span class="badge ${tier.cls}">${tier.label}</span></td>
      <td>${factor}</td>
    </tr>`;
  }).join('');

  container.innerHTML = `
    <table>
      <thead><tr>${theadCells}</tr></thead>
      <tbody>${tbodyRows}</tbody>
    </table>
  `;

  // Wire sort click handlers
  container.querySelectorAll('th[data-col]').forEach(th => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (portfolioSort.col === col) {
        portfolioSort.dir = portfolioSort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        portfolioSort.col = col;
        portfolioSort.dir = 'asc';
      }
      renderPortfolioTable(results);
    });
  });
}

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = (angleDeg - 90) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx, cy, r, startAngle, endAngle) {
  const s = polarToCartesian(cx, cy, r, startAngle);
  const e = polarToCartesian(cx, cy, r, endAngle);
  const large = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
}

function renderDonutChart(results) {
  const container = document.getElementById('portfolioDonut');
  if (!container || !results || results.length === 0) return;

  const TIERS = [
    { key: 'Low',       color: '#1a7f37' },
    { key: 'Moderate',  color: '#9a6700' },
    { key: 'High',      color: '#d97706' },
    { key: 'Very High', color: '#b42318' },
  ];

  const counts = {};
  TIERS.forEach(t => { counts[t.key] = 0; });
  results.forEach(r => { counts[getRiskTier(r.pd).label]++; });

  const total = results.length;
  const cx = 90, cy = 90, r = 65, innerR = 38;
  const width = 260, height = 210;

  // Degenerate case: single tier has all loans
  const activeTiers = TIERS.filter(t => counts[t.key] > 0);
  if (activeTiers.length === 1) {
    const t = activeTiers[0];
    container.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Risk tier distribution">
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="${t.color}" />
        <circle cx="${cx}" cy="${cy}" r="${innerR}" fill="var(--card, #fff)" />
        <text x="${cx}" y="${cy + 5}" text-anchor="middle" fill="var(--ink)" font-size="11" font-weight="600">${total} ${t.key}</text>
      </svg>`;
    return;
  }

  // Multi-tier arcs
  let arcs = '';
  let labels = '';
  let currentAngle = 0;
  TIERS.forEach(t => {
    const count = counts[t.key];
    if (count === 0) return;
    const sweep = (count / total) * 360;
    const endAngle = currentAngle + sweep;
    const d = arcPath(cx, cy, r, currentAngle, endAngle);
    arcs += `<path d="${d}" fill="none" stroke="${t.color}" stroke-width="27" />`;

    // Label positioned at arc midpoint
    const midAngle = currentAngle + sweep / 2;
    const labelPos = polarToCartesian(cx, cy, r + 22, midAngle);
    labels += `<text x="${labelPos.x.toFixed(1)}" y="${labelPos.y.toFixed(1)}" text-anchor="middle" fill="var(--ink)" font-size="10">${t.key} (${count})</text>`;
    currentAngle = endAngle;
  });

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Risk tier distribution donut chart">
      ${arcs}
      <circle cx="${cx}" cy="${cy}" r="${innerR}" fill="var(--card, #fff)" />
      <text x="${cx}" y="${cy - 4}" text-anchor="middle" fill="var(--ink)" font-size="11" font-weight="600">${total}</text>
      <text x="${cx}" y="${cy + 12}" text-anchor="middle" fill="var(--ink)" font-size="9">loans</text>
      ${labels}
    </svg>`;
}

function bootstrap() {
  initDemoButton();
  initForecastForm();
  initScoreForm();
  initBatchForm();
  initJobsForm();
  initModelForm();
  initMonitoringSection();
  loadStatus();
}

bootstrap();
