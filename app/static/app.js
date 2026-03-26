const siteGrid = document.querySelector("#site-grid");
const comparisonOutput = document.querySelector("#comparison-output");
const memoOutput = document.querySelector("#memo-output");
const template = document.querySelector("#site-card-template");
const addSiteButton = document.querySelector("#add-site");
const sampleButton = document.querySelector("#load-sample");
const memoButton = document.querySelector("#generate-memo");

function buildCard(defaults = {}) {
  const fragment = template.content.cloneNode(true);
  const card = fragment.querySelector(".site-card");
  const title = fragment.querySelector(".site-title");

  fragment.querySelectorAll("[data-field]").forEach((field) => {
    const key = field.dataset.field;
    if (defaults[key] !== undefined) {
      field.value = defaults[key];
    }

    field.addEventListener("input", () => {
      if (key === "name") {
        title.textContent = field.value || "Candidate Site";
      }
    });
  });

  fragment.querySelector(".remove-site").addEventListener("click", () => {
    card.remove();
  });

  siteGrid.appendChild(fragment);
}

function collectSites() {
  return [...siteGrid.querySelectorAll(".site-card")].map((card) => {
    const site = {};
    card.querySelectorAll("[data-field]").forEach((field) => {
      const key = field.dataset.field;
      const value = field.value;
      if (field.type === "number") {
        site[key] = Number(value);
      } else {
        site[key] = value;
      }
    });
    return site;
  });
}

async function compareSites() {
  const sites = collectSites();
  if (sites.length < 2) {
    comparisonOutput.textContent = "Add at least two sites before comparing.";
    return null;
  }

  const response = await fetch("/api/sites/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      portfolio_name: "Screening slate",
      sites,
    }),
  });
  const data = await response.json();

  comparisonOutput.innerHTML = data.rankings
    .map(
      (item) => `
        <article class="comparison-card">
          <div class="pill">Rank ${item.rank}</div>
          <strong>${item.site_name}</strong>
          <p>Score: ${item.overall_score} | Tier: ${item.readiness_tier}</p>
          <p>${item.risk_flags[0] || "Low immediate gating risk in first-pass screening."}</p>
        </article>
      `
    )
    .join("");

  return { sites, data };
}

async function generateMemo() {
  const comparison = await compareSites();
  if (!comparison) {
    return;
  }

  const response = await fetch("/api/reports/interconnection-memo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_name: "Developer screening portfolio",
      target_cod_year: 2029,
      sites: comparison.sites,
    }),
  });
  const data = await response.json();
  memoOutput.textContent = data.memo_markdown;
}

function loadSamples() {
  siteGrid.innerHTML = "";
  buildCard({
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
  });
  buildCard({
    name: "Central Illinois Buildout",
    region: "MISO",
    state: "IL",
    technology: "solar",
    acreage: 470,
    distance_to_substation_km: 5.8,
    queue_wait_months: 32,
    estimated_upgrade_cost_musd: 18.0,
    transmission_voltage_kv: 115,
    environmental_sensitivity: 28,
    community_support: 69,
    permitting_complexity: "medium",
    site_control: "optioned",
    land_use_conflict: "medium",
  });
}

addSiteButton.addEventListener("click", () => buildCard());
sampleButton.addEventListener("click", loadSamples);
memoButton.addEventListener("click", generateMemo);

loadSamples();
