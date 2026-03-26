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
const currentUserBadge = document.querySelector("#current-user-badge");
const currentRoleText = document.querySelector("#current-role-text");
const adminPanel = document.querySelector("#admin-panel");
const adminStatus = document.querySelector("#admin-status");
const userForm = document.querySelector("#user-form");
const userList = document.querySelector("#user-list");
const activityList = document.querySelector("#activity-list");
const pageDataset = document.body.dataset;

const state = {
  projectSummaries: [],
  selectedProject: null,
  regionProfiles: [],
  users: [],
  activity: [],
  session: {
    authRequired: pageDataset.authRequired === "true",
    canWrite: pageDataset.canWrite === "true",
    canManageUsers: pageDataset.canManageUsers === "true",
    csrfToken: pageDataset.csrfToken || "",
    username: pageDataset.currentUser || "",
    role: pageDataset.currentRole || "",
  },
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
  const method = (options.method || "GET").toUpperCase();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && state.session.csrfToken) {
    headers["X-CSRF-Token"] = state.session.csrfToken;
  }

  const response = await fetch(url, {
    headers,
    ...options,
  });

  if (response.status === 401) {
    window.location.assign("/login?next=%2F");
    throw new Error("Authentication required");
  }
  if (response.status === 403) {
    const payload = await response.json().catch(() => ({ detail: "Access denied" }));
    throw new Error(payload.detail || "Access denied");
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

function formatRelativeDate(isoString) {
  if (!isoString) {
    return "Unknown";
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

function applySessionState() {
  const label = state.session.username || "Open workspace";
  const roleDescription = state.session.authRequired
    ? `Signed in as ${state.session.role || "user"}.`
    : "Local workspace mode.";

  currentUserBadge.textContent = label;
  currentRoleText.textContent = roleDescription;
  loadDemoButton.disabled = !state.session.canWrite;
  projectForm.querySelectorAll("input, select, textarea, button").forEach((field) => {
    field.disabled = !state.session.canWrite;
  });
  projectForm.classList.toggle("disabled-stack", !state.session.canWrite);

  if (adminPanel) {
    adminPanel.hidden = !state.session.canManageUsers;
  }
  if (userForm) {
    userForm.querySelectorAll("input, select, button").forEach((field) => {
      field.disabled = !state.session.canManageUsers;
    });
  }
  if (adminStatus) {
    adminStatus.textContent = state.session.canManageUsers
      ? "Create analysts, viewers, and additional admins for this workspace."
      : "Admin access is required to manage workspace users.";
  }
}

function setSiteFormEnabled(enabled) {
  const isEnabled = enabled && state.session.canWrite;
  siteForm.classList.toggle("disabled-stack", !isEnabled);
  siteForm.querySelectorAll("input, select, textarea, button").forEach((field) => {
    field.disabled = !isEnabled;
  });
  importSitesButton.disabled = !isEnabled;
  siteImportFile.disabled = !isEnabled;
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
  runAnalysisButton.disabled = project.sites.length === 0 || !state.session.canWrite;
  deleteProjectButton.disabled = !state.session.canWrite;
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
              ${state.session.canWrite ? `<button class="ghost danger small" data-delete-site="${site.id}">Delete</button>` : ""}
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

function renderUsers() {
  if (!state.session.canManageUsers) {
    return;
  }
  if (!state.users.length) {
    userList.className = "site-list empty-state";
    userList.textContent = "No workspace users loaded yet.";
    return;
  }

  userList.className = "site-list";
  userList.innerHTML = state.users
    .map(
      (user) => `
        <article class="site-result-card">
          <div class="site-result-header">
            <div>
              <strong>${user.full_name || user.username}</strong>
              <p class="muted-text">${user.username} - ${user.role} - ${user.is_active ? "active" : "inactive"}</p>
            </div>
            <span class="pill">${user.role}</span>
          </div>
          <p class="muted-text">Last login: ${formatRelativeDate(user.last_login_at)} - Locked until: ${user.locked_until ? formatRelativeDate(user.locked_until) : "Not locked"}</p>
          <div class="field-row">
            <label>
              Role
              <select data-user-role="${user.id}">
                <option value="admin" ${user.role === "admin" ? "selected" : ""}>Admin</option>
                <option value="analyst" ${user.role === "analyst" ? "selected" : ""}>Analyst</option>
                <option value="viewer" ${user.role === "viewer" ? "selected" : ""}>Viewer</option>
              </select>
            </label>
            <label>
              Active
              <select data-user-active="${user.id}">
                <option value="true" ${user.is_active ? "selected" : ""}>Active</option>
                <option value="false" ${!user.is_active ? "selected" : ""}>Inactive</option>
              </select>
            </label>
          </div>
          <div class="project-actions">
            <button class="ghost small" type="button" data-user-save="${user.id}">Save access</button>
            <button class="ghost small" type="button" data-user-reset="${user.id}">Reset password</button>
          </div>
        </article>
      `
    )
    .join("");

  userList.querySelectorAll("[data-user-save]").forEach((button) => {
    button.addEventListener("click", async () => {
      const userId = button.dataset.userSave;
      const role = userList.querySelector(`[data-user-role="${userId}"]`).value;
      const isActive = userList.querySelector(`[data-user-active="${userId}"]`).value === "true";
      try {
        await apiRequest(`/api/admin/users/${userId}`, {
          method: "PATCH",
          body: JSON.stringify({ role, is_active: isActive }),
        });
        await Promise.all([loadUsers(), loadActivity()]);
        setStatus("User access updated.", "success");
      } catch (error) {
        setStatus(error.message, "error");
      }
    });
  });

  userList.querySelectorAll("[data-user-reset]").forEach((button) => {
    button.addEventListener("click", async () => {
      const userId = button.dataset.userReset;
      const newPassword = window.prompt("Enter a new password for this user (minimum 8 characters).");
      if (!newPassword) {
        return;
      }
      try {
        await apiRequest(`/api/admin/users/${userId}`, {
          method: "PATCH",
          body: JSON.stringify({ password: newPassword }),
        });
        await Promise.all([loadUsers(), loadActivity()]);
        setStatus("User password reset.", "success");
      } catch (error) {
        setStatus(error.message, "error");
      }
    });
  });
}

function renderActivity() {
  if (!state.activity.length) {
    activityList.className = "site-list empty-state";
    activityList.textContent = "No recent activity recorded yet.";
    return;
  }

  activityList.className = "site-list";
  activityList.innerHTML = state.activity
    .map(
      (event) => `
        <article class="site-result-card">
          <div class="site-result-header">
            <div>
              <strong>${event.description}</strong>
              <p class="muted-text">${event.actor_username} - ${event.action}</p>
            </div>
            <span class="pill">${formatRelativeDate(event.created_at)}</span>
          </div>
          <p class="muted-text">${event.entity_type}${event.project_id ? ` - Project ${event.project_id}` : ""}</p>
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

async function loadUsers() {
  if (!state.session.canManageUsers) {
    state.users = [];
    return;
  }
  state.users = await apiRequest("/api/admin/users");
  renderUsers();
}

async function loadActivity() {
  state.activity = await apiRequest("/api/activity");
  renderActivity();
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
  await Promise.all([refreshProjects(), loadRegionProfiles(), loadActivity(), loadUsers()]);
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

if (userForm) {
  userForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.session.canManageUsers) {
      setStatus("Admin access is required to create users.", "error");
      return;
    }

    const formData = new FormData(userForm);
    const payload = Object.fromEntries(formData.entries());
    try {
      await apiRequest("/api/admin/users", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      userForm.reset();
      userForm.querySelector("[name='role']").value = "analyst";
      await Promise.all([loadUsers(), loadActivity()]);
      setStatus("Workspace user created.", "success");
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
    applySessionState();
    await Promise.all([refreshProjects(), loadRegionProfiles(), loadActivity(), loadUsers()]);
    if (!state.session.canWrite) {
      setStatus("Workspace ready in read-only mode.", "info");
      return;
    }
    setStatus("Workspace ready.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

bootstrap();
