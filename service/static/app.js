const pretty = (value) => JSON.stringify(value, null, 2);
const jobPayloadTemplates = {
  "seed-demo": {
    output_dir: "data/raw/fannie_mae/combined",
    filename: "demo_2025Q1.csv",
    n_loans: 250,
    months: 8,
    seed: 42,
    overwrite: true,
  },
  train: { model: "sklearn-logreg" },
  pipeline: { source: "fannie-mae", model: "sklearn-logreg" },
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
    try {
      const payload = await fetch("/forecast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, model: "prophet", horizon }),
      }).then(readJson);
      setOutput("forecastView", payload);
    } catch (error) {
      setOutput("forecastView", error.message, true);
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
