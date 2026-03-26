const projectList = document.querySelector("#project-list");
const statusBanner = document.querySelector("#status-banner");
const regionReference = document.querySelector("#region-reference");
const analysisOutput = document.querySelector("#analysis-output");
const memoOutput = document.querySelector("#memo-output");

const projectName = document.querySelector("#project-name");
const projectSubtitle = document.querySelector("#project-subtitle");
const projectNotes = document.querySelector("#project-notes");
const metricSites = document.querySelector("#metric-sites");
const metricStatus = document.querySelector("#metric-status");
const metricCod = document.querySelector("#metric-cod");
const metricTopPick = document.querySelector("#metric-top-pick");

const projectForm = document.querySelector("#project-form");
const siteForm = document.querySelector("#site-form");
const siteList = document.querySelector("#site-list");
const runAnalysisButton = document.querySelector("#run-analysis");
const deleteProjectButton = document.querySelector("#delete-project");
const refreshWorkspaceButton = document.querySelector("#refresh-workspace");
const loadDemoButton = document.querySelector("#load-demo");
const logoutButton = document.querySelector("#logout");
const exportProjectButton = document.querySelector("#export-project");
const downloadRankingsButton = document.querySelector("#download-rankings");
const downloadMemoButton = document.querySelector("#download-memo");
const downloadTemplateButton = document.querySelector("#download-template");
const importSitesButton = document.querySelector("#import-sites");
const siteImportFile = document.querySelector("#site-import-file");

const state = {
  projectSummaries: [],
  selectedProject: null,
  regionProfiles: [],
};

function formatErrorDetail(detail) {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.join("; ");
  }
  if (detail && Array.isArray(detail.errors)) {
    return detail.errors.join(" | ");
  }
  return "Request failed";
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (response.status === 401) {
    window.location.assign("/login?next=%2F");
    throw new Error("Authentication required");
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null ? payload.detail || "Request failed" : payload;
    throw new Error(formatErrorDetail(detail));
  }

  return payload;
}

function setStatus(message, tone = "info") {
  statusBanner.textContent = message;
  statusBanner.dataset.tone = tone;
}

function formatDate(isoString) {
  if (!isoString) {
    return "No analysis yet";
  }
  return new Date(isoString).toLocaleString();
}

function renderProjects() {
  if (!state.projectSummaries.length) {
    projectList.className = "project-list empty-state";
    projectList.textContent = "No saved projects yet. Create one or load the demo data.";
    return;
  }

  projectList.className = "project-list";
  projectList.innerHTML = state.projectSummaries
    .map(
      (project) => `
        <button class="project-card ${state.selectedProject && state.selectedProject.id === project.id ? "selected" : ""}" data-project-id="${project.id}">
          <span class="pill">${project.status}</span>
          <strong>${project.name}</strong>
          <span class="muted-text">${project.developer}</span>
          <span class="muted-text">${project.site_count} site(s) - COD ${project.target_cod_year}</span>
          <span class="muted-text">Last analysis: ${formatDate(project.latest_analysis_at)}</span>
        </button>
      `
    )
    .join("");

  projectList.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      await loadProject(button.dataset.projectId);
    });
  });
}

function setSiteFormEnabled(enabled) {
  siteForm.classList.toggle("disabled-stack", !enabled);
  siteForm.querySelectorAll("input, select, textarea, button").forEach((field) => {
    field.disabled = !enabled;
  });
  importSitesButton.disabled = !enabled;
  siteImportFile.disabled = !enabled;
}

