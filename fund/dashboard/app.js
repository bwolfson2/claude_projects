const STATE_ORDER = [
  "sourced",
  "screening",
  "first_meeting",
  "watchlist",
  "dataroom_requested",
  "dataroom_received",
  "deep_diligence",
  "ic_prep",
  "term_sheet",
  "closed_invested",
  "closed_passed",
  "portfolio_monitoring",
];

const elements = {
  fundName: document.querySelector("#fund-name"),
  lastUpdated: document.querySelector("#last-updated"),
  companyCount: document.querySelector("#company-count"),
  stageCards: document.querySelector("#stage-cards"),
  pipelineRows: document.querySelector("#pipeline-rows"),
  kanban: document.querySelector("#kanban"),
  detailTitle: document.querySelector("#detail-title"),
  detailBody: document.querySelector("#detail-body"),
  search: document.querySelector("#search"),
  stageFilter: document.querySelector("#stage-filter"),
  postureFilter: document.querySelector("#posture-filter"),
};

const appState = {
  data: null,
  filteredCompanies: [],
  selectedSlug: null,
};

function formatMoney(value) {
  if (!value) return "-";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function stageSort(a, b) {
  return STATE_ORDER.indexOf(a) - STATE_ORDER.indexOf(b);
}

function buildStageCounts(companies) {
  const counts = new Map();
  companies.forEach((company) => {
    counts.set(company.stage, (counts.get(company.stage) || 0) + 1);
  });
  return [...counts.entries()].sort((a, b) => stageSort(a[0], b[0]));
}

function fillFilters(companies) {
  const stages = [...new Set(companies.map((company) => company.stage))].sort(stageSort);
  const postures = [...new Set(companies.map((company) => company.decision_posture))].sort();

  elements.stageFilter.innerHTML = '<option value="">All stages</option>';
  stages.forEach((stage) => {
    const option = document.createElement("option");
    option.value = stage;
    option.textContent = stage;
    elements.stageFilter.appendChild(option);
  });

  elements.postureFilter.innerHTML = '<option value="">All postures</option>';
  postures.forEach((posture) => {
    const option = document.createElement("option");
    option.value = posture;
    option.textContent = posture;
    elements.postureFilter.appendChild(option);
  });
}

function matchesFilters(company) {
  const search = elements.search.value.trim().toLowerCase();
  const stage = elements.stageFilter.value;
  const posture = elements.postureFilter.value;
  const haystack = [
    company.company_name,
    company.sector,
    company.thesis,
    company.next_action,
    company.stage,
    company.decision_posture,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (search && !haystack.includes(search)) return false;
  if (stage && company.stage !== stage) return false;
  if (posture && company.decision_posture !== posture) return false;
  return true;
}

function selectCompany(slug) {
  appState.selectedSlug = slug;
  render();
}

function renderStageCards(companies) {
  const stageCounts = buildStageCounts(companies);
  elements.stageCards.innerHTML = "";

  stageCounts.forEach(([stage, count]) => {
    const card = document.createElement("article");
    card.className = "stage-card";
    card.innerHTML = `
      <span class="pill">${stage.replaceAll("_", " ")}</span>
      <strong class="count">${count}</strong>
    `;
    elements.stageCards.appendChild(card);
  });
}

function renderTable(companies) {
  elements.pipelineRows.innerHTML = "";

  companies
    .slice()
    .sort((a, b) => {
      const dueA = a.next_action_due || "9999-99-99";
      const dueB = b.next_action_due || "9999-99-99";
      return dueA.localeCompare(dueB) || a.company_name.localeCompare(b.company_name);
    })
    .forEach((company) => {
      const row = document.createElement("tr");
      if (company.slug === appState.selectedSlug) row.classList.add("is-selected");
      row.innerHTML = `
        <td><strong>${company.company_name}</strong></td>
        <td>${company.stage}</td>
        <td>${company.decision_posture}</td>
        <td>${formatMoney(company.raise_usd)} @ ${formatMoney(company.valuation_cap_usd)}</td>
        <td>${company.owner || "-"}</td>
        <td>${company.next_action_due || "-"}</td>
        <td>${company.next_action || "-"}</td>
      `;
      row.addEventListener("click", () => selectCompany(company.slug));
      elements.pipelineRows.appendChild(row);
    });
}

function renderKanban(companies) {
  elements.kanban.innerHTML = "";

  const stages = [...new Set(companies.map((company) => company.stage))].sort(stageSort);
  stages.forEach((stage) => {
    const column = document.createElement("section");
    column.className = "kanban-column";
    column.innerHTML = `<h3>${stage.replaceAll("_", " ")}</h3><div class="kanban-stack"></div>`;
    const stack = column.querySelector(".kanban-stack");

    companies
      .filter((company) => company.stage === stage)
      .sort((a, b) => a.company_name.localeCompare(b.company_name))
      .forEach((company) => {
        const card = document.createElement("article");
        card.className = "deal-card";
        if (company.slug === appState.selectedSlug) card.classList.add("is-selected");
        card.innerHTML = `
          <h4>${company.company_name}</h4>
          <p>${company.decision_posture}</p>
          <p>${company.next_action_due || "No due date"}</p>
        `;
        card.addEventListener("click", () => selectCompany(company.slug));
        stack.appendChild(card);
      });

    elements.kanban.appendChild(column);
  });
}

function renderArtifacts(artifacts) {
  const keys = Object.keys(artifacts || {});
  if (!keys.length) return "<p>-</p>";

  return `
    <ul>
      ${keys
        .sort()
        .map((key) => {
          const item = artifacts[key];
          const href = item.repo_relative ? `../../${item.repo_relative}` : null;
          if (href) {
            return `<li><strong>${key}</strong>: <a href="${href}" target="_blank" rel="noreferrer">${item.repo_relative}</a></li>`;
          }
          return `<li><strong>${key}</strong>: ${item.absolute || "-"}</li>`;
        })
        .join("")}
    </ul>
  `;
}

function renderList(items, empty = "-") {
  if (!items || !items.length) return `<p>${empty}</p>`;
  return `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`;
}

function renderDiligence(diligence) {
  if (!diligence) return "<p>-</p>";
  return `
    <div class="diligence-grid">
      ${Object.entries(diligence)
        .map(
          ([key, value]) => `
            <div class="diligence-chip">
              <strong>${key.replaceAll("_", " ")}</strong>
              <span>${value}</span>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderDetails(companies) {
  const selected =
    companies.find((company) => company.slug === appState.selectedSlug) ||
    companies[0] ||
    null;

  if (!selected) {
    elements.detailTitle.textContent = "Select a company";
    elements.detailBody.className = "detail-body empty-state";
    elements.detailBody.textContent =
      "No companies match the current filters.";
    return;
  }

  appState.selectedSlug = selected.slug;
  elements.detailTitle.textContent = selected.company_name;
  elements.detailBody.className = "detail-body";
  elements.detailBody.innerHTML = `
    <div class="detail-grid">
      <section class="detail-block">
        <h3>Snapshot</h3>
        <p><strong>Stage:</strong> ${selected.stage}</p>
        <p><strong>Status:</strong> ${selected.status}</p>
        <p><strong>Posture:</strong> ${selected.decision_posture}</p>
        <p><strong>Owner:</strong> ${selected.owner || "-"}</p>
        <p><strong>Raise:</strong> ${formatMoney(selected.raise_usd)} @ ${formatMoney(selected.valuation_cap_usd)}</p>
        <p><strong>Last touch:</strong> ${selected.last_touch || "-"}</p>
        <p><strong>Due:</strong> ${selected.next_action_due || "-"}</p>
      </section>
      <section class="detail-block">
        <h3>Thesis</h3>
        <p>${selected.thesis || "-"}</p>
      </section>
    </div>
    <section class="detail-block">
      <h3>Next Action</h3>
      <p>${selected.next_action || "-"}</p>
      <p><strong>Owner:</strong> ${selected.next_action_owner || "-"}</p>
    </section>
    <section class="detail-block">
      <h3>Diligence State</h3>
      ${renderDiligence(selected.diligence)}
    </section>
    <div class="detail-grid">
      <section class="detail-block">
        <h3>Assumptions</h3>
        ${renderList(selected.assumptions)}
      </section>
      <section class="detail-block">
        <h3>Open Questions</h3>
        ${renderList(selected.open_questions)}
      </section>
    </div>
    <section class="detail-block">
      <h3>Artifacts</h3>
      ${renderArtifacts(selected.artifacts)}
    </section>
  `;
}

function render() {
  const companies = appState.data.companies.filter(matchesFilters);
  appState.filteredCompanies = companies;

  renderStageCards(companies);
  renderTable(companies);
  renderKanban(companies);
  renderDetails(companies);
}

async function bootstrap() {
  const response = await fetch("./data/deals.json");
  if (!response.ok) {
    throw new Error(`Failed to load dashboard data: ${response.status}`);
  }
  appState.data = await response.json();

  elements.fundName.textContent = appState.data.fund_name;
  elements.lastUpdated.textContent = appState.data.last_updated;
  elements.companyCount.textContent = String(appState.data.companies.length);

  fillFilters(appState.data.companies);
  appState.selectedSlug = appState.data.companies[0]?.slug || null;

  [elements.search, elements.stageFilter, elements.postureFilter].forEach((element) => {
    element.addEventListener("input", render);
    element.addEventListener("change", render);
  });

  render();
}

bootstrap().catch((error) => {
  elements.detailTitle.textContent = "Dashboard error";
  elements.detailBody.className = "detail-body empty-state";
  elements.detailBody.textContent = error.message;
});
