const pretty = (value) => JSON.stringify(value, null, 2);
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
      setOutput("forecastView", payload);
      renderForecastChart(payload.forecast || [], alertThreshold);
    } catch (error) {
      setOutput("forecastView", error.message, true);
      renderForecastChart([], alertThreshold);
    }
  });
}

function initScoreForm() {
  const form = document.getElementById("scoreForm");
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
      setOutput("scoreView", payload);
    } catch (error) {
      setOutput("scoreView", error.message, true);
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
      setOutput("batchView", payload);
    } catch (error) {
      setOutput("batchView", error.message, true);
    }
  });
}

async function refreshJobs() {
  try {
    const payload = await fetch("/jobs?limit=20").then(readJson);
    setOutput("jobsView", payload);
  } catch (error) {
    setOutput("jobsView", error.message, true);
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
      setOutput("jobsView", created);
      refreshJobs();
    } catch (error) {
      setOutput("jobsView", error.message, true);
    }
  });

  refreshJobs();
  setInterval(refreshJobs, 4000);
}

async function refreshModels() {
  try {
    const payload = await fetch("/models").then(readJson);
    setOutput("modelsView", payload);
  } catch (error) {
    setOutput("modelsView", error.message, true);
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
      setOutput("modelsView", payload);
      refreshModels();
    } catch (error) {
      setOutput("modelsView", error.message, true);
    }
  });

  refreshModels();
}

function bootstrap() {
  initForecastForm();
  initScoreForm();
  initBatchForm();
  initJobsForm();
  initModelForm();
  loadStatus();
}

bootstrap();