function renderSelectedProject() {
  const project = state.selectedProject;
  if (!project) {
    projectName.textContent = "No project selected";
    projectSubtitle.textContent = "Create a project or load demo data to start working.";
    projectNotes.textContent = "Project notes will appear here.";
    metricSites.textContent = "0";
    metricStatus.textContent = "Draft";
    metricCod.textContent = "-";
    metricTopPick.textContent = "-";
    siteList.className = "site-list empty-state";
    siteList.textContent = "Add a project first, then attach candidate sites here.";
    analysisOutput.className = "empty-state";
    analysisOutput.textContent = "Run an analysis after you add sites to generate a ranked portfolio.";
    memoOutput.textContent = "No analysis memo yet.";
    runAnalysisButton.disabled = true;
    deleteProjectButton.disabled = true;
    exportProjectButton.disabled = true;
    downloadRankingsButton.disabled = true;
    downloadMemoButton.disabled = true;
    setSiteFormEnabled(false);
    return;
  }

  const latestAnalysis = project.analysis_runs[0] || null;
  const resultLookup = new Map((latestAnalysis?.results || []).map((result) => [result.site_id, result]));

  projectName.textContent = project.name;
  projectSubtitle.textContent = `${project.developer} - ${project.technology_focus.replaceAll("_", " ")} focus`;
  projectNotes.textContent = project.notes || "No project notes captured yet.";
  metricSites.textContent = String(project.sites.length);
  metricStatus.textContent = project.status;
  metricCod.textContent = String(project.target_cod_year);
  metricTopPick.textContent = latestAnalysis?.top_pick_site_name || "-";
  runAnalysisButton.disabled = project.sites.length === 0;
  deleteProjectButton.disabled = false;
  exportProjectButton.disabled = false;
  downloadRankingsButton.disabled = !latestAnalysis;
  downloadMemoButton.disabled = !latestAnalysis;
  setSiteFormEnabled(true);

  if (!project.sites.length) {
    siteList.className = "site-list empty-state";
    siteList.textContent = "This project has no sites yet. Add one to start screening.";
  } else {
    siteList.className = "site-list";
    siteList.innerHTML = project.sites
      .map((site) => {
        const result = resultLookup.get(site.id);
        return `
          <article class="site-result-card">
            <div class="site-result-header">
              <div>
                <strong>${site.name}</strong>
                <p class="muted-text">${site.region} - ${site.state} - ${site.technology.replaceAll("_", " ")}</p>
              </div>
              <button class="ghost danger small" data-delete-site="${site.id}">Delete</button>
            </div>
            <p class="muted-text">Queue: ${site.queue_wait_months} months - Upgrade cost: $${site.estimated_upgrade_cost_musd}M - Substation distance: ${site.distance_to_substation_km} km</p>
            ${
              result
                ? `<div class="result-chip-row">
                     <span class="pill">Rank ${result.rank}</span>
                     <span class="pill">${result.readiness_tier}</span>
                     <span class="pill">Score ${result.overall_score}</span>
                   </div>
                   <p class="muted-text">${result.risk_flags[0] || "No material gating risk captured in latest run."}</p>`
                : `<p class="muted-text">No saved score yet. Run analysis to generate ranked results.</p>`
            }
          </article>
        `;
      })
      .join("");

    siteList.querySelectorAll("[data-delete-site]").forEach((button) => {
      button.addEventListener("click", async () => {
        const confirmed = window.confirm("Delete this site from the project?");
        if (!confirmed) return;
        await apiRequest(`/api/projects/${project.id}/sites/${button.dataset.deleteSite}`, { method: "DELETE" });
        setStatus("Site removed.", "success");
        await refreshProjects(project.id);
      });
    });
  }

  if (!latestAnalysis) {
    analysisOutput.className = "empty-state";
    analysisOutput.textContent = "No analysis has been saved yet. Run a portfolio analysis when your sites are ready.";
    memoOutput.textContent = "No analysis memo yet.";
  } else {
    analysisOutput.className = "analysis-grid";
    analysisOutput.innerHTML = `
      <article class="analysis-summary-card">
        <p class="muted-text">Latest run: ${formatDate(latestAnalysis.created_at)}</p>
        <strong>${latestAnalysis.top_pick_site_name || "No top pick"}</strong>
        <p>${latestAnalysis.executive_summary}</p>
        <p class="muted-text">${latestAnalysis.portfolio_recommendation}</p>
      </article>
      ${latestAnalysis.results
        .map(
          (result) => `
            <article class="analysis-rank-card">
              <span class="pill">Rank ${result.rank}</span>
              <strong>${result.site_name}</strong>
              <p class="muted-text">Score ${result.overall_score} - ${result.readiness_tier}</p>
              <p class="muted-text">${result.next_actions[0] || "Advance into deeper diligence."}</p>
            </article>
          `
        )
        .join("")}
    `;
    memoOutput.textContent = latestAnalysis.memo_markdown;
  }
}

