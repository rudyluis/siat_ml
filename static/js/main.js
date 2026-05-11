$(document).ready(function () {
  if ($("#tablaData").length) {
    $("#tablaData").DataTable({
      pageLength: 10,
      language: {
        url: "https://cdn.datatables.net/plug-ins/1.13.8/i18n/es-ES.json",
      },
    });
  }
  $("#toggleMenu").on("click", function () {
    $(".sidebar").toggleClass("show");
  });
});
function groupBy(arr, key) {
  return arr.reduce((acc, o) => {
    const k = o[key] ?? "Sin dato";
    (acc[k] = acc[k] || []).push(o);
    return acc;
  }, {});
}
function sumBy(arr, key) {
  return arr.reduce((a, o) => a + (+o[key] || 0), 0);
}
function renderDashboardCharts(charts) {
  const carreraGrouped = groupBy(charts.carrera, "carrera");
  const carreras = Object.keys(carreraGrouped).slice(0, 8);
  const altoCarrera = carreras.map((c) =>
    sumBy(
      carreraGrouped[c].filter((x) => x.nivel_riesgo === "Alto"),
      "total",
    ),
  );
  const medioCarrera = carreras.map((c) =>
    sumBy(
      carreraGrouped[c].filter((x) => x.nivel_riesgo === "Medio"),
      "total",
    ),
  );
  if (document.getElementById("chartCarrera"))
    new Chart(document.getElementById("chartCarrera"), {
      type: "bar",
      data: {
        labels: carreras,
        datasets: [
          { label: "Alto", data: altoCarrera, backgroundColor: "#dc2626" },
          { label: "Medio", data: medioCarrera, backgroundColor: "#f59e0b" },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } }
      },
    });
  if (document.getElementById("chartDist"))
    new Chart(document.getElementById("chartDist"), {
      type: "doughnut",
      data: {
        labels: charts.dist.map((x) => x.nivel_riesgo),
        datasets: [
          {
            data: charts.dist.map((x) => x.total),
            backgroundColor: charts.dist.map(
              (x) => charts.colors[x.nivel_riesgo],
            ),
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
      },
    });
  const semGrouped = groupBy(charts.semestre, "semestre");
  const sems = Object.keys(semGrouped).sort((a, b) => Number(a) - Number(b));
  const altoSem = sems.map((s) =>
    sumBy(
      semGrouped[s].filter((x) => x.nivel_riesgo === "Alto"),
      "total",
    ),
  );
  const medioSem = sems.map((s) =>
    sumBy(
      semGrouped[s].filter((x) => x.nivel_riesgo === "Medio"),
      "total",
    ),
  );
  if (document.getElementById("chartSemestre"))
    new Chart(document.getElementById("chartSemestre"), {
      type: "line",
      data: {
        labels: sems,
        datasets: [
          {
            label: "Alto",
            data: altoSem,
            borderColor: "#dc2626",
            backgroundColor: "#dc2626",
            tension: 0.35,
          },
          {
            label: "Medio",
            data: medioSem,
            borderColor: "#f59e0b",
            backgroundColor: "#f59e0b",
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: { y: { beginAtZero: true } },
      },
    });
}

function shortLabel(txt, n = 18) {
  txt = String(txt ?? "Sin dato");
  return txt.length > n ? txt.slice(0, n - 1) + "…" : txt;
}
function pctColor(value) {
  if (value >= 37) return "#dc2626";
  if (value >= 25) return "#f59e0b";
  return "#16a34a";
}
function renderAcademicAnalyticsCharts(charts) {
  const carrera = charts.carrera_riesgo || [];
  const carreraLabels = carrera.map((x) => shortLabel(x.carrera, 20));
  const carreraRisk = carrera.map((x) => +x.riesgo_pct || 0);
  if (document.getElementById("aaCarreraRiesgo"))
    new Chart(document.getElementById("aaCarreraRiesgo"), {
      type: "bar",
      data: {
        labels: carreraLabels,
        datasets: [
          {
            label: "Riesgo medio + alto (%)",
            data: carreraRisk,
            backgroundColor: carreraRisk.map(pctColor),
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { callback: (v) => v + "%" } },
        },
      },
    });

  const prom = charts.carrera_promedio || [];
  if (document.getElementById("aaCarreraPromedio"))
    new Chart(document.getElementById("aaCarreraPromedio"), {
      type: "bar",
      data: {
        labels: prom.map((x) => shortLabel(x.carrera, 20)),
        datasets: [
          {
            label: "Promedio",
            data: prom.map((x) => +x.promedio || 0),
            backgroundColor: "#2563eb",
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });

  const dist = charts.dist || [];
  if (document.getElementById("aaDistribucion"))
    new Chart(document.getElementById("aaDistribucion"), {
      type: "doughnut",
      data: {
        labels: dist.map((x) => x.nivel_riesgo),
        datasets: [
          {
            data: dist.map((x) => x.total),
            backgroundColor: dist.map((x) => charts.colors[x.nivel_riesgo]),
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
      },
    });

  const sem = charts.semestre || [];
  if (document.getElementById("aaSemestreRiesgo"))
    new Chart(document.getElementById("aaSemestreRiesgo"), {
      type: "line",
      data: {
        labels: sem.map((x) => x.semestre + "°"),
        datasets: [
          {
            label: "Riesgo medio + alto (%)",
            data: sem.map((x) => +x.riesgo_pct || 0),
            borderColor: "#2563eb",
            backgroundColor: "#2563eb",
            tension: 0.35,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: {
          y: { beginAtZero: true, ticks: { callback: (v) => v + "%" } },
        },
      },
    });

  const asis = charts.carrera_asistencia || [];
  if (document.getElementById("aaAsistenciaCarrera"))
    new Chart(document.getElementById("aaAsistenciaCarrera"), {
      type: "bar",
      data: {
        labels: asis.map((x) => shortLabel(x.carrera, 14)),
        datasets: [
          {
            label: "Asistencia (%)",
            data: asis.map((x) => +x.asistencia || 0),
            backgroundColor: "#0ea5e9",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            ticks: { callback: (v) => v + "%" },
          },
        },
      },
    });

  const crit = charts.criticos || [];
  if (document.getElementById("aaIndicadores"))
    new Chart(document.getElementById("aaIndicadores"), {
      type: "bar",
      data: {
        labels: crit.map((x) => x.factor),
        datasets: [
          {
            label: "Valor",
            data: crit.map((x) => +x.valor || 0),
            backgroundColor: [
              "#dc2626",
              "#ef4444",
              "#f59e0b",
              "#fb923c",
              "#22c55e",
            ],
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } },
      },
    });

  const imp = charts.importance || [];
  if (document.getElementById("aaImportancia"))
    new Chart(document.getElementById("aaImportancia"), {
      type: "bar",
      data: {
        labels: imp.map((x) => x.factor),
        datasets: [
          {
            label: "Asociación",
            data: imp.map((x) => +x.importancia || 0),
            backgroundColor: "#16a34a",
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, max: 1 } },
      },
    });

  if (document.getElementById("aaSemestreMixto"))
    new Chart(document.getElementById("aaSemestreMixto"), {
      type: "line",
      data: {
        labels: sem.map((x) => x.semestre + "°"),
        datasets: [
          {
            label: "Promedio",
            data: sem.map((x) => +x.promedio || 0),
            borderColor: "#2563eb",
            backgroundColor: "#2563eb",
            tension: 0.35,
            yAxisID: "y",
          },
          {
            label: "Asistencia (%)",
            data: sem.map((x) => +x.asistencia || 0),
            borderColor: "#16a34a",
            backgroundColor: "#16a34a",
            tension: 0.35,
            yAxisID: "y1",
          },
          {
            label: "Reprobaciones",
            data: sem.map((x) => +x.reprobaciones || 0),
            borderColor: "#dc2626",
            backgroundColor: "#dc2626",
            tension: 0.35,
            yAxisID: "y",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
        scales: {
          y: { beginAtZero: true, position: "left" },
          y1: {
            beginAtZero: true,
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { callback: (v) => v + "%" },
          },
        },
      },
    });

  renderCorrHeatmap(charts.corr || { labels: [], values: [] });
}

function renderCorrHeatmap(corr) {
  const el = document.getElementById("corrHeatmap");
  if (!el) return;
  const labels = corr.labels || [];
  const values = corr.values || [];
  if (!labels.length) {
    el.innerHTML =
      '<div class="text-muted">No existen columnas suficientes para correlación.</div>';
    return;
  }
  let html =
    '<table class="corr-table"><thead><tr><th></th>' +
    labels.map((l) => `<th>${l}</th>`).join("") +
    "</tr></thead><tbody>";
  values.forEach((row, i) => {
    html += `<tr><th>${labels[i]}</th>`;
    row.forEach((v) => {
      const val = Number(v || 0);
      const abs = Math.min(1, Math.abs(val));
      const color =
        val >= 0
          ? `rgba(220,38,38,${0.18 + abs * 0.72})`
          : `rgba(37,99,235,${0.18 + abs * 0.72})`;
      html += `<td style="background:${color}">${val.toFixed(2)}</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  el.innerHTML = html;
}

let aaDynamicCharts = {};
function destroyChart(id) {
  if (aaDynamicCharts[id]) {
    aaDynamicCharts[id].destroy();
    delete aaDynamicCharts[id];
  }
}
function riskColor(r) {
  return { Bajo: "#16a34a", Medio: "#f59e0b", Alto: "#dc2626" }[r] || "#2563eb";
}
function niceNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.round(n * 100) / 100 : 0;
}
function pearson(xs, ys) {
  const pairs = xs
    .map((x, i) => [Number(x), Number(ys[i])])
    .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
  const n = pairs.length;
  if (n < 2) return null;
  const mx = pairs.reduce((a, p) => a + p[0], 0) / n,
    my = pairs.reduce((a, p) => a + p[1], 0) / n;
  let num = 0,
    dx = 0,
    dy = 0;
  pairs.forEach((p) => {
    const vx = p[0] - mx,
      vy = p[1] - my;
    num += vx * vy;
    dx += vx * vx;
    dy += vy * vy;
  });
  if (dx === 0 || dy === 0) return null;
  return num / Math.sqrt(dx * dy);
}
function labelForVar(charts, key) {
  return charts.variables && charts.variables[key]
    ? charts.variables[key]
    : key;
}
function filterAARecords(charts) {
  const carrera = document.getElementById("cmpCarrera")?.value || "";
  const semestre = document.getElementById("cmpSemestre")?.value || "";
  const riesgo = document.getElementById("cmpRiesgo")?.value || "";
  return (charts.records || []).filter(
    (r) =>
      (!carrera || String(r.carrera) === carrera) &&
      (!semestre || String(r.semestre) === semestre) &&
      (!riesgo || String(r.nivel_riesgo) === riesgo),
  );
}
function interpretationForCorr(r) {
  if (r === null || !Number.isFinite(r))
    return "No existen datos suficientes para interpretar la relación seleccionada.";
  const abs = Math.abs(r),
    sentido = r < 0 ? "inversa" : "directa";
  let fuerza =
    abs >= 0.7
      ? "alta"
      : abs >= 0.4
        ? "moderada"
        : abs >= 0.2
          ? "baja"
          : "muy baja";
  return `Existe una relación ${sentido} ${fuerza}: ${r < 0 ? "a menor valor de la variable X, mayor tiende a ser la variable Y" : "a mayor valor de la variable X, mayor tiende a ser la variable Y"}.`;
}
function renderDynamicComparison(charts) {
  const rec = filterAARecords(charts);
  const xKey = document.getElementById("cmpX")?.value || "asistencia_pct";
  const yKey =
    document.getElementById("cmpY")?.value || "probabilidad_desercion";
  const tipo = document.getElementById("cmpTipo")?.value || "scatter";
  const ctx = document.getElementById("aaComparacionDinamica");
  if (!ctx) return;
  const xLabel = labelForVar(charts, xKey),
    yLabel = labelForVar(charts, yKey);
  const xs = rec.map((r) => Number(r[xKey])).filter((v) => Number.isFinite(v));
  const ys = rec.map((r) => Number(r[yKey])).filter((v) => Number.isFinite(v));
  const corr = pearson(
    rec.map((r) => r[xKey]),
    rec.map((r) => r[yKey]),
  );
  destroyChart("aaComparacionDinamica");
  let config;
  if (tipo === "scatter") {
    config = {
      type: "scatter",
      data: {
        datasets: ["Alto", "Medio", "Bajo"].map((risk) => ({
          label: risk,
          data: rec
            .filter((r) => r.nivel_riesgo === risk)
            .map((r) => ({ x: niceNumber(r[xKey]), y: niceNumber(r[yKey]) }))
            .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)),
          backgroundColor: riskColor(risk),
          pointRadius: 4,
          pointHoverRadius: 6,
        })),
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "right" } },
        scales: {
          x: { title: { display: true, text: xLabel } },
          y: { title: { display: true, text: yLabel }, beginAtZero: false },
        },
      },
    };
  } else if (tipo === "doughnut") {
    const grouped = groupBy(rec, "nivel_riesgo");
    const labels = ["Alto", "Medio", "Bajo"];
    config = {
      type: "doughnut",
      data: {
        labels,
        datasets: [
          {
            data: labels.map((l) => (grouped[l] || []).length),
            backgroundColor: labels.map(riskColor),
          },
        ],
      },
      options: { responsive: true, plugins: { legend: { position: "right" } } },
    };
  } else {
    const grouped = groupBy(rec, "nivel_riesgo");
    const labels = ["Alto", "Medio", "Bajo"];
    const values = labels.map((l) => {
      const arr = (grouped[l] || [])
        .map((r) => Number(r[yKey]))
        .filter(Number.isFinite);
      return arr.length
        ? niceNumber(arr.reduce((a, b) => a + b, 0) / arr.length)
        : 0;
    });
    config = {
      type: tipo === "line" ? "line" : "bar",
      data: {
        labels,
        datasets: [
          {
            label: `Promedio de ${yLabel}`,
            data: values,
            backgroundColor: labels.map(riskColor),
            borderColor: labels.map(riskColor),
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    };
  }
  aaDynamicCharts["aaComparacionDinamica"] = new Chart(ctx, config);
  const rText = corr === null ? "-" : corr.toFixed(2);
  const mini = document.getElementById("cmpCorrelation");
  if (mini)
    mini.innerHTML = `<strong>Correlación (r):</strong> ${rText} <span>${interpretationForCorr(corr)}</span>`;
  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  setText("sumX", xLabel);
  setText("sumY", yLabel);
  setText(
    "sumTipo",
    {
      scatter: "Dispersión",
      bar: "Barras",
      line: "Línea",
      doughnut: "Pie / Donut",
    }[tipo] || tipo,
  );
  setText("sumN", rec.length.toLocaleString("es-BO"));
  setText("sumCorr", rText);
  const interp = document.getElementById("sumInterpretacion");
  if (interp) interp.textContent = interpretationForCorr(corr);
}
function averageByRisk(records, key) {
  const grouped = groupBy(records, "nivel_riesgo");
  const labels = ["Alto", "Medio", "Bajo"];
  return labels.map((l) => {
    const arr = (grouped[l] || [])
      .map((r) => Number(r[key]))
      .filter(Number.isFinite);
    return arr.length
      ? niceNumber(arr.reduce((a, b) => a + b, 0) / arr.length)
      : 0;
  });
}
function renderAcademicAnalyticsChartsAdvanced(charts) {
  renderAcademicAnalyticsCharts(charts);
  const records = charts.records || [];
  const dist = charts.dist || [];
  if (document.getElementById("aaBarrasRiesgo"))
    aaDynamicCharts["aaBarrasRiesgo"] = new Chart(
      document.getElementById("aaBarrasRiesgo"),
      {
        type: "bar",
        data: {
          labels: ["Alto", "Medio", "Bajo"],
          datasets: [
            {
              data: ["Alto", "Medio", "Bajo"].map(
                (r) => (groupBy(records, "nivel_riesgo")[r] || []).length,
              ),
              backgroundColor: ["#dc2626", "#f59e0b", "#16a34a"],
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
        },
      },
    );
  if (document.getElementById("aaPromedioRiesgo"))
    aaDynamicCharts["aaPromedioRiesgo"] = new Chart(
      document.getElementById("aaPromedioRiesgo"),
      {
        type: "bar",
        data: {
          labels: ["Alto", "Medio", "Bajo"],
          datasets: [
            {
              label: "Promedio académico",
              data: averageByRisk(records, "promedio_2sem"),
              backgroundColor: ["#ef4444", "#f59e0b", "#22c55e"],
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } },
        },
      },
    );
  if (document.getElementById("aaPieCarrera")) {
    const grouped = groupBy(records, "carrera");
    const labels = Object.keys(grouped)
      .sort((a, b) => grouped[b].length - grouped[a].length)
      .slice(0, 8);
    aaDynamicCharts["aaPieCarrera"] = new Chart(
      document.getElementById("aaPieCarrera"),
      {
        type: "pie",
        data: {
          labels: labels.map((l) => shortLabel(l, 22)),
          datasets: [
            {
              data: labels.map((l) => grouped[l].length),
              backgroundColor: [
                "#2563eb",
                "#f97316",
                "#16a34a",
                "#f59e0b",
                "#0ea5e9",
                "#dc2626",
                "#7c3aed",
                "#14b8a6",
              ],
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { position: "right" } },
        },
      },
    );
  }
  renderDynamicComparison(charts);
  document
    .getElementById("btnComparar")
    ?.addEventListener("click", function (e) {
      e.preventDefault();
      renderDynamicComparison(charts);
    });
  ["cmpCarrera", "cmpSemestre", "cmpRiesgo", "cmpX", "cmpY", "cmpTipo"].forEach(
    (id) =>
      document
        .getElementById(id)
        ?.addEventListener("change", () => renderDynamicComparison(charts)),
  );
  document
    .getElementById("btnLimpiar")
    ?.addEventListener("click", function (e) {
      e.preventDefault();
      ["cmpCarrera", "cmpSemestre", "cmpRiesgo"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.value = "";
      });
      const x = document.getElementById("cmpX"),
        y = document.getElementById("cmpY"),
        t = document.getElementById("cmpTipo");
      if (x && charts.variables?.asistencia_pct) x.value = "asistencia_pct";
      if (y && charts.variables?.probabilidad_desercion)
        y.value = "probabilidad_desercion";
      if (t) t.value = "scatter";
      renderDynamicComparison(charts);
    });
}

function initAcademicTabs() {
  const buttons = document.querySelectorAll("#aaTabs button[data-tab]");
  const sections = document.querySelectorAll(".aa-section");
  const selector = document.getElementById("aaVistaSelector");
  function activate(tab) {
    buttons.forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    sections.forEach((sec) =>
      sec.classList.toggle("active", sec.id === "aa-tab-" + tab),
    );
    if (selector) selector.value = tab;
    setTimeout(() => {
      Object.values(aaDynamicCharts || {}).forEach((ch) => {
        try {
          ch.resize();
          ch.update();
        } catch (e) {}
      });
    }, 120);
  }
  buttons.forEach((b) =>
    b.addEventListener("click", () => activate(b.dataset.tab)),
  );
  if (selector)
    selector.addEventListener("change", (e) => activate(e.target.value));
  document
    .getElementById("btnModoPresentacion")
    ?.addEventListener("click", () =>
      document.body.classList.toggle("presentation-mode"),
    );
  activate("resumen");
  if (document.getElementById("aaImportanciaExtra") && window.aaCharts) {
    const imp = aaCharts.importance || [];
    aaDynamicCharts["aaImportanciaExtra"] = new Chart(
      document.getElementById("aaImportanciaExtra"),
      {
        type: "bar",
        data: {
          labels: imp.map((x) => x.factor),
          datasets: [
            {
              label: "Asociación",
              data: imp.map((x) => +x.importancia || 0),
              backgroundColor: "#2563eb",
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true, max: 1 } },
        },
      },
    );
  }
  if (document.getElementById("aaTendencia")) {
    aaDynamicCharts["aaTendencia"] = new Chart(
      document.getElementById("aaTendencia"),
      {
        type: "line",
        data: {
          labels: ["2023-I", "2023-II", "2024-I", "2024-II", "2025-I"],
          datasets: [
            {
              label: "Riesgo alto",
              data: [19, 17, 16, 15, 14],
              borderColor: "#dc2626",
              backgroundColor: "#dc2626",
              tension: 0.35,
            },
            {
              label: "Retención",
              data: [71, 73, 75, 77, 79],
              borderColor: "#16a34a",
              backgroundColor: "#16a34a",
              tension: 0.35,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { position: "bottom" } },
          scales: {
            y: { beginAtZero: true, ticks: { callback: (v) => v + "%" } },
          },
        },
      },
    );
  }
}
