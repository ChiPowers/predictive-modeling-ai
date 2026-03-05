const pretty = (value) => JSON.stringify(value, null, 2);
const AUTH_TOKEN_KEY = "pmai_auth_token";
const AUTH_USER_KEY = "pmai_auth_user";
const jobPayloadTemplates = {
  "seed-demo": {
    output_dir: "data/raw/fannie_mae/combined",
    filename: "demo_2025Q1.csv",
    n_loans: 2500,
    months: 18,
    seed: 42,
    overwrite: true,
  },
  train: { model: "sklearn-rf" },
  pipeline: { source: "fannie-mae", model: "sklearn-rf" },
  monitor: {
    reference_path: "data/processed/fannie_mae/features/features.parquet",
    current_path: "data/processed/fannie_mae/features/current_period.parquet",
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

function authToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function authHeaders() {
  const token = authToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function setOutput(id, data, isError = false) {
  const el = document.getElementById(id);
  el.textContent = typeof data === "string" ? data : pretty(data);
  el.classList.toggle("error", isError);
}

async function loadSnapshot() {
  try {
    const [health, metadata, monitoring] = await Promise.all([
      fetch("/health").then(readJson),
      fetch("/metadata").then(readJson),
      fetch("/monitoring/summary").then(readJson),
    ]);

    document.getElementById("healthBadge").textContent = `API: ${health.status}`;
    document.getElementById("modeBadge").textContent = `Mode: ${metadata.mode}`;

    setOutput("metadataView", metadata);
    setOutput("monitoringView", monitoring.summary_markdown || monitoring);
    const user = localStorage.getItem(AUTH_USER_KEY);
    if (user) {
      setOutput("authView", `Logged in as ${user}`);
    }
  } catch (error) {
    setOutput("metadataView", `Failed to load snapshot: ${error.message}`, true);
    setOutput("monitoringView", "Monitoring unavailable.", true);
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
    const endpoint = authToken() ? "/me/jobs?limit=20" : "/jobs?limit=20";
    const payload = await fetch(endpoint, { headers: authHeaders() }).then(readJson);
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
      const endpoint = authToken() ? `/me/jobs/${jobType}` : `/jobs/${jobType}`;
      const created = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
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
    const endpoint = authToken() ? "/me/models" : "/models";
    const payload = await fetch(endpoint, { headers: authHeaders() }).then(readJson);
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
      const endpoint = authToken() ? "/me/models/activate" : "/models/activate";
      const payload = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
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

function initAuthForm() {
  const form = document.getElementById("authForm");
  const registerBtn = document.getElementById("registerBtn");
  const logoutBtn = document.getElementById("logoutBtn");

  async function setLoggedInUser() {
    if (!authToken()) {
      setOutput("authView", "Not logged in. Demo mode still available.");
      return;
    }
    try {
      const me = await fetch("/auth/me", { headers: authHeaders() }).then(readJson);
      localStorage.setItem(AUTH_USER_KEY, me.username);
      setOutput("authView", `Logged in as ${me.username}`);
    } catch (error) {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(AUTH_USER_KEY);
      setOutput("authView", error.message, true);
    }
  }

  registerBtn.addEventListener("click", async () => {
    try {
      const payload = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.username.value.trim(),
          password: form.password.value,
        }),
      }).then(readJson);
      setOutput("authView", payload);
    } catch (error) {
      setOutput("authView", error.message, true);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const login = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.username.value.trim(),
          password: form.password.value,
        }),
      }).then(readJson);
      localStorage.setItem(AUTH_TOKEN_KEY, login.access_token);
      localStorage.setItem(AUTH_USER_KEY, login.username);
      setOutput("authView", `Logged in as ${login.username}`);
      refreshJobs();
      refreshModels();
    } catch (error) {
      setOutput("authView", error.message, true);
    }
  });

  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    setOutput("authView", "Logged out. Demo mode active.");
    refreshJobs();
    refreshModels();
  });

  setLoggedInUser();
}

function bootstrap() {
  initForecastForm();
  initScoreForm();
  initBatchForm();
  initAuthForm();
  initJobsForm();
  initModelForm();
  loadSnapshot();
}

bootstrap();