function renderRegionProfiles() {
  if (!state.regionProfiles.length) {
    regionReference.className = "region-grid empty-state";
    regionReference.textContent = "No regional data loaded yet.";
    return;
  }

  regionReference.className = "region-grid";
  regionReference.innerHTML = state.regionProfiles
    .map(
      (region) => `
        <article class="region-card">
          <span class="pill">${region.region}</span>
          <strong>${region.typical_queue_months} month baseline queue</strong>
          <p class="muted-text">Typical upgrade cost: $${region.typical_upgrade_cost_musd}M</p>
          <p class="muted-text">Permitting friction index: ${region.permitting_friction}/100</p>
        </article>
      `
    )
    .join("");
}

async function refreshProjects(selectedId = state.selectedProject?.id) {
  state.projectSummaries = await apiRequest("/api/projects");
  renderProjects();

  const targetId =
    (selectedId && state.projectSummaries.find((project) => project.id === selectedId)?.id) ||
    state.projectSummaries[0]?.id ||
    null;

  if (!targetId) {
    state.selectedProject = null;
    renderSelectedProject();
    return;
  }

  await loadProject(targetId, false);
}

async function loadProject(projectId, rerenderProjects = true) {
  state.selectedProject = await apiRequest(`/api/projects/${projectId}`);
  if (rerenderProjects) {
    renderProjects();
  }
  renderSelectedProject();
}

async function loadRegionProfiles() {
  const response = await apiRequest("/api/reference/regions");
  state.regionProfiles = response.regions;
  renderRegionProfiles();
}

async function loadDemoProject() {
  setStatus("Creating demo project...", "info");
  const project = await apiRequest("/api/projects", {
    method: "POST",
    body: JSON.stringify({
      name: "Southwest Screening Portfolio",
      developer: "Prairie Grid Partners",
      status: "screening",
      technology_focus: "solar_storage",
      target_cod_year: 2029,
      notes: "Production-demo project focused on ERCOT and MISO screening for near-term capital deployment.",
    }),
  });

  const demoSites = [
    {
      name: "West Texas Pivot",
      region: "ERCOT",
      state: "TX",
      technology: "solar_storage",
      acreage: 560,
      distance_to_substation_km: 2.2,
      queue_wait_months: 14,
      estimated_upgrade_cost_musd: 7.5,
      transmission_voltage_kv: 138,
      environmental_sensitivity: 16,
      community_support: 84,
      permitting_complexity: "low",
      site_control: "secured",
      land_use_conflict: "low",
      notes: "Fast first-pass screen with strong community posture.",
    },
    {
      name: "Central Illinois Buildout",
      region: "MISO",
      state: "IL",
      technology: "solar",
      acreage: 470,
      distance_to_substation_km: 5.8,
      queue_wait_months: 32,
      estimated_upgrade_cost_musd: 18,
      transmission_voltage_kv: 115,
      environmental_sensitivity: 28,
      community_support: 69,
      permitting_complexity: "medium",
      site_control: "optioned",
      land_use_conflict: "medium",
      notes: "Useful backup site with moderate permitting friction.",
    },
  ];

  for (const site of demoSites) {
    await apiRequest(`/api/projects/${project.id}/sites`, {
      method: "POST",
      body: JSON.stringify(site),
    });
  }

  await refreshProjects(project.id);
  setStatus("Demo project loaded.", "success");
}

projectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(projectForm);
  const payload = Object.fromEntries(formData.entries());
  payload.target_cod_year = Number(payload.target_cod_year);

  try {
    const project = await apiRequest("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    projectForm.reset();
    projectForm.querySelector("[name='target_cod_year']").value = "2029";
    setStatus("Project created.", "success");
    await refreshProjects(project.id);
  } catch (error) {
    setStatus(error.message, "error");
  }
});

siteForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.selectedProject) {
    setStatus("Select a project before adding sites.", "error");
    return;
  }

  const formData = new FormData(siteForm);
  const payload = Object.fromEntries(formData.entries());
  [
    "acreage",
    "distance_to_substation_km",
    "queue_wait_months",
    "estimated_upgrade_cost_musd",
    "transmission_voltage_kv",
    "environmental_sensitivity",
    "community_support",
  ].forEach((key) => {
    payload[key] = Number(payload[key]);
  });

  try {
    await apiRequest(`/api/projects/${state.selectedProject.id}/sites`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    siteForm.reset();
    siteForm.querySelector("[name='state']").value = "TX";
    siteForm.querySelector("[name='acreage']").value = "550";
    siteForm.querySelector("[name='distance_to_substation_km']").value = "3.0";
    siteForm.querySelector("[name='queue_wait_months']").value = "18";
    siteForm.querySelector("[name='estimated_upgrade_cost_musd']").value = "12.0";
    siteForm.querySelector("[name='transmission_voltage_kv']").value = "138";
    siteForm.querySelector("[name='environmental_sensitivity']").value = "20";
    siteForm.querySelector("[name='community_support']").value = "75";
    setStatus("Site added.", "success");
    await refreshProjects(state.selectedProject.id);
  } catch (error) {
    setStatus(error.message, "error");
  }
});

runAnalysisButton.addEventListener("click", async () => {
  if (!state.selectedProject) return;
  try {
    setStatus("Running portfolio analysis...", "info");
    await apiRequest(`/api/projects/${state.selectedProject.id}/analysis`, { method: "POST" });
    await refreshProjects(state.selectedProject.id);
    setStatus("Analysis complete.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
});

deleteProjectButton.addEventListener("click", async () => {
  if (!state.selectedProject) return;
  const confirmed = window.confirm(`Delete project "${state.selectedProject.name}"?`);
  if (!confirmed) return;

  try {
    await apiRequest(`/api/projects/${state.selectedProject.id}`, { method: "DELETE" });
    state.selectedProject = null;
    await refreshProjects();
    setStatus("Project deleted.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
});

refreshWorkspaceButton.addEventListener("click", async () => {
  setStatus("Refreshing workspace...", "info");
  await refreshProjects();
  await loadRegionProfiles();
  setStatus("Workspace refreshed.", "success");
});

loadDemoButton.addEventListener("click", async () => {
  try {
    await loadDemoProject();
  } catch (error) {
    setStatus(error.message, "error");
  }
});

if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    try {
      await apiRequest("/api/session/logout", { method: "POST" });
      window.location.assign("/login");
    } catch (error) {
      setStatus(error.message, "error");
    }
  });
}

exportProjectButton.addEventListener("click", () => {
  if (!state.selectedProject) return;
  window.location.assign(`/api/projects/${state.selectedProject.id}/export`);
});

downloadRankingsButton.addEventListener("click", () => {
  if (!state.selectedProject) return;
  window.location.assign(`/api/projects/${state.selectedProject.id}/analysis/latest.csv`);
});

downloadMemoButton.addEventListener("click", () => {
  if (!state.selectedProject) return;
  window.location.assign(`/api/projects/${state.selectedProject.id}/analysis/latest.md`);
});

downloadTemplateButton.addEventListener("click", () => {
  window.location.assign("/api/reference/site-template.csv");
});

importSitesButton.addEventListener("click", async () => {
  if (!state.selectedProject) {
    setStatus("Select a project before importing sites.", "error");
    return;
  }

  const file = siteImportFile.files[0];
  if (!file) {
    setStatus("Choose a CSV file before importing.", "error");
    return;
  }

  try {
    setStatus("Importing site pipeline...", "info");
    const csvContent = await file.text();
    const result = await apiRequest(`/api/projects/${state.selectedProject.id}/sites/import-csv`, {
      method: "POST",
      body: JSON.stringify({ csv_content: csvContent }),
    });
    siteImportFile.value = "";
    await refreshProjects(state.selectedProject.id);
    setStatus(`Imported ${result.created_count} site(s).`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
});

async function bootstrap() {
  try {
    await Promise.all([refreshProjects(), loadRegionProfiles()]);
    setStatus("Workspace ready.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

bootstrap();
