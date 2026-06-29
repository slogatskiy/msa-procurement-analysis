/* MSA federal procurement tracker — renders window.SITE_DATA into the page. */
(function () {
  const D = window.SITE_DATA;
  if (!D) { console.error("SITE_DATA missing"); return; }

  const COL = {
    accent: "#2E5A3C", accent2: "#F4C430", accent3: "#A8C49B",
    blue: "#3a5a78", neg: "#C95D4A", indus: "#caa53a", other: "#b0a98f",
    text: "#2b2f25", muted: "#8b8b78", grid: "rgba(45,47,37,0.08)",
  };
  const SEG_COLOR = {
    "Fire Services (SCBA)": COL.neg,
    "Detection": COL.blue,
    "Industrial PPE": COL.indus,
    "Other / Unclassified": COL.other,
  };
  const SEG_CLASS = {
    "Fire Services (SCBA)": "seg-fire",
    "Detection": "seg-detect",
    "Industrial PPE": "seg-indus",
    "Other / Unclassified": "seg-other",
  };

  const usdCompact = (n) => {
    const a = Math.abs(n);
    if (a >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
    if (a >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
    if (a >= 1e3) return "$" + (n / 1e3).toFixed(0) + "K";
    return "$" + n.toFixed(0);
  };
  const usdFull = (n) => "$" + Math.round(n).toLocaleString("en-US");
  const pct = (n, d) => (d ? (100 * n / d).toFixed(0) + "%" : "0%");
  const el = (id) => document.getElementById(id);

  Chart.defaults.font.family = "'Inter','Segoe UI',system-ui,sans-serif";
  Chart.defaults.color = COL.muted;
  Chart.defaults.font.size = 11;

  /* ---------- Section 00: window + hero tiles ---------- */
  el("sub-window").textContent =
    `Contract activity ${D.meta.window.start} → ${D.meta.window.end} · refreshed ${D.meta.generated}`;
  el("foot-date").textContent = D.meta.generated;

  const seg = Object.fromEntries(D.by_segment.map((s) => [s.segment, s]));
  const fire = seg["Fire Services (SCBA)"] || { amount: 0, count: 0 };
  const detect = seg["Detection"] || { amount: 0, count: 0 };

  const tiles = [
    { label: "Total federal awards", val: usdCompact(D.meta.total_dollars),
      sub: `${D.meta.total_awards.toLocaleString()} distinct prime contracts` },
    { label: "Fire Services (SCBA)", val: usdCompact(fire.amount),
      sub: `${pct(fire.amount, D.meta.total_dollars)} of dollars · ${fire.count} awards` },
    { label: "Detection", val: usdCompact(detect.amount),
      sub: `${pct(detect.amount, D.meta.total_dollars)} of dollars · ${detect.count} awards` },
    { label: "Reach", val: `${D.meta.n_agencies} agencies`,
      sub: `${D.meta.n_sub_agencies} buying offices · ${D.meta.n_states} states` },
  ];
  el("hero").innerHTML = tiles.map((t) => `
    <div class="hero-tile">
      <div class="hero-label">${t.label}</div>
      <div class="hero-val">${t.val}</div>
      <div class="hero-sub">${t.sub}</div>
    </div>`).join("");

  /* ---------- Section 01: segments ---------- */
  const segData = D.by_segment;
  new Chart(el("segDoughnut"), {
    type: "doughnut",
    data: {
      labels: segData.map((s) => s.segment),
      datasets: [{ data: segData.map((s) => s.amount),
        backgroundColor: segData.map((s) => SEG_COLOR[s.segment] || COL.other),
        borderColor: "#fff", borderWidth: 2 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "58%",
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
        tooltip: { callbacks: { label: (c) =>
          `${c.label}: ${usdFull(c.parsed)} (${pct(c.parsed, D.meta.total_dollars)})` } },
      },
    },
  });
  new Chart(el("segBar"), {
    type: "bar",
    data: {
      labels: segData.map((s) => s.segment),
      datasets: [{ data: segData.map((s) => s.count),
        backgroundColor: segData.map((s) => SEG_COLOR[s.segment] || COL.other) }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: { grid: { color: COL.grid }, ticks: { precision: 0 } },
                y: { grid: { display: false } } },
    },
  });
  el("take-seg").innerHTML =
    `<strong>Fire Services dominates the federal book</strong> at ${usdCompact(fire.amount)} ` +
    `(${pct(fire.amount, D.meta.total_dollars)} of awarded dollars) — overwhelmingly ` +
    `self-contained breathing apparatus (SCBA), the highest-margin product line and the one ` +
    `tied to the regulatory replacement cycle in the thesis. <strong>Detection</strong> is the ` +
    `clear #2 at ${usdCompact(detect.amount)} (${pct(detect.amount, D.meta.total_dollars)}). ` +
    `Industrial PPE shows up as many small GSA hard-hat / safety-helmet buys — high award count, ` +
    `low dollars — consistent with it being MSA's lowest-margin, commoditized segment.`;
  el("src-seg").innerHTML =
    `<strong>Source:</strong> USAspending.gov prime award records · segment mapping by ` +
    `description keyword → PSC → NAICS · refreshed <code>${D.meta.generated}</code>`;

  /* ---------- Section 02: trend by year ---------- */
  const yrs = D.by_year.filter((y) => Number(y.year) >= 2021);
  new Chart(el("yearChart"), {
    type: "bar",
    data: {
      labels: yrs.map((y) => y.year),
      datasets: [{ label: "Awarded $", data: yrs.map((y) => y.amount),
        backgroundColor: COL.accent, borderRadius: 4 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) =>
          `${usdFull(c.parsed.y)} · ${yrs[c.dataIndex].count} awards` } },
      },
      scales: { y: { grid: { color: COL.grid }, ticks: { callback: (v) => usdCompact(v) } },
                x: { grid: { display: false } } },
    },
  });
  const peak = yrs.reduce((a, b) => (b.amount > a.amount ? b : a), yrs[0]);
  el("take-year").innerHTML =
    `Federal awarded value steps up sharply into <strong>2023–2024</strong>, peaking at ` +
    `<strong>${usdCompact(peak.amount)} in ${peak.year}</strong> — driven by large DoD (Air Force) ` +
    `and DHS (Coast Guard) SCBA delivery orders. This is the federal footprint of the demand the ` +
    `thesis flags: ahead of the 2027–2029 replacement window for the record 2014–2018 G1 SCBA ` +
    `cohort. Watch whether award value re-accelerates as those units de-certify.`;
  el("src-year").innerHTML =
    `<strong>Source:</strong> USAspending.gov · awarded value by action start date · ` +
    `chart shows ${yrs[0].year}–${yrs[yrs.length - 1].year} · refreshed <code>${D.meta.generated}</code>`;

  /* ---------- Section 03: agencies ---------- */
  const ag = D.by_agency.slice(0, 10);
  new Chart(el("agencyChart"), {
    type: "bar",
    data: {
      labels: ag.map((a) => a.agency),
      datasets: [{ data: ag.map((a) => a.amount), backgroundColor: COL.accent, borderRadius: 4 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => `${usdFull(c.parsed.x)} · ${ag[c.dataIndex].count} awards` } },
      },
      scales: { x: { grid: { color: COL.grid }, ticks: { callback: (v) => usdCompact(v) } },
                y: { grid: { display: false }, ticks: { autoSkip: false, font: { size: 10 } } } },
    },
  });
  const top2 = ag.slice(0, 2);
  el("take-agency").innerHTML =
    `Demand is anchored by federal first-responder and defense buyers — led by ` +
    `<strong>${top2[0].agency}</strong> (${usdCompact(top2[0].amount)}) and ` +
    `<strong>${top2[1].agency}</strong> (${usdCompact(top2[1].amount)}). These are mandate-driven, ` +
    `budget-protected customers: safety equipment is rarely cut even in downturns, supporting the ` +
    `"non-cyclical, recurring" leg of the thesis.`;
  el("subAgencyTable").querySelector("tbody").innerHTML =
    D.by_sub_agency.slice(0, 10).map((s) => `
      <tr><td>${s.sub_agency || "—"}</td>
      <td class="num">${usdFull(s.amount)}</td>
      <td class="num">${s.count}</td></tr>`).join("");
  el("src-agency").innerHTML =
    `<strong>Source:</strong> USAspending.gov · awarding agency &amp; sub-agency · refreshed <code>${D.meta.generated}</code>`;

  /* ---------- Section 04: geography ---------- */
  const st = D.by_state.slice(0, 15);
  new Chart(el("stateChart"), {
    type: "bar",
    data: {
      labels: st.map((s) => s.state),
      datasets: [{ data: st.map((s) => s.amount), backgroundColor: COL.blue, borderRadius: 4 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => `${usdFull(c.parsed.x)} · ${st[c.dataIndex].count} awards` } },
      },
      scales: { x: { grid: { color: COL.grid }, ticks: { callback: (v) => usdCompact(v) } },
                y: { grid: { display: false } } },
    },
  });
  el("src-state").innerHTML =
    `<strong>Source:</strong> USAspending.gov · place-of-performance state · top 15 of ` +
    `${D.meta.n_states} · refreshed <code>${D.meta.generated}</code>`;

  /* ---------- Section 05: top contracts ---------- */
  el("contractsTable").querySelector("tbody").innerHTML =
    D.top_contracts.map((c) => `
      <tr>
        <td><a href="${c.url}" target="_blank" rel="noopener">${c.award_id || "—"}</a></td>
        <td><span class="badge ${SEG_CLASS[c.segment] || "seg-other"}">${c.segment.replace(" (SCBA)", "").replace(" / Unclassified", "")}</span></td>
        <td>${c.agency}${c.sub_agency ? " · " + c.sub_agency : ""}</td>
        <td class="num">${usdFull(c.amount)}</td>
        <td class="num">${c.start_date || "—"}</td>
        <td>${(c.description || "").replace(/</g, "&lt;")}</td>
      </tr>`).join("");
  el("src-contracts").innerHTML =
    `<strong>Source:</strong> USAspending.gov · top ${D.top_contracts.length} awards by value · ` +
    `award IDs link to official records · refreshed <code>${D.meta.generated}</code>`;

  /* ---------- Section 04: competition ---------- */
  const cv = D.competition.competed_vs_not;
  const compTotal = cv.competed.amount + cv.not_competed.amount;
  el("comp-won").textContent = usdCompact(cv.competed.amount);
  el("comp-won-sub").textContent =
    `${cv.competed.count} awards · ${pct(cv.competed.amount, compTotal)} of competed dollars`;
  el("comp-sole").textContent = usdCompact(cv.not_competed.amount);
  el("comp-sole-sub").textContent =
    `${cv.not_competed.count} awards · brand-locked / single-source`;

  const off = D.competition.offers;
  new Chart(el("offersChart"), {
    type: "bar",
    data: {
      labels: off.map((o) => o.bucket),
      datasets: [{ data: off.map((o) => o.count),
        backgroundColor: off.map((o) => (o.bucket.startsWith("1") ? COL.accent2 : COL.accent)),
        borderRadius: 4 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: (c) => `${c.parsed.y} awards` } } },
      scales: { y: { grid: { color: COL.grid }, ticks: { precision: 0 } },
                x: { grid: { display: false }, title: { display: true, text: "bids received" } } },
    },
  });
  const sole = off.find((o) => o.bucket.startsWith("1"));
  el("take-comp").innerHTML =
    `Of the ${D.competition.have_extent} awards with a competition flag, MSA won ` +
    `<strong>${usdCompact(cv.competed.amount)} in open competition</strong> (${cv.competed.count} awards) — ` +
    `it is repeatedly out-bidding rivals, not just coasting on incumbency. At the same time ` +
    `<strong>${sole ? sole.count : 0} awards drew only a single bid</strong>: contracts effectively ` +
    `brand-locked to MSA, evidence of the switching-cost / spec-in moat the thesis describes.`;
  el("src-comp").innerHTML =
    `<strong>Source:</strong> USAspending.gov / FPDS competition fields ` +
    `(<code>extent_competed</code>, <code>number_of_offers_received</code>) · refreshed <code>${D.meta.generated}</code>`;

  /* ---------- Section 05: state & local ---------- */
  const SL = D.state_local;
  if (SL && SL.by_jurisdiction && SL.by_jurisdiction.length) {
    const slTop = SL.by_jurisdiction.slice(0, 15);
    const states = SL.by_jurisdiction.filter((j) => j.level === "state").length;
    const cities = SL.by_jurisdiction.filter((j) => j.level === "city").length;
    const slTiles = [
      { label: "Direct payments to MSA", val: usdCompact(SL.meta.total_payments_usd),
        sub: `${SL.meta.total_rows.toLocaleString()} payment records` },
      { label: "Jurisdictions", val: String(SL.meta.n_jurisdictions),
        sub: `${states} states · ${cities} cities · + counties` },
      { label: "Top jurisdiction", val: slTop[0].jurisdiction,
        sub: `${usdCompact(slTop[0].amount)} · ${slTop[0].count} records` },
      { label: "Coverage", val: "Socrata sweep",
        sub: "open-checkbook portals, auto-discovered" },
    ];
    el("sl-hero").innerHTML = slTiles.map((t) => `
      <div class="hero-tile">
        <div class="hero-label">${t.label}</div>
        <div class="hero-val" style="font-size:${t.val.length > 10 ? "20px" : "30px"}">${t.val}</div>
        <div class="hero-sub">${t.sub}</div>
      </div>`).join("");

    new Chart(el("slChart"), {
      type: "bar",
      data: {
        labels: slTop.map((j) => j.jurisdiction),
        datasets: [{ data: slTop.map((j) => j.amount),
          backgroundColor: slTop.map((j) =>
            j.level === "state" ? COL.accent : j.level === "city" ? COL.blue : COL.indus),
          borderRadius: 4 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: "y",
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${usdFull(c.parsed.x)} · ${slTop[c.dataIndex].count} records (${slTop[c.dataIndex].level})` } } },
        scales: { x: { grid: { color: COL.grid }, ticks: { callback: (v) => usdCompact(v) } },
                  y: { grid: { display: false }, ticks: { font: { size: 10 } } } },
      },
    });
    el("take-sl").innerHTML =
      `Across <strong>${SL.meta.n_jurisdictions} state &amp; local governments</strong> we can see direct MSA ` +
      `payments totalling <strong>${usdCompact(SL.meta.total_payments_usd)}</strong> — led by ` +
      `<strong>${slTop[0].jurisdiction}</strong> (${usdCompact(slTop[0].amount)}, largely fire-department SCBA). ` +
      `Green = state, blue = city. This is demand entirely absent from federal data, and it is itself an ` +
      `undercount: it omits the very common case of buying MSA through a distributor.`;
    el("slTable").querySelector("tbody").innerHTML =
      SL.by_jurisdiction.slice(0, 20).map((j) => `
        <tr><td>${j.jurisdiction}</td>
        <td><span class="badge ${j.level === "state" ? "seg-detect" : j.level === "city" ? "seg-fire" : "seg-indus"}">${j.level}</span></td>
        <td class="num">${usdFull(j.amount)}</td>
        <td class="num">${j.count}</td></tr>`).join("");
    el("src-sl").innerHTML =
      `<strong>Source:</strong> Government open-data checkbooks on Socrata · automated vendor sweep ` +
      `(match: ${SL.meta.match_terms.join(", ")}) · payments booked directly to MSA · refreshed <code>${D.meta.generated}</code>`;
  }

  /* ---------- Section 06: AFG ---------- */
  const AFG = D.afg;
  if (AFG && AFG.by_year) {
    const ay = AFG.by_year.filter((y) => Number(y.fiscal_year) >= 2021 && y.amount > 0);
    new Chart(el("afgChart"), {
      type: "bar",
      data: {
        labels: ay.map((y) => "FY" + y.fiscal_year),
        datasets: [{ label: "AFG obligations", data: ay.map((y) => y.amount),
          backgroundColor: COL.neg, borderRadius: 4 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: (c) => usdFull(c.parsed.y) } } },
        scales: { y: { grid: { color: COL.grid }, ticks: { callback: (v) => usdCompact(v) } },
                  x: { grid: { display: false } } },
      },
    });
    const avg = ay.reduce((s, y) => s + y.amount, 0) / (ay.length || 1);
    el("take-afg").innerHTML =
      `National AFG funding runs <strong>~${usdCompact(avg)} per year</strong> of federal money flowing to ` +
      `fire departments for equipment. SCBA is one of the largest eligible categories. With a new NFPA SCBA ` +
      `standard landing in 2026 and the record 2014–2018 G1 cohort hitting its replacement window in ` +
      `2027–2029, this grant pool is the funded demand MSA's fire franchise is positioned to capture.`;
    el("src-afg").innerHTML =
      `<strong>Source:</strong> ${AFG.meta.source} · Assistance Listing ${AFG.meta.program} · ` +
      `refreshed <code>${AFG.meta.generated}</code>`;
  }

  /* ---------- Section 09: method ---------- */
  el("entities").textContent = D.meta.recipient_entities.join(" · ");
  el("src-method").innerHTML =
    `<strong>Source:</strong> USAspending.gov API · ${D.meta.total_awards} awards · ` +
    `${usdFull(D.meta.total_dollars)} total · refreshed <code>${D.meta.generated}</code>`;
})();
