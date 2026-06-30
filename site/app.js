/* MSA fire-segment procurement tracker — renders window.SITE_DATA. */
(function () {
  const D = window.SITE_DATA;
  if (!D) { console.error("SITE_DATA missing"); return; }

  const COL = {
    accent: "#2E5A3C", accent2: "#F4C430", accent3: "#A8C49B",
    blue: "#3a5a78", neg: "#C95D4A", muted: "#b0a98f", grid: "rgba(45,47,37,0.08)",
  };
  const el = (id) => document.getElementById(id);
  const usdC = (n) => {
    const a = Math.abs(n);
    if (a >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
    if (a >= 1e3) return "$" + (n / 1e3).toFixed(0) + "K";
    return "$" + n.toFixed(0);
  };
  const usdF = (n) => "$" + Math.round(n).toLocaleString("en-US");
  const num = (n) => Number(n).toLocaleString("en-US");
  const pct = (n, d) => (d ? (100 * n / d).toFixed(0) + "%" : "0%");

  Chart.defaults.font.family = "'Inter','Segoe UI',system-ui,sans-serif";
  Chart.defaults.color = COL.muted;
  Chart.defaults.font.size = 11;

  el("sub-window").textContent = D.meta.scope + " · refreshed " + D.meta.generated;
  el("foot-date").textContent = D.meta.generated;
  el("src-method").innerHTML = "<strong>Source:</strong> USAspending.gov · Socrata government open-data · "
    + "FEMA AFG · MSA co-op disclosures · refreshed <code>" + D.meta.generated + "</code>";

  const M = D.municipal;
  const FF = D.federal_fire;

  /* ---------- Overview hero ---------- */
  el("hero").innerHTML = [
    { l: "MSA channel reach", v: M.msa_jurisdictions + " of " + M.total_jurisdictions, s: "US jurisdictions with MSA fire activity" },
    { l: "Where MSA channel leads", v: M.msa_wins_jurisdictions + " of " + M.active_jurisdictions, s: "jurisdictions: MSA channel > competitors" },
    { l: "Fire transactions (MSA channel)", v: num(M.msa_txns), s: "vs " + num(M.competitor_txns) + " competitor — see caveat" },
    { l: "Federal fire (supporting)", v: usdC(FF.total_dollars), s: FF.total_awards + " prime awards · fire only" },
  ].map((t) => `<div class="hero-tile"><div class="hero-label">${t.l}</div>
      <div class="hero-val" style="font-size:${String(t.v).length > 9 ? "22px" : "30px"}">${t.v}</div>
      <div class="hero-sub">${t.s}</div></div>`).join("");

  /* ---------- 01 Municipal ---------- */
  el("mu-msa").textContent = num(M.msa_txns);
  el("mu-msa-sub").textContent = "MSA direct + dealers · " + M.msa_jurisdictions + " jurisdictions";
  el("mu-comp").textContent = num(M.competitor_txns);
  el("mu-comp-sub").textContent = "Scott / Dräger / LION / etc. · " + M.competitor_jurisdictions + " jurisdictions";
  el("mu-floor").textContent = usdC(M.msa_direct_floor_usd);
  if (el("mu-top3")) el("mu-top3").textContent = M.top3_share_pct + "%";

  const CLASS_COL = {
    "Via MSA fire dealer": COL.accent, "MSA direct": COL.blue,
    "MSA product spec'd": COL.accent3, "Competitor": COL.neg, "Fire — unattributed": COL.muted,
  };
  const bc = M.by_class;
  new Chart(el("muClassChart"), {
    type: "bar",
    data: {
      labels: bc.map((x) => x.class),
      datasets: [{ data: bc.map((x) => x.count), backgroundColor: bc.map((x) => CLASS_COL[x.class] || COL.muted), borderRadius: 4 }],
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => num(c.parsed.x) + " transactions" } } },
      scales: { x: { grid: { color: COL.grid }, ticks: { precision: 0 } }, y: { grid: { display: false }, ticks: { font: { size: 10 } } } },
    },
  });

  const dl = M.top_dealers;
  new Chart(el("dealerChart"), {
    type: "bar",
    data: {
      labels: dl.map((x) => x.name),
      datasets: [{ data: dl.map((x) => x.count), backgroundColor: COL.accent, borderRadius: 4 }],
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => num(c.parsed.x) + " txns · " + dl[c.dataIndex].jurisdictions + " jurisdictions" } } },
      scales: { x: { grid: { color: COL.grid }, ticks: { precision: 0 } }, y: { grid: { display: false }, ticks: { font: { size: 10 } } } },
    },
  });

  el("take-mu").innerHTML =
    `Read this by <strong>breadth, not raw volume</strong>: across the ${M.active_jurisdictions} jurisdictions with ` +
    `visible fire activity, MSA's channel <strong>out-transacts every competitor combined in ${M.msa_wins_jurisdictions} of them</strong>, ` +
    `and appears in <strong>${M.msa_jurisdictions} of ${M.total_jurisdictions}</strong> (competitors in ${M.competitor_jurisdictions}). ` +
    `The dealer network (Witmer, MES, Casco, Vogelpohl, Ten-8…) is the visible spine of how cities and counties actually ` +
    `buy MSA fire gear — demand the federal data misses entirely. The raw count (${num(M.msa_txns)} vs ${num(M.competitor_txns)}) ` +
    `points the same way but is concentrated — see the caveat below.`;
  el("src-mu").innerHTML = `<strong>Source:</strong> ${M.source} · fire-product + vendor match · ` +
    `${num(M.total_rows)} attributed rows · refreshed <code>${D.meta.generated}</code>`;

  const lvlBadge = (l) => `<span class="badge b-${l}">${l}</span>`;
  el("muJurisTable").querySelector("tbody").innerHTML = M.by_jurisdiction.slice(0, 20).map((j) => `
    <tr><td>${j.jurisdiction}</td><td>${lvlBadge(j.level)}</td>
    <td class="num">${num(j.msa)}</td><td class="num">${num(j.comp)}</td></tr>`).join("");

  /* ---------- 02 Co-op ---------- */
  el("coopTable").querySelector("tbody").innerHTML = D.coop.map((c) => {
    const direct = c.type.startsWith("Direct");
    return `<tr><td><strong>${c.coop}</strong></td>
      <td><span class="badge ${direct ? "b-direct" : "b-indirect"}">${c.type}</span></td>
      <td><code style="font-size:11px">${c.contract}</code></td><td>${c.products}</td></tr>`;
  }).join("");

  /* ---------- 03 Platforms ---------- */
  el("platformTable").querySelector("tbody").innerHTML = D.platforms.map((p) => {
    const blocked = /blocked|bans|disallow|waf|captcha/i.test(p.mine);
    return `<tr><td><strong>${p.name}</strong></td><td>${p.network}</td><td>${p.awards}</td>
      <td><span class="badge ${blocked ? "b-blocked" : "b-ok"}">${p.mine}</span></td></tr>`;
  }).join("");

  /* ---------- 04 Federal fire ---------- */
  const agencies = FF.by_agency.length;
  el("ff-hero").innerHTML = [
    { l: "Federal fire awards", v: usdC(FF.total_dollars), s: FF.total_awards + " prime contracts" },
    { l: "Awarding agencies", v: String(agencies), s: "DoD, DHS, HHS, …" },
    { l: "Top buyer", v: FF.by_agency[0] ? FF.by_agency[0].agency.replace("Department of ", "") : "—", s: FF.by_agency[0] ? usdC(FF.by_agency[0].amount) : "" },
    { l: "Peak year", v: peakYear(FF.by_year), s: "SCBA delivery surge" },
  ].map((t) => `<div class="hero-tile"><div class="hero-label">${t.l}</div>
      <div class="hero-val" style="font-size:${String(t.v).length > 9 ? "22px" : "30px"}">${t.v}</div>
      <div class="hero-sub">${t.s}</div></div>`).join("");

  const fy = FF.by_year.filter((y) => Number(y.year) >= 2021);
  new Chart(el("ffYearChart"), {
    type: "bar",
    data: { labels: fy.map((y) => y.year), datasets: [{ data: fy.map((y) => y.amount), backgroundColor: COL.accent, borderRadius: 4 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => usdF(c.parsed.y) + " · " + fy[c.dataIndex].count + " awards" } } },
      scales: { y: { grid: { color: COL.grid }, ticks: { callback: (v) => usdC(v) } }, x: { grid: { display: false } } },
    },
  });
  const f24 = (fy.find((y) => y.year === "2024") || {}).amount || 0;
  const f25 = (fy.find((y) => y.year === "2025") || {}).amount || 0;
  el("take-ffyear").innerHTML =
    `Even in the small federal slice the <strong>SCBA replacement cycle is visible</strong>: fire dollars ` +
    `ramp to <strong>${usdC(f24)} in 2024</strong>, then drop to <strong>${usdC(f25)} in 2025</strong> as ` +
    `departments paused ahead of the 2026 NFPA standard (MSA's Americas fire revenue fell ~12% the same year). ` +
    `The 2014–2018 G1 cohort comes due for replacement in 2027–2029 — the catalyst this whole page is evidence for. ` +
    `(Federal value is lumpy: one or two large DoD/Coast Guard delivery orders drive each year.)`;
  el("src-ffyear").innerHTML = `<strong>Source:</strong> USAspending.gov · fire-segment awards by year · refreshed <code>${D.meta.generated}</code>`;

  const cv = FF.competition.competed_vs_not;
  el("ff-won").textContent = usdC(cv.competed.amount);
  el("ff-won-sub").textContent = cv.competed.count + " awards won in open competition";
  el("ff-sole").textContent = usdC(cv.not_competed.amount);
  el("ff-sole-sub").textContent = cv.not_competed.count + " awards sole-source (brand-locked)";

  el("ffContractsTable").querySelector("tbody").innerHTML = FF.top_contracts.map((c) => `
    <tr><td><a href="${c.url}" target="_blank" rel="noopener">${c.award_id || "—"}</a></td>
    <td>${c.agency}${c.sub_agency ? " · " + c.sub_agency : ""}</td>
    <td class="num">${usdF(c.amount)}</td><td class="num">${c.start_date || "—"}</td>
    <td>${(c.description || "").replace(/</g, "&lt;")}</td></tr>`).join("");
  el("src-ff").innerHTML = `<strong>Source:</strong> USAspending.gov · fire-segment prime awards · ` +
    `competition fields from FPDS · refreshed <code>${D.meta.generated}</code>`;

  /* ---------- 05 AFG ---------- */
  if (D.afg && D.afg.by_year) {
    const ay = D.afg.by_year.filter((y) => Number(y.fiscal_year) >= 2021 && y.amount > 0);
    new Chart(el("afgChart"), {
      type: "bar",
      data: { labels: ay.map((y) => "FY" + y.fiscal_year), datasets: [{ data: ay.map((y) => y.amount), backgroundColor: COL.neg, borderRadius: 4 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => usdF(c.parsed.y) } } },
        scales: { y: { grid: { color: COL.grid }, ticks: { callback: (v) => usdC(v) } }, x: { grid: { display: false } } },
      },
    });
    const avg = ay.reduce((s, y) => s + y.amount, 0) / (ay.length || 1);
    el("take-afg").innerHTML =
      `National AFG funding runs <strong>~${usdC(avg)} per year</strong> of federal money flowing to fire ` +
      `departments for equipment, with SCBA among the largest eligible categories. With a new NFPA SCBA standard ` +
      `in 2026 and the record 2014–2018 G1 cohort hitting replacement in 2027–2029, this is the funded demand ` +
      `MSA's municipal channel is positioned to capture.`;
    el("src-afg").innerHTML = `<strong>Source:</strong> ${D.afg.meta.source} · Assistance Listing ${D.afg.meta.program} · refreshed <code>${D.afg.meta.generated}</code>`;
  }

  function peakYear(byYear) {
    const f = byYear.filter((y) => Number(y.year) >= 2021);
    if (!f.length) return "—";
    return f.reduce((a, b) => (b.amount > a.amount ? b : a), f[0]).year;
  }
})();
