const LANGUAGES = {
  zh: "Chinese", "zh-hant": "Traditional Chinese", yue: "Cantonese", en: "English",
  fr: "French", pt: "Portuguese", es: "Spanish", ja: "Japanese", tr: "Turkish",
  ru: "Russian", ar: "Arabic", ko: "Korean", th: "Thai", it: "Italian", de: "German",
  vi: "Vietnamese", ms: "Malay", id: "Indonesian", tl: "Filipino", hi: "Hindi",
  pl: "Polish", cs: "Czech", nl: "Dutch", km: "Khmer", my: "Burmese", fa: "Persian",
  gu: "Gujarati", ur: "Urdu", te: "Telugu", mr: "Marathi", he: "Hebrew", bn: "Bengali",
  ta: "Tamil", uk: "Ukrainian", bo: "Tibetan", kk: "Kazakh", mn: "Mongolian", ug: "Uyghur",
};

const $ = (id) => document.getElementById(id);
const logEl = $("log");

function log(msg) {
  const t = new Date().toLocaleTimeString();
  logEl.textContent += `[${t}] ${msg}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function apiBase() {
  return $("apiBase").value.replace(/\/+$/, "");
}

function headers() {
  const h = { "Content-Type": "application/json" };
  const key = $("apiKey").value.trim();
  if (key) h["X-API-Key"] = key;
  return h;
}

function populateLanguageSelects() {
  const targetSel = $("targetLang");
  const sourceSel = $("sourceLang");
  targetSel.innerHTML = "";
  for (const [code, name] of Object.entries(LANGUAGES)) {
    const opt1 = new Option(`${name} (${code})`, code);
    targetSel.add(opt1);
    const opt2 = new Option(`${name} (${code})`, code);
    sourceSel.add(opt2);
  }
  targetSel.value = "tr";
}

async function fetchLanguagesFromApi() {
  try {
    const res = await fetch(`${apiBase()}/languages`, { headers: headers() });
    if (!res.ok) return;
    const data = await res.json();
    if (data && Object.keys(data).length) {
      Object.assign(LANGUAGES, data);
      populateLanguageSelects();
      log("Dil listesi API'den alındı.");
    }
  } catch (e) {
    // ignore, fall back to built-in list
  }
}

function getLines() {
  return $("sourceText").value
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
}

function requestBody(texts) {
  const body = {
    target_lang: $("targetLang").value,
    preserve_placeholders: false,
  };
  const source = $("sourceLang").value;
  if (source) body.source_lang = source;
  if (Array.isArray(texts)) body.texts = texts;
  else body.text = texts;
  return body;
}

function showResultsPanel() {
  $("results-panel").hidden = false;
}

function renderStats(stats) {
  const row = $("statsRow");
  row.innerHTML = "";
  for (const [label, value] of stats) {
    const div = document.createElement("div");
    div.className = "stat";
    div.innerHTML = `<div class="num">${value}</div><div class="label">${label}</div>`;
    row.appendChild(div);
  }
}

function renderTable(rows) {
  const tbody = document.querySelector("#resultsTable tbody");
  tbody.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    const timeCell = r.error
      ? `<td class="error">${r.error}</td>`
      : `<td>${r.translation ?? ""}</td>`;
    tr.innerHTML = `<td>${r.original}</td>${timeCell}<td class="time">${r.time ?? ""}</td>`;
    tbody.appendChild(tr);
  }
}

async function checkHealth() {
  const pill = $("healthStatus");
  pill.textContent = "kontrol ediliyor...";
  pill.className = "status-pill status-unknown";
  try {
    const res = await fetch(`${apiBase()}/health`, { headers: headers() });
    const data = await res.json();
    if (res.ok && data.llama_server) {
      pill.textContent = `hazır (${data.model_file}, ${data.parallel_slots} slot)`;
      pill.className = "status-pill status-ok";
      log("Sağlık kontrolü başarılı: " + JSON.stringify(data));
    } else {
      pill.textContent = "model başlıyor / yanıt vermiyor";
      pill.className = "status-pill status-bad";
      log("Sağlık kontrolü: backend henüz hazır değil.");
    }
  } catch (e) {
    pill.textContent = "bağlanılamadı";
    pill.className = "status-pill status-bad";
    log("Sağlık kontrolü hatası: " + e.message);
  }
}

async function translateSingle() {
  const lines = getLines();
  if (!lines.length) return log("Çevrilecek metin yok.");
  const text = lines[0];
  log(`Tek istek gönderiliyor: "${text}"`);
  try {
    const t0 = performance.now();
    const res = await fetch(`${apiBase()}/translate`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(requestBody(text)),
    });
    const data = await res.json();
    const clientMs = performance.now() - t0;
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

    showResultsPanel();
    renderStats([
      ["Sunucu Süresi", `${data.elapsed_seconds.toFixed(2)}s`],
      ["Toplam (istemci)", `${(clientMs / 1000).toFixed(2)}s`],
      ["Öğe Sayısı", "1"],
    ]);
    renderTable([{ original: text, translation: data.translation, time: `${data.elapsed_seconds.toFixed(2)}s` }]);
    log(`Tamamlandı: "${data.translation}" (${data.elapsed_seconds.toFixed(2)}s)`);
  } catch (e) {
    log("Hata: " + e.message);
  }
}

async function translateBatch(silent = false) {
  const lines = getLines();
  if (!lines.length) {
    if (!silent) log("Çevrilecek metin yok.");
    return null;
  }
  if (!silent) log(`Toplu istek gönderiliyor (${lines.length} satır)...`);
  const t0 = performance.now();
  const res = await fetch(`${apiBase()}/translate/batch`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(requestBody(lines)),
  });
  const data = await res.json();
  const clientMs = performance.now() - t0;
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

  if (!silent) {
    showResultsPanel();
    renderStats([
      ["Sunucu Süresi", `${data.elapsed_seconds.toFixed(2)}s`],
      ["Toplam (istemci)", `${(clientMs / 1000).toFixed(2)}s`],
      ["Öğe/sn", data.items_per_second ?? "-"],
      ["Öğe Sayısı", data.count],
    ]);
    renderTable(
      data.translations.map((t) => ({
        original: t.original,
        translation: t.translation,
        error: t.error,
        time: "",
      }))
    );
    log(`Toplu çeviri tamamlandı: ${data.count} öğe, ${data.elapsed_seconds.toFixed(2)}s, ${data.items_per_second} öğe/sn`);
  }
  return { data, clientSeconds: clientMs / 1000 };
}

async function runBenchmark() {
  const lines = getLines();
  if (!lines.length) return log("Çevrilecek metin yok.");

  $("benchmark-panel").hidden = false;
  const bars = $("benchBars");
  const summary = $("benchSummary");
  bars.innerHTML = "";
  summary.textContent = "";
  log(`Karşılaştırma başlıyor: ${lines.length} satır, sıralı istek vs. tek toplu istek.`);

  // 1) Sequential: one /translate call per line, awaited one at a time.
  const seqStart = performance.now();
  for (const line of lines) {
    try {
      const res = await fetch(`${apiBase()}/translate`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(requestBody(line)),
      });
      await res.json();
    } catch (e) {
      log("Sıralı istek hatası: " + e.message);
    }
  }
  const seqSeconds = (performance.now() - seqStart) / 1000;
  log(`Sıralı: ${lines.length} istek, ${seqSeconds.toFixed(2)}s toplam.`);

  // 2) Batch: a single /translate/batch call for all lines.
  let batchSeconds;
  try {
    const result = await translateBatch(true);
    batchSeconds = result.clientSeconds;
    log(`Toplu: ${lines.length} öğe tek istekte, ${batchSeconds.toFixed(2)}s toplam.`);
  } catch (e) {
    log("Toplu istek hatası: " + e.message);
    return;
  }

  const maxSeconds = Math.max(seqSeconds, batchSeconds, 0.001);
  bars.innerHTML = `
    <div class="bench-row">
      <div class="bench-label">Sıralı (${lines.length}x)</div>
      <div class="bench-track"><div class="bench-fill sequential" style="width:${(seqSeconds / maxSeconds) * 100}%"></div></div>
      <div class="bench-value">${seqSeconds.toFixed(2)}s</div>
    </div>
    <div class="bench-row">
      <div class="bench-label">Toplu (1x)</div>
      <div class="bench-track"><div class="bench-fill batch" style="width:${(batchSeconds / maxSeconds) * 100}%"></div></div>
      <div class="bench-value">${batchSeconds.toFixed(2)}s</div>
    </div>
  `;
  const speedup = batchSeconds > 0 ? (seqSeconds / batchSeconds).toFixed(2) : "-";
  summary.textContent = `Toplu istek, sıralı isteklere göre ${speedup}x daha hızlıydı (${lines.length} kısa string için).`;
}

$("checkHealth").addEventListener("click", checkHealth);
$("btnSingle").addEventListener("click", translateSingle);
$("btnBatch").addEventListener("click", () => translateBatch(false));
$("btnBenchmark").addEventListener("click", runBenchmark);

populateLanguageSelects();
fetchLanguagesFromApi();
log("Arayüz hazır. Önce API Base URL'i ayarlayıp Sağlık Kontrolü yapın.");
