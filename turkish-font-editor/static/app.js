(() => {
  "use strict";

  const state = {
    sessionId: null,
    fontInfo: null,
    chars: {}, // char -> { status, label, codepoint, recipe, originalRecipe, warnings, include, open }
  };

  const STATUS_LABEL = {
    present: "Zaten Mevcut",
    existing_unmapped: "Fontta Var (Eşlenecek)",
    composable: "Otomatik Oluşturulacak",
    composable_synthetic: "Oluşturulacak (Sentetik Aksan)",
    needs_attention: "Dikkat Gerekiyor",
  };
  const STATUS_DOT_COLOR = {
    present: "#2f7d4f",
    existing_unmapped: "#3a5ba0",
    composable: "#3a5ba0",
    composable_synthetic: "#a5680c",
    needs_attention: "#b23a3a",
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  // ---------------------------------------------------------------- upload

  const dropzone = $("#dropzone");
  const fileInput = $("#fileInput");
  const browseBtn = $("#browseBtn");
  const uploadError = $("#uploadError");

  browseBtn.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("click", (e) => {
    if (e.target === browseBtn) return;
    fileInput.click();
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) handleFile(fileInput.files[0]);
  });
  ["dragenter", "dragover"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    })
  );
  dropzone.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  });

  $("#newFontBtn").addEventListener("click", () => {
    if (state.sessionId) {
      fetch(`/api/session/${state.sessionId}`, { method: "DELETE" }).catch(() => {});
    }
    state.sessionId = null;
    state.chars = {};
    $("#workspace").classList.add("hidden");
    $("#uploadSection").classList.remove("hidden");
    $("#newFontBtn").classList.add("hidden");
    $("#fontInfoBadge").classList.add("hidden");
    fileInput.value = "";
  });

  async function handleFile(file) {
    uploadError.classList.add("hidden");
    if (!/\.(ttf|otf)$/i.test(file.name)) {
      showUploadError("Lütfen .ttf ya da .otf uzantılı bir dosya seçin.");
      return;
    }
    const fd = new FormData();
    fd.append("font", file);
    dropzone.classList.add("dragover");
    dropzone.querySelector(".dropzone-title").textContent = "Yükleniyor...";
    try {
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Yükleme başarısız.");
      onUploaded(data);
    } catch (err) {
      showUploadError(err.message);
    } finally {
      dropzone.classList.remove("dragover");
      dropzone.querySelector(".dropzone-title").textContent = "TTF veya OTF font dosyanızı buraya sürükleyin";
    }
  }

  function showUploadError(msg) {
    uploadError.textContent = msg;
    uploadError.classList.remove("hidden");
  }

  function onUploaded(data) {
    state.sessionId = data.session_id;
    state.fontInfo = data.font_info;
    state.chars = {};
    for (const c of data.chars) {
      state.chars[c.char] = {
        status: c.status,
        label: c.label,
        codepoint: c.codepoint,
        recipe: c.recipe,
        originalRecipe: JSON.parse(JSON.stringify(c.recipe)),
        warnings: c.warnings,
        include: c.status !== "needs_attention" || !!c.recipe.base_glyph,
        open: false,
      };
    }

    $("#uploadSection").classList.add("hidden");
    $("#workspace").classList.remove("hidden");
    $("#newFontBtn").classList.remove("hidden");
    $("#subsetSuccessBanner").classList.add("hidden");
    const badge = $("#fontInfoBadge");
    badge.textContent = `${data.font_info.family_name} · ${data.font_info.format}`;
    badge.classList.remove("hidden");

    renderFontWarningBanner();
    renderSidebarInfo();
    renderCharList();
    prefetchAllPreviews();
  }

  function renderFontWarningBanner() {
    const info = state.fontInfo;
    const banner = $("#fontWarningBanner");
    if (!info.has_basic_latin) {
      banner.innerHTML =
        "<strong class=\"banner-title\">Bu font temel Latin harfleri içermiyor</strong>" +
        "Muhtemelen bir ikon/sembol fontu (ör. Font Awesome). Türkçe karakterler mevcut harf " +
        "tasarımlarından türetildiği için, hiç harf içermeyen bir fontta otomatik oluşturma yapılamaz " +
        "— aşağıdaki karakterler bu yüzden \"Dikkat Gerekiyor\" olarak işaretli.";
      banner.classList.remove("hidden");
    } else if (info.glyphs_remaining < info.chars_needing_new_glyphs) {
      const needed = info.chars_needing_new_glyphs;
      const remaining = info.glyphs_remaining;
      let msg;
      if (remaining === 0) {
        msg =
          "<strong class=\"banner-title\">Font glyph kapasitesi dolu</strong>" +
          `Bu font zaten OpenType formatının izin verdiği azami 65.535 glyph'in tamamını kullanıyor ` +
          `(${info.num_glyphs.toLocaleString("tr-TR")}/65.535), hiç boş yer yok. Yeni çizim gerektiren ` +
          `${needed} karakterin hiçbiri eklenemeyecek (fontta zaten bulunanlar bundan etkilenmez).`;
      } else {
        const missing = needed - remaining;
        msg =
          "<strong class=\"banner-title\">Font glyph kapasitesi yetersiz</strong>" +
          `Yeni glyph için yalnızca ${remaining} yer kaldı, ama ${needed} karakter yeni çizim gerektiriyor ` +
          `— ${missing} tanesi sığmayacak.`;
      }
      banner.innerHTML = msg + renderSubsetToolHtml();
      banner.classList.remove("hidden");
      wireSubsetTool(banner);
    } else {
      banner.classList.add("hidden");
    }
  }

  function renderSubsetToolHtml() {
    return `
      <div class="subset-tool">
        <p>Yer açmak için fontu subset edebilirsiniz: kullanılmayan glyph'leri kaldırır,
        Türkçe kompozisyon için gereken temel Latin harfler/aksanlar her zaman korunur.</p>
        <label class="subset-checkbox">
          <input type="checkbox" id="subsetCjkPreset" checked />
          Temel CJK Unified Ideographs bloğunu koru (~20.000 karakter + yaygın noktalama — çoğu kullanım için yeterli)
        </label>
        <label class="subset-label" for="subsetKeepText">Ayrıca kesin korunmasını istediğiniz metin/karakterler (opsiyonel):</label>
        <textarea id="subsetKeepText" class="subset-textarea" rows="2" placeholder="Örn. özel olarak kullandığınız ekstra karakterler ya da kelimeler..."></textarea>
        <div class="subset-actions">
          <button id="subsetBtn" type="button" class="btn btn-primary btn-small">Fontu Subset Et</button>
          <span id="subsetStatus" class="subset-status"></span>
        </div>
      </div>`;
  }

  function wireSubsetTool(banner) {
    const btn = banner.querySelector("#subsetBtn");
    const status = banner.querySelector("#subsetStatus");
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      status.textContent = "Subset ediliyor (büyük fontlarda 30-60 saniye sürebilir)...";
      try {
        const keepText = banner.querySelector("#subsetKeepText").value;
        const keepCjk = banner.querySelector("#subsetCjkPreset").checked;
        const res = await fetch("/api/subset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: state.sessionId, keep_text: keepText, keep_cjk_preset: keepCjk }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Subset başarısız.");
        const { glyphs_before, glyphs_after, glyphs_freed } = data.subset_info;
        onUploaded(data);
        const success = $("#subsetSuccessBanner");
        success.textContent = `Subset tamamlandı: ${glyphs_before.toLocaleString("tr-TR")} → ${glyphs_after.toLocaleString("tr-TR")} glyph (${glyphs_freed.toLocaleString("tr-TR")} glyph boşaldı).`;
        success.classList.remove("hidden");
      } catch (err) {
        status.textContent = "Hata: " + err.message;
        btn.disabled = false;
      }
    });
  }

  // -------------------------------------------------------------- sidebar

  function renderSidebarInfo() {
    const info = state.fontInfo;
    const list = $("#fontInfoList");
    const rows = [
      ["Aile", info.family_name],
      ["Stil", info.subfamily_name || "—"],
      ["Format", info.format],
      ["Units/Em", info.units_per_em],
      ["Glyph Sayısı", info.num_glyphs],
    ];
    list.innerHTML = rows.map(([k, v]) => `<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v))}</dd></div>`).join("");
    renderStatusSummary();
  }

  function renderStatusSummary() {
    const counts = {};
    Object.values(state.chars).forEach((c) => {
      counts[c.status] = (counts[c.status] || 0) + 1;
    });
    const ul = $("#statusSummary");
    ul.innerHTML = Object.entries(STATUS_LABEL)
      .filter(([k]) => counts[k])
      .map(
        ([k, label]) =>
          `<li><span class="status-dot" style="background:${STATUS_DOT_COLOR[k]}"></span>${label}: ${counts[k]}</li>`
      )
      .join("");
  }

  // ------------------------------------------------------------- char list

  const template = $("#charRowTemplate");
  const charListEl = $("#charList");

  function renderCharList() {
    charListEl.innerHTML = "";
    Object.values(state.chars).forEach((cs) => {
      const row = template.content.firstElementChild.cloneNode(true);
      row.dataset.char = cs.char || "";
      buildRow(row, cs);
      charListEl.appendChild(row);
    });
  }

  function buildRow(row, cs) {
    const char = charFor(cs);
    row.dataset.char = char;
    row.querySelector(".char-title").textContent = `${char}  (U+${cs.codepoint.toString(16).toUpperCase().padStart(4, "0")})`;
    row.querySelector(".char-label").textContent = cs.label;
    const pill = row.querySelector(".char-status-pill");
    pill.textContent = STATUS_LABEL[cs.status] || cs.status;
    pill.classList.add(`status-${cs.status}`);

    const includeBox = row.querySelector(".include-checkbox");
    if (cs.status === "present") {
      row.querySelector(".char-include").classList.add("hidden");
      row.querySelector(".chevron").classList.add("hidden");
    } else {
      includeBox.checked = cs.include;
      includeBox.addEventListener("change", () => {
        cs.include = includeBox.checked;
      });
    }

    const summaryBtn = row.querySelector(".char-row-summary");
    if (cs.status === "present") {
      row.querySelector(".mini-preview").outerHTML = '<span style="font-size:20px;color:#2f7d4f;">&#10003;</span>';
    } else {
      summaryBtn.addEventListener("click", (e) => {
        if (e.target.closest(".char-include")) return;
        toggleRow(row, cs);
      });
    }

    const editor = row.querySelector(".char-editor");
    const fieldsEl = row.querySelector(".editor-fields");
    renderFields(fieldsEl, cs, row);
  }

  function charFor(cs) {
    return Object.keys(state.chars).find((k) => state.chars[k] === cs);
  }

  function toggleRow(row, cs) {
    cs.open = !cs.open;
    row.classList.toggle("open", cs.open);
    row.querySelector(".char-editor").classList.toggle("hidden", !cs.open);
    if (cs.open) fetchPreview(charFor(cs), true);
  }

  // ------------------------------------------------------------ field UI

  function renderFields(container, cs, row) {
    container.innerHTML = "";
    const mode = cs.recipe.mode;

    if (cs.status === "existing_unmapped") {
      const note = document.createElement("div");
      note.className = "existing-note";
      note.textContent = `Font zaten '${cs.recipe.source_glyph}' adlı bir glyph içeriyor ama bu karaktere eşlenmemiş. Yeni bir çizim yapılmadan doğrudan eşlenecek.`;
      container.appendChild(note);
      return;
    }

    if (mode === "skip" && !cs.recipe.base_glyph) {
      const note = document.createElement("div");
      note.className = "needs-attention-note";
      note.textContent = "Temel harf bu fontta bulunamadığı için otomatik oluşturma yapılamıyor.";
      container.appendChild(note);
      return;
    }

    if (mode === "dotless") {
      container.appendChild(glyphField("Kaynak Glyph (gövde)", cs.recipe.base_glyph, (val) => {
        cs.recipe.base_glyph = val;
        scheduleAndPreview(cs);
      }));
      container.appendChild(sliderField(
        "Nokta Kesme Çizgisi (Y)", cs.recipe.cutoff_y, -200, state.fontInfo.units_per_em * 1.3, 1,
        (val) => { cs.recipe.cutoff_y = val; scheduleAndPreview(cs); }
      ));
      container.appendChild(resetButton(cs));
      return;
    }

    if (mode === "compose") {
      container.appendChild(glyphField("Temel Glyph", cs.recipe.base_glyph, (val) => {
        cs.recipe.base_glyph = val;
        scheduleAndPreview(cs);
      }));

      const desc = document.createElement("div");
      desc.className = "source-desc";
      desc.textContent = describeSource(cs.recipe.accent_source);
      container.appendChild(desc);

      container.appendChild(glyphField("Aksan Glyph (elle değiştir)", "", (val) => {
        if (val.trim()) {
          cs.recipe.accent_source = val.trim();
          desc.textContent = describeSource(cs.recipe.accent_source);
          scheduleAndPreview(cs);
        }
      }, "Farklı bir glyph adı yazın..."));

      const rowFields = document.createElement("div");
      rowFields.className = "field-row";
      rowFields.appendChild(sliderField("X Konumu", cs.recipe.dx, -state.fontInfo.units_per_em, state.fontInfo.units_per_em, 1,
        (val) => { cs.recipe.dx = val; scheduleAndPreview(cs); }));
      rowFields.appendChild(sliderField("Y Konumu", cs.recipe.dy, -state.fontInfo.units_per_em, state.fontInfo.units_per_em, 1,
        (val) => { cs.recipe.dy = val; scheduleAndPreview(cs); }));
      container.appendChild(rowFields);

      container.appendChild(sliderField("Ölçek", cs.recipe.scale_x, 0.2, 2.5, 0.01,
        (val) => { cs.recipe.scale_x = val; cs.recipe.scale_y = val; scheduleAndPreview(cs); }));

      container.appendChild(resetButton(cs));
    }
  }

  function describeSource(source) {
    if (!source) return "Aksan kaynağı seçilmedi.";
    if (source.startsWith("__donor__:")) {
      const donor = source.split(":")[1];
      return `Otomatik: '${donor}' karakterinden ayıklanan şekil kullanılıyor.`;
    }
    if (source.startsWith("__synthetic__")) {
      return "Otomatik: fontta uygun bileşen bulunamadı, yerleşik basit vektör şekli kullanılıyor.";
    }
    return `Kaynak glyph: '${source}'`;
  }

  function glyphField(labelText, value, onChange, placeholder) {
    const wrap = document.createElement("div");
    wrap.className = "field-group field";
    const label = document.createElement("label");
    label.textContent = labelText;
    const input = document.createElement("input");
    input.type = "text";
    input.value = value || "";
    if (placeholder) input.placeholder = placeholder;
    const listId = "glyphs-" + Math.random().toString(36).slice(2);
    input.setAttribute("list", listId);
    const datalist = document.createElement("datalist");
    datalist.id = listId;

    const doSearch = debounce(async (q) => {
      const params = new URLSearchParams({ session_id: state.sessionId, q, limit: 40 });
      const res = await fetch(`/api/glyphs?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      datalist.innerHTML = data.glyphs.map((g) => `<option value="${escapeHtml(g)}"></option>`).join("");
    }, 150);
    input.addEventListener("input", () => doSearch(input.value));
    input.addEventListener("focus", () => doSearch(input.value));
    input.addEventListener("change", () => onChange(input.value));

    wrap.appendChild(label);
    wrap.appendChild(input);
    wrap.appendChild(datalist);
    return wrap;
  }

  function sliderField(labelText, value, min, max, step, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "field-group field";
    const label = document.createElement("label");
    label.textContent = labelText;
    const row = document.createElement("div");
    row.className = "field-slider";
    const range = document.createElement("input");
    range.type = "range";
    range.min = min; range.max = max; range.step = step; range.value = value;
    const num = document.createElement("input");
    num.type = "number";
    num.min = min; num.max = max; num.step = step; num.value = round2(value);

    const sync = (v) => {
      range.value = v; num.value = round2(v);
      onChange(parseFloat(v));
    };
    range.addEventListener("input", () => sync(range.value));
    num.addEventListener("change", () => sync(num.value));

    row.appendChild(range);
    row.appendChild(num);
    wrap.appendChild(label);
    wrap.appendChild(row);
    return wrap;
  }

  function resetButton(cs) {
    const wrap = document.createElement("div");
    wrap.className = "field-actions";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-ghost btn-small";
    btn.textContent = "Otomatik Ayarlara Sıfırla";
    btn.addEventListener("click", () => {
      cs.recipe = JSON.parse(JSON.stringify(cs.originalRecipe));
      const row = charListEl.querySelector(`.char-row[data-char="${cssEscape(charFor(cs))}"]`);
      const wasOpen = cs.open;
      renderFields(row.querySelector(".editor-fields"), cs, row);
      if (wasOpen) fetchPreview(charFor(cs), true);
    });
    wrap.appendChild(btn);
    return wrap;
  }

  function round2(v) {
    return Math.round(parseFloat(v) * 100) / 100;
  }

  // ------------------------------------------------------------- preview

  const previewDebounced = debounce((char) => fetchPreview(char, false), 200);
  function scheduleAndPreview(cs) {
    previewDebounced(charFor(cs));
  }

  async function fetchPreview(char, updateBig) {
    const cs = state.chars[char];
    if (!cs || cs.status === "present") return;
    let recipe = cs.recipe;
    if (cs.status === "existing_unmapped") {
      recipe = { mode: "existing", source_glyph: cs.recipe.source_glyph };
    }
    try {
      const res = await fetch("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId, char, recipe }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Önizleme hatası");

      const row = charListEl.querySelector(`.char-row[data-char="${cssEscape(char)}"]`);
      if (!row) return;
      drawGlyphSVG(row.querySelector(".mini-preview"), data, { tight: true });
      if (updateBig || cs.open) {
        drawGlyphSVG(row.querySelector(".big-preview"), data, { tight: false });
      }
      const warnEl = row.querySelector(".editor-warnings");
      const allWarnings = [...(cs.warnings || []), ...(data.warnings || [])];
      warnEl.innerHTML = [...new Set(allWarnings)]
        .map((w) => `<div class="warn-line">${escapeHtml(w)}</div>`)
        .join("");
    } catch (err) {
      // sessizce yut - kullanıcı yazarken geçici hatalı ara durumlar olabilir
    }
  }

  function prefetchAllPreviews() {
    Object.keys(state.chars).forEach((char) => {
      if (state.chars[char].status !== "present") fetchPreview(char, false);
    });
  }

  function drawGlyphSVG(svgEl, data, { tight }) {
    while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
    const ns = "http://www.w3.org/2000/svg";
    const upm = state.fontInfo.units_per_em;
    const asc = state.fontInfo.ascender;
    const desc = state.fontInfo.descender;

    let viewW, viewH, tx, ty;
    if (tight && data.bounds) {
      const [x0, y0, x1, y1] = data.bounds;
      const w = Math.max(x1 - x0, 1), h = Math.max(y1 - y0, 1);
      const margin = Math.max(w, h) * 0.15;
      viewW = w + margin * 2; viewH = h + margin * 2;
      tx = margin - x0; ty = y1 + margin;
    } else {
      const margin = upm * 0.12;
      viewW = Math.max(data.advance_width, 1) + margin * 2;
      viewH = (asc - desc) + margin * 2;
      tx = margin; ty = asc + margin;
    }
    svgEl.setAttribute("viewBox", `0 0 ${viewW} ${viewH}`);

    if (!tight) {
      const baselineY = ty; // font y=0
      const guide = (y, dash) => {
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", 0); line.setAttribute("x2", viewW);
        line.setAttribute("y1", y); line.setAttribute("y2", y);
        line.setAttribute("stroke", "#d8d2c4");
        line.setAttribute("stroke-width", "1");
        if (dash) line.setAttribute("stroke-dasharray", "4 3");
        svgEl.appendChild(line);
      };
      guide(baselineY, false);
      guide(ty - asc, true);
      guide(ty - desc, true);
    }

    const g = document.createElementNS(ns, "g");
    g.setAttribute("transform", `translate(${tx} ${ty}) scale(1,-1)`);
    if (data.path) {
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", data.path);
      path.setAttribute("fill", "#201d18");
      path.setAttribute("fill-rule", "nonzero");
      g.appendChild(path);
    }
    svgEl.appendChild(g);
  }

  // --------------------------------------------------------------- build

  $("#buildBtn").addEventListener("click", async () => {
    const btn = $("#buildBtn");
    btn.disabled = true;
    btn.textContent = "Oluşturuluyor...";
    const reportEl = $("#buildReport");
    reportEl.classList.add("hidden");
    try {
      const recipes = {};
      Object.entries(state.chars).forEach(([char, cs]) => {
        if (cs.status === "present") return;
        if (!cs.include) { recipes[char] = { mode: "skip" }; return; }
        if (cs.status === "existing_unmapped") {
          recipes[char] = { mode: "existing", source_glyph: cs.recipe.source_glyph };
        } else {
          recipes[char] = cs.recipe;
        }
      });
      const res = await fetch("/api/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId, recipes }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Oluşturma başarısız.");
      showBuildReport(data);
    } catch (err) {
      reportEl.classList.remove("hidden");
      reportEl.innerHTML = `<div class="error-box">${escapeHtml(err.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Fontu Oluştur ve İndir";
    }
  });

  function showBuildReport(data) {
    const reportEl = $("#buildReport");
    reportEl.classList.remove("hidden");
    const lines = [];
    Object.entries(data.report || {}).forEach(([char, msgs]) => {
      msgs.forEach((m) => lines.push(`<li><strong>${escapeHtml(char)}</strong>: ${escapeHtml(m)}</li>`));
    });
    const byteChars = atob(data.font_base64);
    const bytes = new Uint8Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i);
    const blob = new Blob([bytes], { type: "font/ttf" });
    const url = URL.createObjectURL(blob);

    reportEl.innerHTML = `
      <h3>Sonuç</h3>
      <ul>${lines.join("") || "<li>Değişiklik yapılmadı.</li>"}</ul>
      <a class="download-link" href="${url}" download="${escapeHtml(data.filename)}">⬇ ${escapeHtml(data.filename)} indir</a>
    `;
  }

  // --------------------------------------------------------------- utils

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function cssEscape(str) {
    return String(str).replace(/["\\]/g, "\\$&");
  }
})();
