/* El Libro de las Hojas — consumo del contrato y estados de pantalla.
   Sin frameworks: el contrato manda y la pantalla se adapta. */

(() => {
  "use strict";

  const API = "/api";
  const DEFAULT_MAX_BYTES = 10 * 1024 * 1024;
  // El historial se pide por páginas: el archivo crece y nadie quiere 500 filas
  // en el primer trazo (ADR-017).
  const PAGE_SIZE = 50;
  // Valor de fantasma para el filtro «Quién»: las hojas sin cuenta detrás
  // (ADR-018). No puede chocar con un usuario real, que no admite «@».
  const UNASSIGNED = "@sin-dueno";
  const state = {
    items: [],
    current: null,
    pendingDelete: null,
    pendingClear: false,
    pendingOrphans: false,
    pendingUser: null,
    maxUploadBytes: DEFAULT_MAX_BYTES,
    allowedFormats: ["PNG", "JPEG"],
    busy: false,
    reportRequest: 0,
    auth: { required: false, user: null },
    filters: { q: "", version: "", owner: "", unassigned: false },
    versions: [],
    users: [],
    page: 0,
    hasMore: false,
    // Catálogo de umbrales y valores que muestra el panel (ADR-022).
    tuning: { catalogue: [], defaults: {}, values: {} },
  };

  const els = {
    health: document.getElementById("health"),
    healthText: document.getElementById("health-text"),
    dropzone: document.getElementById("dropzone"),
    pick: document.getElementById("pick"),
    input: document.getElementById("file-input"),
    dropHint: document.getElementById("drop-hint"),
    tuningPanel: document.getElementById("tuning"),
    tuningGrid: document.getElementById("tuning-grid"),
    tuningBadge: document.getElementById("tuning-badge"),
    tuningReset: document.getElementById("tuning-reset"),
    tuningApply: document.getElementById("tuning-apply"),
    tuningStatus: document.getElementById("tuning-status"),
    alert: document.getElementById("alert"),
    alertMessage: document.getElementById("alert-message"),
    status: document.getElementById("status"),
    statusText: document.getElementById("status-text"),
    live: document.getElementById("live"),
    result: document.getElementById("result"),
    resultTitle: document.getElementById("result-title"),
    resultMeta: document.getElementById("result-meta"),
    seal: document.getElementById("seal"),
    sealWord: document.getElementById("seal-word"),
    verdictNote: document.getElementById("verdict-note"),
    metrics: document.getElementById("metrics"),
    overlay: document.getElementById("overlay"),
    layers: document.getElementById("layers"),
    layerList: document.getElementById("layer-list"),
    trace: document.getElementById("trace-json"),
    originalLink: document.getElementById("original-link"),
    deleteCurrent: document.getElementById("delete-current"),
    ledgerList: document.getElementById("ledger-list"),
    ledgerCount: document.getElementById("ledger-count"),
    ledgerEmpty: document.getElementById("ledger-empty"),
    ledgerMore: document.getElementById("ledger-more"),
    filterQ: document.getElementById("filter-q"),
    filterVersion: document.getElementById("filter-version"),
    filterOwner: document.getElementById("filter-owner"),
    filterOwnerField: document.getElementById("filter-owner-field"),
    session: document.getElementById("session"),
    sessionName: document.getElementById("session-name"),
    sessionRole: document.getElementById("session-role"),
    logout: document.getElementById("logout"),
    usersOpen: document.getElementById("users-open"),
    usersDialog: document.getElementById("users"),
    usersList: document.getElementById("users-list"),
    usersError: document.getElementById("users-error"),
    usersClose: document.getElementById("users-close"),
    userForm: document.getElementById("user-form"),
    userUsername: document.getElementById("user-username"),
    userDisplay: document.getElementById("user-display"),
    userPassword: document.getElementById("user-password"),
    userRole: document.getElementById("user-role"),
    userSubmit: document.getElementById("user-submit"),
    clearOrphans: document.getElementById("clear-orphans"),
    login: document.getElementById("login"),
    loginForm: document.getElementById("login-form"),
    loginUser: document.getElementById("login-user"),
    loginPassword: document.getElementById("login-password"),
    loginError: document.getElementById("login-error"),
    loginSubmit: document.getElementById("login-submit"),
    refresh: document.getElementById("refresh"),
    clearArchive: document.getElementById("clear-archive"),
    dialog: document.getElementById("confirm-delete"),
    confirmTitle: document.getElementById("confirm-title"),
    confirmText: document.getElementById("confirm-text"),
    confirmAccept: document.getElementById("confirm-accept"),
    reportOpen: document.getElementById("report-open"),
    reportDialog: document.getElementById("lot-report"),
    reportTitle: document.getElementById("report-title"),
    reportSubtitle: document.getElementById("report-subtitle"),
    reportSeal: document.getElementById("report-seal"),
    reportSealWord: document.getElementById("report-seal-word"),
    reportSevere: document.getElementById("report-severe"),
    reportSave: document.getElementById("report-save"),
    reportSaveStatus: document.getElementById("report-save-status"),
    reportPrint: document.getElementById("report-print"),
    reportEmpty: document.getElementById("report-empty"),
    reportLoading: document.getElementById("report-loading"),
    reportError: document.getElementById("report-error"),
    reportErrorText: document.getElementById("report-error-text"),
    reportBody: document.getElementById("report-body"),
    reportImages: document.getElementById("report-images"),
    reportLesions: document.getElementById("report-lesions"),
    reportAreaMedian: document.getElementById("report-area-median"),
    reportWorstArea: document.getElementById("report-worst-area"),
    reportWorstName: document.getElementById("report-worst-name"),
    reportHistogram: document.getElementById("report-histogram"),
    reportHistogramData: document.getElementById("report-histogram-data"),
    reportScatter: document.getElementById("report-scatter"),
    reportScatterData: document.getElementById("report-scatter-data"),
    reportRanking: document.getElementById("report-ranking"),
    reportRankingData: document.getElementById("report-ranking-data"),
    reportRows: document.getElementById("report-rows"),
    reportQuality: document.getElementById("report-quality"),
    reportMethods: document.getElementById("report-methods"),
  };

  const numberFormat = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 });
  const dateFormat = new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" });
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const format = {
    int: (value) => numberFormat.format(value),
    num: (value) => numberFormat.format(value),
    pct: (value) => `${numberFormat.format(value * 100)} %`,
  };

  function announce(message) {
    els.live.textContent = "";
    window.setTimeout(() => {
      els.live.textContent = message;
    }, 30);
  }

  function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "—" : dateFormat.format(date);
  }

  const SEVERITY_ORDER = ["sano", "leve", "moderado", "severo"];
  const SEVERITY_LABELS = {
    sano: "Sano",
    leve: "Leve",
    moderado: "Moderado",
    severo: "Severo",
    sin_datos: "Sin datos",
  };
  const HISTOGRAM_BINS = [
    { label: "0–1 %", test: (value) => value < 1 },
    { label: "1–2 %", test: (value) => value < 2 },
    { label: "2–5 %", test: (value) => value < 5 },
    { label: "5–10 %", test: (value) => value < 10 },
    { label: "10–20 %", test: (value) => value < 20 },
    { label: "≥ 20 %", test: () => true },
  ];
  const FLAG_LABELS = {
    borrosa: "borrosa",
    poca_superficie_valida: "poca superficie válida",
    sobreexpuesta: "sobreexpuesta",
  };
  const METHOD_LABELS = {
    primer_plano: "primer plano",
    grabcut: "GrabCut",
    desconocido: "sin registro",
  };
  const STAGE_LABELS = {
    entrada: "entrada",
    aislamiento: "aislamiento de hoja",
    preproceso: "preproceso",
    segmentacion: "segmentación",
    medicion: "medición",
  };
  const SVG_NS = "http://www.w3.org/2000/svg";
  const reportBandSegments = Object.fromEntries(
    SEVERITY_ORDER.map((key) => [key, document.getElementById(`report-band-${key}`)])
  );
  const reportSeverityNodes = Object.fromEntries(
    SEVERITY_ORDER.map((key) => [
      key,
      {
        count: document.getElementById(`report-sev-${key}-count`),
        pct: document.getElementById(`report-sev-${key}-pct`),
      },
    ])
  );

  function plural(count, singular, pluralForm) {
    return `${format.int(count)} ${count === 1 ? singular : pluralForm}`;
  }

  function severityKey(areaFraction) {
    if (areaFraction < 0.01) return "sano";
    if (areaFraction < 0.05) return "leve";
    if (areaFraction < 0.15) return "moderado";
    return "severo";
  }

  function formatFlag(flag) {
    return FLAG_LABELS[flag] || String(flag).replaceAll("_", " ");
  }

  function formatMethod(method) {
    return METHOD_LABELS[method] || String(method || "desconocido").replaceAll("_", " ");
  }

  function truncateName(name, limit = 26) {
    const text = name || "sin nombre";
    return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
  }

  function svgNode(tag, attributes = {}, text = "") {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attributes).forEach(([key, value]) => {
      if (value !== null && value !== undefined) node.setAttribute(key, String(value));
    });
    if (text !== "") node.textContent = text;
    return node;
  }

  function svgText(parent, x, y, text, className, anchor = "start") {
    parent.append(svgNode("text", { x, y, class: className, "text-anchor": anchor }, text));
  }

  function mountChart(container, svg, label) {
    container.replaceChildren(svg);
    container.setAttribute("aria-label", label);
  }

  function niceAreaMax(value) {
    if (value <= 5) return 5;
    if (value <= 10) return 10;
    if (value <= 20) return 20;
    if (value <= 30) return 30;
    if (value <= 50) return 50;
    if (value <= 75) return 75;
    if (value <= 100) return 100;
    return Math.ceil(value / 25) * 25;
  }

  function histogramCounts(points) {
    const counts = HISTOGRAM_BINS.map(() => 0);
    points.forEach((point) => {
      const area = Math.max(0, Number(point.area_fraction) || 0) * 100;
      const index = HISTOGRAM_BINS.findIndex((bin) => bin.test(area));
      counts[index === -1 ? counts.length - 1 : index] += 1;
    });
    return counts;
  }

  function buildHistogram(points) {
    const width = 720;
    const height = 268;
    const margin = { left: 52, right: 16, top: 24, bottom: 48 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const counts = histogramCounts(points);
    const maxCount = Math.max(...counts, 1);
    const yMax = Math.max(4, Math.ceil(maxCount / 4) * 4);
    const svg = svgNode("svg", {
      viewBox: `0 0 ${width} ${height}`,
      preserveAspectRatio: "xMidYMid meet",
      "aria-hidden": "true",
      focusable: "false",
    });

    for (let tick = 0; tick <= 4; tick += 1) {
      const value = (yMax / 4) * tick;
      const y = margin.top + plotHeight - (value / yMax) * plotHeight;
      svg.append(
        svgNode("line", {
          x1: margin.left,
          x2: width - margin.right,
          y1: y,
          y2: y,
          class: tick === 0 ? "chart-baseline" : "chart-grid",
        })
      );
      svgText(svg, margin.left - 8, y + 4, format.int(value), "chart-tick", "end");
    }

    const slot = plotWidth / counts.length;
    const barWidth = slot * 0.58;
    counts.forEach((count, index) => {
      const x = margin.left + slot * index + (slot - barWidth) / 2;
      const barHeight = (count / yMax) * plotHeight;
      const y = margin.top + plotHeight - barHeight;
      if (count > 0) {
        svg.append(
          svgNode("rect", {
            x,
            y,
            width: barWidth,
            height: barHeight,
            class: "chart-bar",
          })
        );
        svgText(svg, x + barWidth / 2, y - 6, format.int(count), "chart-value", "middle");
      } else {
        svgText(
          svg,
          x + barWidth / 2,
          margin.top + plotHeight - 6,
          "0",
          "chart-value",
          "middle"
        );
      }
      svgText(
        svg,
        x + barWidth / 2,
        margin.top + plotHeight + 20,
        HISTOGRAM_BINS[index].label,
        "chart-tick",
        "middle"
      );
    });

    svgText(svg, margin.left, 14, "Hojas (n)", "chart-axis-title");
    svgText(
      svg,
      margin.left + plotWidth / 2,
      height - 8,
      "Área afectada (% de la superficie válida)",
      "chart-axis-title",
      "middle"
    );

    const dominantIndex = counts.indexOf(Math.max(...counts));
    const label =
      `Histograma de ${plural(points.length, "hoja", "hojas")}; ` +
      `el intervalo más poblado es ${HISTOGRAM_BINS[dominantIndex].label} ` +
      `con ${format.int(counts[dominantIndex])}.`;
    return { svg, counts, label };
  }

  function renderHistogramData(counts) {
    const rows = counts.map((count, index) => {
      const row = document.createElement("tr");
      const label = document.createElement("td");
      label.textContent = HISTOGRAM_BINS[index].label;
      const value = document.createElement("td");
      value.className = "is-number";
      value.textContent = format.int(count);
      row.append(label, value);
      return row;
    });
    els.reportHistogramData.replaceChildren(...rows);
  }

  function buildScatter(points) {
    const width = 720;
    const height = 340;
    const margin = { left: 56, right: 24, top: 24, bottom: 56 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const lesionCounts = points.map((point) => Math.max(0, Number(point.lesion_count) || 0));
    const areas = points.map(
      (point) => Math.max(0, Number(point.area_fraction) || 0) * 100
    );
    const maxLesions = Math.max(1, ...lesionCounts);
    const minLesions = Math.min(...lesionCounts);
    const maxArea = Math.max(0, ...areas);
    const minArea = Math.min(...areas);
    const xMax = Math.max(4, Math.ceil(maxLesions / 4) * 4);
    const yMax = niceAreaMax(maxArea * 1.05);
    const svg = svgNode("svg", {
      viewBox: `0 0 ${width} ${height}`,
      preserveAspectRatio: "xMidYMid meet",
      "aria-hidden": "true",
      focusable: "false",
    });

    for (let tick = 0; tick <= 5; tick += 1) {
      const value = (yMax / 5) * tick;
      const y = margin.top + plotHeight - (tick / 5) * plotHeight;
      svg.append(
        svgNode("line", {
          x1: margin.left,
          x2: width - margin.right,
          y1: y,
          y2: y,
          class: tick === 0 ? "chart-baseline" : "chart-grid",
        })
      );
      svgText(svg, margin.left - 8, y + 4, format.num(value), "chart-tick", "end");
    }

    for (let tick = 0; tick <= 4; tick += 1) {
      const value = (xMax / 4) * tick;
      const x = margin.left + (tick / 4) * plotWidth;
      svg.append(
        svgNode("line", {
          x1: x,
          x2: x,
          y1: margin.top,
          y2: margin.top + plotHeight,
          class: tick === 0 ? "chart-baseline" : "chart-grid",
        })
      );
      svgText(
        svg,
        x,
        margin.top + plotHeight + 20,
        format.int(value),
        "chart-tick",
        "middle"
      );
    }

    points.forEach((point, index) => {
      const areaFraction = Math.max(0, Number(point.area_fraction) || 0);
      const x = margin.left + (lesionCounts[index] / xMax) * plotWidth;
      const y = margin.top + plotHeight - (areas[index] / yMax) * plotHeight;
      const key = severityKey(areaFraction);
      const name = point.filename || "sin nombre";
      let shape;
      if (key === "severo") {
        shape = svgNode("path", {
          d: `M ${x} ${y - 5} L ${x + 5} ${y} L ${x} ${y + 5} L ${x - 5} ${y} Z`,
          class: "chart-point chart-point--severo",
        });
      } else {
        shape = svgNode("circle", {
          cx: x,
          cy: y,
          r: 4,
          class: `chart-point chart-point--${key}`,
        });
      }
      shape.append(
        svgNode(
          "title",
          {},
          `${name} · ${format.int(lesionCounts[index])} lesiones · ` +
            `${format.num(areas[index])} % · ${SEVERITY_LABELS[key]}`
        )
      );
      svg.append(shape);
    });

    svgText(svg, margin.left, 14, "Área afectada (%)", "chart-axis-title");
    svgText(
      svg,
      margin.left + plotWidth / 2,
      height - 8,
      "Lesiones (componentes)",
      "chart-axis-title",
      "middle"
    );

    const label =
      `Dispersión de ${plural(points.length, "hoja", "hojas")}; ` +
      `entre ${format.int(minLesions)} y ${format.int(maxLesions)} lesiones, ` +
      `área afectada de ${format.num(minArea)} % a ${format.num(maxArea)} %.`;
    return { svg, label };
  }

  function renderScatterData(points) {
    const rows = points.map((point) => {
      const area = Math.max(0, Number(point.area_fraction) || 0);
      const row = document.createElement("tr");
      const name = document.createElement("td");
      name.textContent = point.filename || "sin nombre";
      const lesions = document.createElement("td");
      lesions.className = "is-number";
      lesions.textContent = format.int(Math.max(0, Number(point.lesion_count) || 0));
      const areaCell = document.createElement("td");
      areaCell.className = "is-number";
      areaCell.textContent = format.num(area * 100);
      const level = document.createElement("td");
      level.textContent = SEVERITY_LABELS[severityKey(area)];
      row.append(name, lesions, areaCell, level);
      return row;
    });
    els.reportScatterData.replaceChildren(...rows);
  }

  function buildRanking(worst) {
    const entries = worst.slice(0, 5);
    const width = 720;
    const height = 40 + 34 * Math.max(entries.length, 1);
    const margin = { left: 190, right: 64, top: 12, bottom: 36 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const areas = entries.map(
      (point) => Math.max(0, Number(point.area_fraction) || 0) * 100
    );
    const maxArea = Math.max(0, ...areas);
    const xMax = niceAreaMax(maxArea * 1.05);
    const baselineY = margin.top + plotHeight;
    const svg = svgNode("svg", {
      viewBox: `0 0 ${width} ${height}`,
      preserveAspectRatio: "xMidYMid meet",
      "aria-hidden": "true",
      focusable: "false",
    });

    for (let tick = 0; tick <= 5; tick += 1) {
      const value = (xMax / 5) * tick;
      const x = margin.left + (tick / 5) * plotWidth;
      svg.append(
        svgNode("line", {
          x1: x,
          x2: x,
          y1: margin.top,
          y2: baselineY,
          class: tick === 0 ? "chart-baseline" : "chart-grid",
        })
      );
      svgText(svg, x, baselineY + 16, format.num(value), "chart-tick", "middle");
    }

    entries.forEach((point, index) => {
      const name = point.filename || "sin nombre";
      const y = margin.top + index * 34 + 8;
      const barWidth = xMax > 0 ? (areas[index] / xMax) * plotWidth : 0;
      const nameNode = svgNode(
        "text",
        {
          x: margin.left - 12,
          y: y + 13,
          class: "chart-tick",
          "text-anchor": "end",
        },
        truncateName(name)
      );
      nameNode.append(svgNode("title", {}, name));
      svg.append(nameNode);
      svg.append(
        svgNode("rect", {
          x: margin.left,
          y,
          width: Math.max(barWidth, 0),
          height: 18,
          class: index === 0 ? "chart-bar chart-bar--worst" : "chart-bar",
        })
      );
      svgText(
        svg,
        margin.left + barWidth + 6,
        y + 13,
        format.num(areas[index]),
        "chart-value"
      );
    });

    svgText(
      svg,
      margin.left + plotWidth / 2,
      height - 4,
      "Área afectada (% de la superficie válida)",
      "chart-axis-title",
      "middle"
    );

    const worstPoint = entries[0];
    const label = worstPoint
      ? `Ranking de ${plural(entries.length, "hoja", "hojas")} por área afectada; ` +
        `la peor es ${worstPoint.filename || "sin nombre"} con ${format.num(areas[0])} %.`
      : "Ranking de hojas por área afectada sin datos.";
    return { svg, label };
  }

  function renderRankingData(worst) {
    const rows = worst.slice(0, 5).map((point) => {
      const area = Math.max(0, Number(point.area_fraction) || 0);
      const row = document.createElement("tr");
      const name = document.createElement("td");
      name.textContent = point.filename || "sin nombre";
      const areaCell = document.createElement("td");
      areaCell.className = "is-number";
      areaCell.textContent = format.num(area * 100);
      const level = document.createElement("td");
      level.textContent = SEVERITY_LABELS[severityKey(area)];
      row.append(name, areaCell, level);
      return row;
    });
    els.reportRankingData.replaceChildren(...rows);
  }

  function buildReportRow(point) {
    const area = Math.max(0, Number(point.area_fraction) || 0);
    const key = severityKey(area);
    const row = document.createElement("tr");
    row.className = "report-row";
    row.dataset.severity = key;

    const nameCell = document.createElement("td");
    nameCell.dataset.label = "Hoja";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "report-open";
    open.dataset.id = point.id || "";
    open.textContent = point.filename || "sin nombre";
    open.title = point.filename || "sin nombre";
    open.setAttribute(
      "aria-label",
      `Abrir la inspección de ${point.filename || "la hoja sin nombre"}`
    );
    nameCell.append(open);

    const dateCell = document.createElement("td");
    dateCell.dataset.label = "Fecha";
    dateCell.textContent = formatDate(point.created_at);

    const lesionsCell = document.createElement("td");
    lesionsCell.dataset.label = "Lesiones";
    lesionsCell.className = "is-number";
    lesionsCell.textContent = format.int(Math.max(0, Number(point.lesion_count) || 0));

    const areaCell = document.createElement("td");
    areaCell.dataset.label = "Área (%)";
    areaCell.className = "is-number";
    areaCell.textContent = format.num(area * 100);

    const feretCell = document.createElement("td");
    feretCell.dataset.label = "Feret máx. (px)";
    feretCell.className = "is-number";
    feretCell.textContent = format.num(Math.max(0, Number(point.max_feret_px) || 0));

    const qualityCell = document.createElement("td");
    qualityCell.dataset.label = "Calidad / aislamiento";
    const flags = Array.isArray(point.quality_flags) ? point.quality_flags : [];
    const qualityText = flags.length ? flags.map(formatFlag).join(", ") : "sin advertencias";
    qualityCell.textContent = `${qualityText} · ${formatMethod(point.isolation_method)}`;

    row.append(nameCell, dateCell, lesionsCell, areaCell, feretCell, qualityCell);
    return row;
  }

  function renderReportNotes(report) {
    const quality = Object.entries(report.quality_flags || {}).map(([flag, count]) => {
      const item = document.createElement("li");
      item.textContent = `${formatFlag(flag)} · ${plural(Number(count) || 0, "hoja", "hojas")}`;
      return item;
    });
    els.reportQuality.replaceChildren(...quality);

    const methods = Object.entries(report.isolation_methods || {}).map(([method, count]) => {
      const item = document.createElement("li");
      item.textContent = `${formatMethod(method)} · ${plural(Number(count) || 0, "hoja", "hojas")}`;
      return item;
    });
    els.reportMethods.replaceChildren(...methods);
  }

  function showReportState(kind) {
    els.reportLoading.hidden = kind !== "loading";
    els.reportEmpty.hidden = kind !== "empty";
    els.reportError.hidden = kind !== "error";
    els.reportBody.hidden = kind !== "body";
    els.reportSave.disabled = kind !== "body";
  }

  function resetReport() {
    els.reportSubtitle.textContent = "—";
    els.reportSeal.dataset.level = "sin_datos";
    els.reportSealWord.textContent = "Sin datos";
    els.reportSevere.hidden = true;
    els.reportWorstName.textContent = "—";
    els.reportWorstName.removeAttribute("title");
    els.reportErrorText.textContent = "";
    els.reportSaveStatus.textContent = "";
    showReportState("loading");
  }

  function renderReport(report) {
    const points = Array.isArray(report.points) ? report.points : [];
    const totals = report.totals || {};
    const images = Number(totals.images) || 0;
    els.reportSubtitle.textContent =
      `Generado el ${formatDate(report.generated_at)} · ` +
      plural(images, "imagen aceptada", "imágenes aceptadas");
    els.reportImages.textContent = format.int(images);
    els.reportLesions.textContent = format.int(Number(totals.lesions) || 0);
    els.reportAreaMedian.textContent = format.num(
      (Number(totals.median_area_fraction) || 0) * 100
    );

    const worst = Array.isArray(report.worst) && report.worst.length ? report.worst[0] : null;
    if (worst) {
      const area = Math.max(0, Number(worst.area_fraction) || 0);
      els.reportWorstArea.textContent = format.num(area * 100);
      els.reportWorstName.textContent = worst.filename || "sin nombre";
      els.reportWorstName.title = worst.filename || "sin nombre";
    } else {
      els.reportWorstArea.textContent = "—";
      els.reportWorstName.textContent = "—";
      els.reportWorstName.removeAttribute("title");
    }

    const level = SEVERITY_LABELS[report.dominant_severity]
      ? report.dominant_severity
      : "sin_datos";
    els.reportSeal.dataset.level = level;
    els.reportSealWord.textContent = SEVERITY_LABELS[level];
    els.reportSevere.hidden = !report.has_severe;

    const severity = Array.isArray(report.severity) ? report.severity : [];
    SEVERITY_ORDER.forEach((key) => {
      const entry = severity.find((bin) => bin.key === key) || { count: 0, fraction: 0 };
      const segment = reportBandSegments[key];
      const nodes = reportSeverityNodes[key];
      const count = Number(entry.count) || 0;
      const fraction = Number(entry.fraction) || 0;
      nodes.count.textContent = format.int(count);
      nodes.pct.textContent = format.pct(fraction);
      segment.style.flexGrow = String(fraction);
      segment.hidden = count === 0;
    });

    if (points.length === 0) {
      showReportState("empty");
      return;
    }

    const histogram = buildHistogram(points);
    mountChart(els.reportHistogram, histogram.svg, histogram.label);
    renderHistogramData(histogram.counts);

    const scatter = buildScatter(points);
    mountChart(els.reportScatter, scatter.svg, scatter.label);
    renderScatterData(points);

    const worstEntries = Array.isArray(report.worst) ? report.worst : [];
    const ranking = buildRanking(worstEntries);
    mountChart(els.reportRanking, ranking.svg, ranking.label);
    renderRankingData(worstEntries);

    els.reportRows.replaceChildren(...points.map(buildReportRow));
    renderReportNotes(report);
    showReportState("body");
  }

  async function openReport() {
    if (typeof els.reportDialog.showModal !== "function") return;
    const request = state.reportRequest + 1;
    state.reportRequest = request;
    resetReport();
    if (!els.reportDialog.open) els.reportDialog.showModal();
    els.reportDialog.setAttribute("aria-busy", "true");

    try {
      const report = await api("/reports/lot");
      if (request !== state.reportRequest) return;
      renderReport(report);
    } catch (error) {
      if (request !== state.reportRequest) return;
      els.reportSubtitle.textContent = "—";
      els.reportErrorText.textContent = error.message;
      showReportState("error");
    } finally {
      if (request === state.reportRequest) {
        els.reportDialog.setAttribute("aria-busy", "false");
      }
    }
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function standaloneReportHtml(css) {
    const sheet = els.reportDialog.querySelector(".report-sheet");
    if (!sheet) throw new Error("No se encontró la hoja del informe.");

    const clone = sheet.cloneNode(true);
    clone.querySelectorAll(".report-states").forEach((node) => node.remove());
    clone.querySelectorAll(".report-actions").forEach((node) => node.remove());
    clone.querySelectorAll("button").forEach((button) => {
      const name = document.createElement("span");
      name.className = "report-saved-name";
      name.textContent = button.textContent;
      button.replaceWith(name);
    });

    const title = escapeHtml(els.reportTitle.textContent);
    const subtitle = escapeHtml(els.reportSubtitle.textContent);
    const generated = escapeHtml(new Date().toISOString());

    return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="El Libro de las Hojas">
<meta name="generated-at" content="${generated}">
<title>${title} · ${subtitle}</title>
<style>${css}</style>
<style>
  html { color-scheme: light; }
  body { margin: 0; background: var(--surface); }
  .report-sheet {
    width: min(calc(100% - var(--space-6)), var(--report-width));
    max-width: var(--report-width);
    max-height: none;
    margin: 0 auto;
    overflow: visible;
  }
  .report-saved-name {
    font-family: var(--font-body);
    font-size: var(--text-sm);
    font-weight: 700;
    overflow-wrap: anywhere;
  }
  @media print {
    .report-sheet { width: auto; max-width: none; margin: 0; padding: 0; }
  }
</style>
</head>
<body>
<main class="report-sheet">
${clone.innerHTML}
</main>
</body>
</html>`;
  }

  async function loadReportStyles() {
    const [tokensResponse, stylesResponse] = await Promise.all([
      fetch("tokens.css"),
      fetch("styles.css"),
    ]);
    if (!tokensResponse.ok || !stylesResponse.ok) {
      throw new Error("No se pudieron leer los estilos del informe.");
    }
    const [tokens, styles] = await Promise.all([
      tokensResponse.text(),
      stylesResponse.text(),
    ]);
    return `${tokens}\n${styles}`;
  }

  async function saveReport() {
    if (els.reportBody.hidden || els.reportSave.disabled) return;
    els.reportSave.disabled = true;
    els.reportSaveStatus.textContent = "Preparando la copia…";

    try {
      const css = await loadReportStyles();
      const html = standaloneReportHtml(css);
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const filename = `informe-lote-${new Date().toISOString().slice(0, 10)}.html`;
      let saved = false;

      if (typeof window.showSaveFilePicker === "function") {
        try {
          const handle = await window.showSaveFilePicker({
            suggestedName: filename,
            types: [
              {
                description: "Página HTML del informe",
                accept: { "text/html": [".html"] },
              },
            ],
          });
          const writable = await handle.createWritable();
          await writable.write(blob);
          await writable.close();
          saved = true;
        } catch (error) {
          if (error && error.name === "AbortError") {
            els.reportSaveStatus.textContent = "";
            return;
          }
          // Si el selector nativo falla, se intenta la descarga del navegador.
        }
      }

      if (!saved) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.rel = "noopener";
        document.body.append(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      }

      els.reportSaveStatus.textContent = "Copia guardada en esta computadora.";
      announce("Informe guardado en esta computadora.");
    } catch (error) {
      els.reportSaveStatus.textContent = `No se pudo guardar: ${error.message}`;
    } finally {
      els.reportSave.disabled = els.reportBody.hidden;
    }
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, options);
    if (response.status === 204) return null;

    // Una sesión vencida no es un error de datos: se vuelve a la puerta. Las
    // rutas de /auth quedan afuera para que sus propios 401 se lean como son.
    if (response.status === 401 && !path.startsWith("/auth/")) {
      state.auth.user = null;
      renderSession();
      openLogin("La sesión terminó. Volvé a entrar.");
      throw new Error("Hace falta iniciar sesión.");
    }

    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    const body = isJson ? await response.json() : null;

    if (!response.ok) {
      const detail = body && body.detail;
      let message = `Error ${response.status}.`;
      let code = "";
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        message = detail.message || message;
        code = detail.code ? ` (${detail.code})` : "";
      }
      throw new Error(message + code);
    }
    return body;
  }

  // -- sesión (ADR-017) ---------------------------------------------------

  function renderSession() {
    const user = state.auth.user;
    els.session.hidden = !user;
    // La conserjería y el filtro por dueño son cosas de administración: el
    // operador no ve la lista de la base (ADR-018).
    const admin = Boolean(user && user.role === "admin");
    els.usersOpen.hidden = !admin;
    els.filterOwnerField.hidden = !admin;
    if (!user) return;
    els.sessionName.textContent = user.display_name || user.username;
    els.sessionRole.textContent = user.role === "admin" ? "administrador" : "operador";
  }

  function openLogin(message = "") {
    els.loginError.textContent = message;
    els.loginError.hidden = !message;
    if (!state.auth.required || els.login.open) return;
    els.loginPassword.value = "";
    els.login.showModal();
    els.loginUser.focus();
  }

  async function submitLogin(event) {
    event.preventDefault();
    const username = els.loginUser.value.trim();
    const password = els.loginPassword.value;
    if (!username || !password) return;

    els.loginSubmit.disabled = true;
    els.loginError.hidden = true;
    try {
      const user = await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      state.auth.user = user;
      state.auth.required = true;
      els.loginPassword.value = "";
      els.login.close();
      renderSession();
      announce(`Sesión iniciada como ${user.display_name || user.username}.`);
      // El catálogo falló sin sesión al arrancar: ahora sí se puede leer.
      await Promise.all([loadThresholds(), refreshArchive()]);
    } catch (error) {
      els.loginError.textContent = error.message;
      els.loginError.hidden = false;
      els.loginPassword.select();
    } finally {
      els.loginSubmit.disabled = false;
    }
  }

  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch (error) {
      // Si la sesión ya no existía, el resultado es el mismo: se cierra igual.
      console.warn("No se pudo cerrar la sesión en el servidor:", error);
    }
    state.auth.user = null;
    state.current = null;
    state.page = 0;
    state.hasMore = false;
    // El catálogo y los ajustes no se heredan entre usuarios: sin sesión,
    // el panel no tiene qué mostrar.
    state.tuning.catalogue = [];
    state.tuning.values = {};
    renderTuning();
    // El próximo que entre empieza sin los filtros del anterior.
    state.filters = { q: "", version: "", owner: "", unassigned: false };
    els.filterQ.value = "";
    els.result.hidden = true;
    if (els.usersDialog.open) els.usersDialog.close();
    renderSession();
    renderLedger([]);
    els.filterVersion.replaceChildren();
    els.filterOwner.replaceChildren();
    openLogin();
  }

  async function loadSession() {
    try {
      const me = await api("/auth/me");
      state.auth.required = Boolean(me.auth_required);
      state.auth.user = me.user || null;
    } catch (error) {
      console.warn("No se pudo leer /api/auth/me:", error);
    }
    renderSession();
  }

  function setHealth(stateName, text) {
    els.health.dataset.state = stateName;
    els.healthText.textContent = text;
  }

  function showError(message) {
    els.alertMessage.textContent = message;
    els.alert.hidden = false;
    announce(`Error: ${message}`);
  }

  function clearError() {
    els.alert.hidden = true;
    els.alertMessage.textContent = "";
  }

  function filtersActive() {
    const { q, version, owner, unassigned } = state.filters;
    return Boolean(q || version || owner || unassigned);
  }

  function updateClear() {
    // Con un filtro puesto, «Limpiar» borraría más de lo que se ve.
    const filtered = filtersActive();
    const admin = Boolean(state.auth.user && state.auth.user.role === "admin");
    els.clearArchive.disabled = state.busy || state.items.length === 0 || filtered;
    els.clearArchive.title = filtered
      ? "Quitá el filtro para vaciar el archivo entero."
      : admin
        ? "Elimina todas las inspecciones del almanaque."
        : "Elimina todas tus inspecciones.";
  }

  function setBusy(busy, text = "Analizando la hoja…") {
    state.busy = busy;
    els.status.hidden = !busy;
    els.statusText.textContent = text;
    els.pick.disabled = busy;
    els.input.disabled = busy;
    updateClear();
    els.dropzone.setAttribute("aria-busy", String(busy));
    document.body.toggleAttribute("data-busy", busy);
    // «Repetir» no puede dispararse mientras corre algo.
    if (els.tuningApply) updateTuning();
  }

  function metric(label, value, unit, formatter = format.num) {
    const article = document.createElement("article");
    article.className = "metric";

    const labelEl = document.createElement("p");
    labelEl.className = "metric-label";
    labelEl.textContent = label;

    const valueEl = document.createElement("p");
    valueEl.className = "metric-value";
    valueEl.textContent = formatter(value);

    const unitEl = document.createElement("p");
    unitEl.className = "metric-unit";
    unitEl.textContent = unit;

    article.append(labelEl, valueEl, unitEl);
    return article;
  }

  function renderMetrics(record) {
    const items = [
      metric("Área afectada", record.lesions.area_fraction, "de la superficie válida", format.pct),
      metric("Lesiones", record.lesions.count, "componentes", format.int),
      metric("Feret máximo", record.lesions.max_feret_px, "px", format.num),
      metric("Circularidad media", record.lesions.mean_circularity, "0 – 1", format.num),
      metric("Nervadura", record.lesions.vein_density, "de la superficie", format.pct),
      metric("Nitidez", record.quality.sharpness, "varianza del laplaciano", format.num)
    ];
    if (record.chlorosis) {
      // La clorosis es parte de lo afectado, no área nueva: por eso va pegada
      // al área afectada y no se suma a ella.
      items.splice(
        1,
        0,
        metric("Clorosis", record.chlorosis.area_fraction, "de la superficie válida", format.pct)
      );
    }
    els.metrics.replaceChildren(...items);
  }

  function layerCard(step, layer, url) {
    const item = document.createElement("li");
    item.className = "layer";

    const figure = document.createElement("figure");
    figure.className = "layer-figure";

    const frame = document.createElement("a");
    frame.className = "layer-frame";
    frame.href = url;
    frame.target = "_blank";
    frame.rel = "noopener";
    frame.title = `Abrir la capa «${layer.title}» a tamaño completo`;

    const image = document.createElement("img");
    image.src = url;
    image.alt = `Capa ${step} · ${layer.title}: ${layer.caption}`;
    image.loading = "lazy";
    frame.append(image);

    const caption = document.createElement("figcaption");
    caption.className = "layer-caption";

    const head = document.createElement("p");
    head.className = "layer-head";
    const number = document.createElement("span");
    number.className = "layer-step";
    number.textContent = String(step).padStart(2, "0");
    const title = document.createElement("span");
    title.className = "layer-title";
    title.textContent = layer.title || "Capa";
    head.append(number, title);

    const text = document.createElement("p");
    text.className = "layer-text";
    text.textContent = layer.caption || "";

    const meta = document.createElement("p");
    meta.className = "layer-meta";
    const stage = STAGE_LABELS[layer.stage] || String(layer.stage || "").replaceAll("_", " ");
    const size =
      layer.width && layer.height
        ? `${format.int(layer.width)} × ${format.int(layer.height)} px`
        : "";
    meta.textContent = [stage, size].filter(Boolean).join(" · ");

    caption.append(head, text, meta);
    figure.append(frame, caption);
    item.append(figure);
    return item;
  }

  function renderLayers(record) {
    const trace = record.trace || {};
    const specs = Array.isArray(trace.layers) ? trace.layers : [];
    const urls = record.layer_urls || {};
    const cards = [
      layerCard(
        1,
        {
          title: "Imagen de entrada",
          stage: "entrada",
          caption:
            "El archivo tal como se subió, sin recortes ni correcciones. Todo lo que sigue se aplica sobre esta toma.",
          width: record.image.width,
          height: record.image.height,
        },
        record.original_url
      ),
    ];

    specs.forEach((layer) => {
      const url = urls[layer.key];
      if (url) cards.push(layerCard(cards.length + 1, layer, url));
    });

    els.layers.hidden = cards.length <= 1;
    els.layerList.replaceChildren(...cards);
  }

  function markCurrent(id) {
    els.ledgerList.querySelectorAll(".ledger-load").forEach((button) => {
      if (button.dataset.id === id) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    });
  }

  function renderResult(record) {
    state.current = record;
    els.result.hidden = false;
    els.resultTitle.textContent = record.image.filename;
    const isolation = record.trace && record.trace.isolation;
    const analysis = isolation && isolation.analysis;
    const cropped =
      analysis &&
      (analysis.width !== record.image.width || analysis.height !== record.image.height);
    const sizeText = cropped
      ? `${record.image.width} × ${record.image.height} px · hoja aislada ` +
        `${analysis.width} × ${analysis.height} px`
      : `${record.image.width} × ${record.image.height} px`;
    // Procedencia: versión del software y quién la subió (ADR-017).
    const version = record.app_version ? ` · v${record.app_version}` : "";
    const owner = record.owner ? ` · ${record.owner.display_name || record.owner.username}` : "";
    els.resultMeta.textContent =
      `#${record.id.slice(0, 10)} · ${sizeText} · ` +
      `${record.image.format} · ${formatDate(record.created_at)}${version}${owner}`;

    const usable = record.quality.usable;
    els.seal.className = `seal ${usable ? "seal--ok" : "seal--warn"}`;
    els.sealWord.textContent = usable ? "Analizable" : "Con reservas";

    const flags = record.quality.flags || [];
    els.verdictNote.textContent = flags.length
      ? `Advertencias de calidad: ${flags.join(", ")}.`
      : "Sin advertencias de calidad. La máscara muestra las lesiones detectadas sobre la hoja analizada.";

    renderMetrics(record);
    els.overlay.src = record.result_url;
    els.overlay.alt =
      `Hoja ${record.image.filename} con ${record.lesions.count} lesiones marcadas en óxido ` +
      "y nervaduras en oro.";
    renderLayers(record);
    // El panel se sincroniza con lo que midió esta corrida, no con lo que
    // quedó del intento anterior.
    syncTuning(record);
    els.trace.textContent = JSON.stringify(record.trace, null, 2);
    els.originalLink.href = record.original_url;
    els.deleteCurrent.dataset.id = record.id;
    els.deleteCurrent.dataset.name = record.image.filename;

    markCurrent(record.id);
    els.result.scrollIntoView({
      behavior: reducedMotion.matches ? "auto" : "smooth",
      block: "start",
    });
  }

  function option(value, label) {
    const node = document.createElement("option");
    node.value = value;
    node.textContent = label;
    return node;
  }

  function renderLedger(items) {
    state.items = items;
    els.ledgerList.replaceChildren();

    const total = items.length;
    const filtered = filtersActive();
    els.ledgerCount.textContent =
      total === 0
        ? filtered
          ? "sin coincidencias"
          : "sin inspecciones"
        : `${total} ${total === 1 ? "inspección" : "inspecciones"}` +
          (state.hasMore ? " · hay más" : "");
    els.ledgerEmpty.hidden = total > 0;
    els.ledgerEmpty.textContent = filtered
      ? "Ninguna hoja coincide con el filtro."
      : "La huerta espera su primera hoja.";
    els.ledgerMore.hidden = !state.hasMore;
    updateClear();

    items.forEach((record) => {
      const item = document.createElement("li");
      item.className = "ledger-item";

      const load = document.createElement("button");
      load.type = "button";
      load.className = "ledger-load";
      load.dataset.id = record.id;
      load.setAttribute("aria-label", `Abrir la inspección de ${record.image.filename}`);

      const thumb = document.createElement("img");
      thumb.src = record.result_url;
      thumb.alt = "";
      thumb.loading = "lazy";
      thumb.width = 48;
      thumb.height = 48;

      const text = document.createElement("span");
      text.className = "ledger-text";
      const name = document.createElement("strong");
      name.textContent = record.image.filename;
      name.title = record.image.filename;
      const meta = document.createElement("span");
      // Fecha, severidad y quién subió la hoja (ADR-017).
      const parts = [formatDate(record.created_at), format.pct(record.lesions.area_fraction)];
      if (record.owner) parts.push(record.owner.display_name || record.owner.username);
      meta.textContent = parts.join(" · ");

      const tags = document.createElement("span");
      tags.className = "ledger-tags";
      if (record.app_version) {
        const badge = document.createElement("span");
        badge.className = "badge-version";
        badge.textContent = `v${record.app_version}`;
        badge.title = record.method_version
          ? `Medida con la versión ${record.app_version} · método ${record.method_version}`
          : `Medida con la versión ${record.app_version}`;
        tags.append(badge);
      }

      text.append(name, meta);
      if (tags.childElementCount) text.append(tags);
      load.append(thumb, text);

      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "ledger-delete";
      remove.dataset.id = record.id;
      remove.dataset.name = record.image.filename;
      remove.setAttribute("aria-label", `Eliminar la inspección de ${record.image.filename}`);
      remove.textContent = "×";

      item.append(load, remove);
      els.ledgerList.append(item);
    });
  }

  function historyQuery() {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (state.filters.q) params.set("q", state.filters.q);
    if (state.filters.version) params.set("version", state.filters.version);
    if (state.filters.owner) params.set("owner", state.filters.owner);
    if (state.filters.unassigned) params.set("unassigned", "true");
    if (state.page) params.set("offset", String(state.page * PAGE_SIZE));
    return params.toString();
  }

  async function loadLedger() {
    try {
      const items = await api(`/inspections?${historyQuery()}`);
      // Una página llena puede no ser la última: el botón «más» lo comprueba.
      state.hasMore = items.length === PAGE_SIZE;
      renderLedger(state.page ? state.items.concat(items) : items);
    } catch (error) {
      showError(`No se pudo leer el archivo: ${error.message}`);
    }
  }

  async function loadMore() {
    if (!state.hasMore || state.busy) return;
    state.page += 1;
    await loadLedger();
    announce(`${state.items.length} inspecciones en el archivo.`);
  }

  function applyFilters() {
    state.page = 0;
    loadLedger();
  }

  async function loadVersions() {
    let versions = [];
    try {
      versions = await api("/versions");
    } catch (error) {
      // Sin versiones el filtro queda vacío, pero el archivo se sigue leyendo.
      console.warn("No se pudo leer /api/versions:", error);
    }
    state.versions = versions || [];
    const current = state.filters.version;
    els.filterVersion.replaceChildren(
      option("", "todas"),
      ...state.versions.map((item) =>
        option(item.version, `${item.version} · ${format.int(item.inspections)}`)
      )
    );
    els.filterVersion.value = current;
  }

  async function loadUsers() {
    const me = state.auth.user;
    const admin = Boolean(me && me.role === "admin");
    let users = [];
    if (me) {
      try {
        // Solo el administrador ve la lista completa de la base.
        users = admin ? await api("/auth/users") : [me];
      } catch (error) {
        console.warn("No se pudo leer la lista de usuarios:", error);
        users = [me];
      }
    }
    state.users = users;
    const options = [
      option("", "todos"),
      ...state.users.map((user) => option(user.username, user.display_name || user.username)),
    ];
    // Las hojas huérfanas solo las puede pedir el administrador (ADR-018).
    if (admin) options.push(option(UNASSIGNED, "sin dueño"));
    const current = state.filters.unassigned ? UNASSIGNED : state.filters.owner;
    els.filterOwner.replaceChildren(...options);
    els.filterOwner.value = current;
    if (els.filterOwner.value !== current) {
      // El dueño filtrado ya no existe: se vuelve a todo el archivo.
      state.filters.owner = "";
      state.filters.unassigned = false;
      els.filterOwner.value = "";
    }
  }

  async function refreshArchive() {
    await Promise.all([loadVersions(), loadUsers()]);
    await loadLedger();
  }

  // -- conserjería (ADR-018) ---------------------------------------------

  function showUsersError(message = "") {
    els.usersError.textContent = message;
    els.usersError.hidden = !message;
  }

  async function openUsers() {
    const me = state.auth.user;
    if (!me || me.role !== "admin" || els.usersDialog.open) return;
    showUsersError("");
    els.userForm.reset();
    await loadUserRows();
    els.usersDialog.showModal();
    els.userUsername.focus();
  }

  async function loadUserRows() {
    let users = [];
    try {
      users = await api("/auth/users");
    } catch (error) {
      showUsersError(`No se pudo leer la lista: ${error.message}`);
    }
    const me = state.auth.user;
    els.usersList.replaceChildren(...users.map((user) => userRow(user, me)));
  }

  function userRow(user, me) {
    const row = document.createElement("li");
    row.className = "user-row";

    const who = document.createElement("span");
    who.className = "user-who";
    const name = document.createElement("span");
    name.className = "user-name";
    name.textContent = user.display_name || user.username;
    const handle = document.createElement("span");
    handle.className = "user-handle";
    handle.textContent = `@${user.username}`;
    who.append(name, handle);

    const role = document.createElement("span");
    role.className = "user-role";
    role.dataset.role = user.role;
    role.textContent = user.role === "admin" ? "administrador" : "operador";
    row.append(who, role);

    if (me && user.id === me.id) {
      // La propia cuenta no se da de baja: siempre queda un administrador.
      const self = document.createElement("span");
      self.className = "user-handle";
      self.textContent = "tu cuenta";
      row.append(self);
      return row;
    }

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "user-delete";
    remove.dataset.id = user.id;
    remove.dataset.name = user.display_name || user.username;
    remove.setAttribute("aria-label", `Dar de baja a ${user.display_name || user.username}`);
    remove.textContent = "×";
    row.append(remove);
    return row;
  }

  async function submitUser(event) {
    event.preventDefault();
    const username = els.userUsername.value.trim();
    const password = els.userPassword.value;
    if (!username || !password) return;

    showUsersError("");
    els.userSubmit.disabled = true;
    try {
      const created = await api("/auth/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          password,
          display_name: els.userDisplay.value.trim(),
          role: els.userRole.value,
        }),
      });
      els.userForm.reset();
      await loadUserRows();
      await refreshArchive();
      announce(`Usuario ${created.username} agregado.`);
    } catch (error) {
      showUsersError(`No se pudo agregar: ${error.message}`);
    } finally {
      els.userSubmit.disabled = false;
    }
  }

  function askDeleteUser(id, name) {
    if (!id) return;
    state.pendingDelete = null;
    state.pendingClear = false;
    state.pendingOrphans = false;
    state.pendingUser = { id, name };
    els.confirmTitle.textContent = "¿Dar de baja el usuario?";
    els.confirmAccept.textContent = "Dar de baja";
    els.confirmText.textContent =
      `Se borra la cuenta de “${name}”. Sus hojas quedan en el almanaque, sin dueño, y se pueden eliminar desde esta misma conserjería. No se puede deshacer.`;
    openConfirm();
  }

  async function deleteUser(id, name) {
    try {
      await api(`/auth/users/${encodeURIComponent(id)}`, { method: "DELETE" });
      await loadUserRows();
      await refreshArchive();
      announce(`Usuario ${name} dado de baja.`);
    } catch (error) {
      showUsersError(`No se pudo dar de baja: ${error.message}`);
    }
  }

  async function askPurgeOrphans() {
    showUsersError("");
    let found = [];
    try {
      // Una sola hoja alcanza para saber si hay algo que borrar.
      found = await api("/inspections?unassigned=true&limit=1");
    } catch (error) {
      showUsersError(`No se pudo revisar el archivo: ${error.message}`);
      return;
    }
    if (!found.length) {
      announce("No hay hojas sin dueño.");
      return;
    }
    state.pendingDelete = null;
    state.pendingClear = false;
    state.pendingUser = null;
    state.pendingOrphans = true;
    els.confirmTitle.textContent = "¿Borrar las hojas sin dueño?";
    els.confirmAccept.textContent = "Borrar hojas";
    els.confirmText.textContent =
      "Se eliminarán las hojas que quedaron sin cuenta —las de usuarios dados de baja y las que nunca tuvieron dueño— con sus originales y medidas. No se puede deshacer.";
    openConfirm();
  }

  async function purgeOrphans() {
    try {
      await api("/inspections?unassigned=true", { method: "DELETE" });
      await refreshArchive();
      announce("Hojas sin dueño eliminadas.");
    } catch (error) {
      showUsersError(`No se pudieron borrar: ${error.message}`);
    }
  }

  async function selectInspection(id) {
    if (state.busy) return;
    try {
      const record = await api(`/inspections/${encodeURIComponent(id)}`);
      renderResult(record);
    } catch (error) {
      showError(`No se pudo abrir la inspección: ${error.message}`);
      await loadLedger();
    }
  }

  async function upload(file, tuning = {}) {
    if (!file || state.busy) return;
    clearError();

    if (!["image/png", "image/jpeg"].includes(file.type)) {
      showError("Seleccioná un archivo PNG o JPEG.");
      return;
    }
    if (file.size > state.maxUploadBytes) {
      const megabytes = Math.round(state.maxUploadBytes / (1024 * 1024));
      showError(`La imagen supera el máximo de ${megabytes} MB.`);
      return;
    }

    setBusy(true, `Analizando ${file.name}…`);
    try {
      const body = new FormData();
      body.append("file", file, file.name);
      // El ajuste viaja al lado del archivo; vacío significa «los defectos»
      // (ADR-022). Como campo hermano no hace falta reserializar la imagen.
      if (Object.keys(tuning).length) body.append("tuning", JSON.stringify(tuning));
      const record = await api("/inspections", { method: "POST", body });
      renderResult(record);
      await refreshArchive();
      announce(`Inspección completada: ${record.lesions.count} lesiones detectadas.`);
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(false);
      els.input.value = "";
    }
  }

  function openConfirm() {
    els.dialog.returnValue = "";
    if (typeof els.dialog.showModal === "function") els.dialog.showModal();
  }

  function askDelete(id, name) {
    if (!id) return;
    state.pendingDelete = id;
    state.pendingClear = false;
    els.confirmTitle.textContent = "¿Eliminar esta inspección?";
    els.confirmAccept.textContent = "Eliminar";
    els.confirmText.textContent =
      `Se eliminará “${name}” con su original, su resultado y sus medidas. No se puede deshacer.`;
    openConfirm();
  }

  function askClear() {
    const total = state.items.length;
    if (!total) return;
    const admin = Boolean(state.auth.user && state.auth.user.role === "admin");
    const where = admin ? "del almanaque" : "de tu archivo";
    state.pendingDelete = null;
    state.pendingClear = true;
    state.pendingOrphans = false;
    state.pendingUser = null;
    els.confirmTitle.textContent = "¿Vaciar el archivo?";
    els.confirmAccept.textContent = "Vaciar archivo";
    els.confirmText.textContent =
      total === 1
        ? `Se eliminará la única inspección ${where}, con su original, resultado y medidas. No se puede deshacer.`
        : `Se eliminarán las ${total} inspecciones ${where}, con sus originales, resultados y medidas. No se puede deshacer.`;
    openConfirm();
  }

  async function deleteInspection(id) {
    try {
      await api(`/inspections/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (state.current && state.current.id === id) {
        state.current = null;
        els.result.hidden = true;
      }
      await refreshArchive();
      announce("Inspección eliminada.");
    } catch (error) {
      showError(`No se pudo eliminar: ${error.message}`);
    }
  }

  async function clearArchive() {
    if (state.busy) return;
    clearError();
    setBusy(true, "Vaciando el almanaque…");
    try {
      await api("/inspections", { method: "DELETE" });
      state.current = null;
      els.result.hidden = true;
      markCurrent("");
      await refreshArchive();
      announce("Almanaque vaciado. No quedan inspecciones.");
    } catch (error) {
      showError(`No se pudo vaciar el almanaque: ${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function loadConfig() {
    try {
      const config = await api("/config");
      state.auth.required = Boolean(config.auth_required);
      if (typeof config.max_upload_bytes === "number") {
        state.maxUploadBytes = config.max_upload_bytes;
      }
      if (Array.isArray(config.allowed_formats) && config.allowed_formats.length) {
        state.allowedFormats = config.allowed_formats;
      }
      const megabytes = Math.round(state.maxUploadBytes / (1024 * 1024));
      els.dropHint.textContent =
        `${state.allowedFormats.join(" o ")} · hasta ${megabytes} MB · ` +
        "la imagen se analiza en este equipo y queda en el archivo local.";
    } catch (error) {
      // El servidor vuelve a validar; el límite por defecto alcanza para seguir.
      console.warn("No se pudo leer /api/config:", error);
    }
  }

  // -- umbrales (ADR-022) -------------------------------------------------

  function tuningReadout(parameter, value) {
    const text = parameter.integer ? String(Math.round(value)) : numberFormat.format(value);
    return parameter.unit ? `${text} ${parameter.unit}` : text;
  }

  function tuningField(parameter, value) {
    const field = document.createElement("div");
    field.className = "tuning-field";
    if (Math.abs(value - parameter.default) > 1e-9) field.classList.add("is-changed");

    const label = document.createElement("label");
    label.className = "tuning-label";
    label.htmlFor = `tuning-${parameter.key}`;
    label.textContent = parameter.label;

    const readout = document.createElement("output");
    readout.className = "tuning-value";
    readout.htmlFor = `tuning-${parameter.key}`;
    readout.textContent = tuningReadout(parameter, value);

    const input = document.createElement("input");
    input.type = "range";
    input.id = `tuning-${parameter.key}`;
    input.dataset.key = parameter.key;
    input.min = String(parameter.min);
    input.max = String(parameter.max);
    input.step = String(parameter.integer ? 1 : parameter.step);
    input.value = String(value);

    const help = document.createElement("p");
    help.className = "tuning-help";
    help.textContent = parameter.help;

    field.append(label, readout, input, help);
    return field;
  }

  function renderTuning() {
    const { catalogue, values } = state.tuning;
    if (!catalogue.length) {
      els.tuningPanel.hidden = true;
      return;
    }
    els.tuningPanel.hidden = false;

    const nodes = [];
    let group = "";
    catalogue.forEach((parameter) => {
      if (parameter.group !== group) {
        group = parameter.group;
        const heading = document.createElement("p");
        heading.className = "tuning-group";
        heading.textContent = group;
        nodes.push(heading);
      }
      nodes.push(tuningField(parameter, values[parameter.key] ?? parameter.default));
    });
    els.tuningGrid.replaceChildren(...nodes);
    updateTuning();
  }

  // Lo que viaja: solo los valores distintos del defecto, para que el registro
  // no arrastre el catálogo entero ni el trace se llene de valores repetidos.
  function tuningPayload() {
    const moved = {};
    state.tuning.catalogue.forEach((parameter) => {
      const value = state.tuning.values[parameter.key];
      if (value === undefined || value === null) return;
      if (Math.abs(value - parameter.default) > 1e-9) moved[parameter.key] = value;
    });
    return moved;
  }

  function sameTuning(left, right) {
    const shape = (tuning) =>
      Object.keys(tuning)
        .sort()
        .map((key) => `${key}=${tuning[key]}`)
        .join("|");
    return shape(left) === shape(right);
  }

  function updateTuning() {
    if (!els.tuningApply) return;
    const payload = tuningPayload();
    const moved = Object.keys(payload).length;
    els.tuningBadge.hidden = moved === 0;
    els.tuningBadge.textContent = moved
      ? `${moved} ${moved === 1 ? "ajuste" : "ajustes"}`
      : "";
    const applied = state.current && state.current.trace ? state.current.trace.tuning || {} : {};
    // «Repetir» solo cuando hay una hoja cargada y el ajuste difiere del que la
    // midió: repetir lo mismo daría un registro gemelo.
    els.tuningApply.disabled = !state.current || state.busy || sameTuning(payload, applied);
  }

  function syncTuning(record) {
    const applied = (record && record.trace && record.trace.tuning) || {};
    const values = { ...state.tuning.defaults };
    Object.keys(applied).forEach((key) => {
      // Una clave que ya no está en el catálogo no puede mover un deslizador.
      if (key in values) values[key] = applied[key];
    });
    state.tuning.values = values;
    if (state.tuning.catalogue.length) renderTuning();
  }

  function resetTuning() {
    state.tuning.values = { ...state.tuning.defaults };
    els.tuningStatus.textContent = "";
    renderTuning();
  }

  async function loadThresholds() {
    try {
      const data = await api("/thresholds");
      state.tuning.catalogue = Array.isArray(data.parameters) ? data.parameters : [];
      state.tuning.defaults = data.defaults || {};
      state.tuning.values = { ...state.tuning.defaults };
      renderTuning();
    } catch (error) {
      // Sin catálogo la pantalla sigue analizando con los defectos del servidor:
      // el panel se esconde y nadie pierde la subida.
      console.warn("No se pudo leer /api/thresholds:", error);
      if (els.tuningPanel) els.tuningPanel.hidden = true;
    }
  }

  async function repeatAnalysis() {
    const record = state.current;
    if (!record || state.busy) return;
    const payload = tuningPayload();
    const before = record.id;
    clearError();
    els.tuningStatus.textContent = "";

    let file;
    setBusy(true, "Trayendo la hoja original…");
    try {
      // La hoja que se repite es la original guardada, no el overlay: las dos
      // corridas miden la misma foto y se pueden comparar.
      const response = await fetch(record.original_url, { credentials: "same-origin" });
      if (!response.ok) throw new Error("No se pudo leer la hoja original del archivo.");
      const blob = await response.blob();
      file = new File([blob], record.image.filename, { type: blob.type || "image/png" });
    } catch (error) {
      setBusy(false);
      showError(error.message);
      return;
    }

    setBusy(false);
    await upload(file, payload);
    // Si la corrida falló, ``upload`` ya mostró el motivo y no hay nada que decir.
    if (state.current && state.current.id !== before) {
      const moved = Object.keys(payload).length;
      els.tuningStatus.textContent = moved
        ? `Repetida con ${moved} ${moved === 1 ? "umbral ajustado" : "umbrales ajustados"}; ` +
          "la corrida anterior queda en el archivo."
        : "Repetida con los umbrales por defecto.";
    }
  }

  async function loadHealth() {
    try {
      const health = await api("/health");
      setHealth("ok", `servicio en línea · v${health.version}`);
    } catch {
      setHealth("down", "servicio sin conexión");
    }
  }

  function bindEvents() {
    els.pick.addEventListener("click", (event) => {
      event.stopPropagation();
      if (!state.busy) els.input.click();
    });

    els.dropzone.addEventListener("click", (event) => {
      if (event.target.closest("button") || state.busy) return;
      els.input.click();
    });

    els.input.addEventListener("change", () => {
      const [file] = els.input.files || [];
      if (file) upload(file);
    });

    ["dragenter", "dragover"].forEach((type) => {
      els.dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        if (!state.busy) els.dropzone.classList.add("is-dragover");
      });
    });

    ["dragleave", "dragend"].forEach((type) => {
      els.dropzone.addEventListener(type, () => els.dropzone.classList.remove("is-dragover"));
    });

    els.dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      els.dropzone.classList.remove("is-dragover");
      if (state.busy) return;
      const [file] = event.dataTransfer.files || [];
      if (file) upload(file);
    });

    els.ledgerList.addEventListener("click", (event) => {
      const load = event.target.closest(".ledger-load");
      const remove = event.target.closest(".ledger-delete");
      if (load) selectInspection(load.dataset.id);
      if (remove) askDelete(remove.dataset.id, remove.dataset.name);
    });

    els.deleteCurrent.addEventListener("click", () => {
      askDelete(els.deleteCurrent.dataset.id, els.deleteCurrent.dataset.name);
    });

    els.dialog.addEventListener("close", () => {
      const id = state.pendingDelete;
      const clear = state.pendingClear;
      const orphans = state.pendingOrphans;
      const user = state.pendingUser;
      state.pendingDelete = null;
      state.pendingClear = false;
      state.pendingOrphans = false;
      state.pendingUser = null;
      if (els.dialog.returnValue !== "confirm") return;
      if (clear) clearArchive();
      else if (orphans) purgeOrphans();
      else if (user) deleteUser(user.id, user.name);
      else if (id) deleteInspection(id);
    });

    els.clearArchive.addEventListener("click", askClear);

    els.logout.addEventListener("click", logout);
    els.loginForm.addEventListener("submit", submitLogin);

    els.usersOpen.addEventListener("click", openUsers);
    els.usersClose.addEventListener("click", () => els.usersDialog.close());
    els.userForm.addEventListener("submit", submitUser);
    els.userRole.addEventListener("change", () => {
      // Crear otro administrador es una decisión explícita: se avisa en el
      // título del botón en vez de bloquearla.
      els.userSubmit.textContent =
        els.userRole.value === "admin" ? "Agregar administrador" : "Agregar usuario";
    });
    els.usersList.addEventListener("click", (event) => {
      const remove = event.target.closest(".user-delete");
      if (remove) askDeleteUser(remove.dataset.id, remove.dataset.name);
    });
    els.clearOrphans.addEventListener("click", askPurgeOrphans);
    // Con base, la puerta no se cierra con Escape hasta que hay sesión.
    els.login.addEventListener("cancel", (event) => {
      if (state.auth.required && !state.auth.user) event.preventDefault();
    });

    // La búsqueda espera a que se termine de escribir; los selectores no.
    let searchTimer = 0;
    els.filterQ.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        state.filters.q = els.filterQ.value.trim();
        applyFilters();
      }, 300);
    });
    els.filterVersion.addEventListener("change", () => {
      state.filters.version = els.filterVersion.value;
      applyFilters();
    });
    els.filterOwner.addEventListener("change", () => {
      const value = els.filterOwner.value;
      // «sin dueño» no es un usuario: pide las hojas sin cuenta detrás.
      state.filters.unassigned = value === UNASSIGNED;
      state.filters.owner = state.filters.unassigned ? "" : value;
      applyFilters();
    });
    els.ledgerMore.addEventListener("click", loadMore);

    // Panel de umbrales (ADR-022): el deslizador solo mueve un valor; repetir
    // el análisis es lo que crea un registro nuevo.
    if (els.tuningGrid) {
      els.tuningGrid.addEventListener("input", (event) => {
        const input = event.target.closest("input[data-key]");
        if (!input) return;
        const parameter = state.tuning.catalogue.find((entry) => entry.key === input.dataset.key);
        if (!parameter) return;
        const value = parameter.integer ? Math.round(Number(input.value)) : Number(input.value);
        state.tuning.values[parameter.key] = value;
        const field = input.closest(".tuning-field");
        if (field) {
          field.classList.toggle("is-changed", Math.abs(value - parameter.default) > 1e-9);
          const readout = field.querySelector(".tuning-value");
          if (readout) readout.textContent = tuningReadout(parameter, value);
        }
        els.tuningStatus.textContent = "";
        updateTuning();
      });
      els.tuningReset.addEventListener("click", resetTuning);
      els.tuningApply.addEventListener("click", repeatAnalysis);
    }

    els.refresh.addEventListener("click", async () => {
      els.refresh.disabled = true;
      await refreshArchive();
      els.refresh.disabled = false;
    });

    els.reportOpen.addEventListener("click", openReport);

    els.reportSave.addEventListener("click", saveReport);

    els.reportPrint.addEventListener("click", () => window.print());

    els.reportRows.addEventListener("click", (event) => {
      const open = event.target.closest(".report-open");
      if (!open) return;
      const id = open.dataset.id;
      if (!id) return;
      els.reportDialog.close();
      selectInspection(id);
    });

    els.reportDialog.addEventListener("close", () => {
      state.reportRequest += 1;
      els.reportSaveStatus.textContent = "";
      els.reportDialog.setAttribute("aria-busy", "false");
    });
  }

  async function init() {
    bindEvents();
    await Promise.all([loadHealth(), loadConfig()]);
    // Con base hay que entrar antes de leer el archivo; sin base, la demo sigue
    // abierta y no hay puerta que cruzar (ADR-017).
    await loadSession();
    if (state.auth.required && !state.auth.user) {
      openLogin();
      return;
    }
    // El catálogo lo sirve una ruta con sesión (ADR-017): se pide recién cuando
    // ya hay quién la tenga. Pedirlo antes del login devolvía 401 y el panel
    // quedaba escondido para siempre, aunque después se entrara.
    await Promise.all([loadThresholds(), refreshArchive()]);
  }

  init();
})();
