const $ = (id) => document.getElementById(id);
const logEl = $("log");

let selectedFile = null;
let projectId = null;
let pollTimer = null;

function log(msg) {
  logEl.textContent += `[${new Date().toLocaleTimeString()}] ${msg}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function apiBase() {
  return $("apiBase").value.replace(/\/+$/, "");
}

function headers(extra) {
  const h = Object.assign({}, extra || {});
  const key = $("apiKey").value.trim();
  if (key) h["X-API-Key"] = key;
  return h;
}

async function api(path, options) {
  const res = await fetch(apiBase() + path, options || {});
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch (e) { /* not json */ }
  if (!res.ok) throw new Error((data && data.detail) || text || res.status);
  return data;
}

// ---------------------------------------------------------------- languages

const FALLBACK_LANGS = { tr: "Turkish", en: "English", ja: "Japanese", de: "German", es: "Spanish" };

function fillLanguages(map) {
  const sel = $("targetLang");
  sel.innerHTML = "";
  for (const [code, name] of Object.entries(map)) {
    sel.add(new Option(`${name} (${code})`, code));
  }
  sel.value = "tr";
}

async function loadLanguages() {
  try {
    fillLanguages(await api("/languages", { headers: headers() }));
  } catch (e) {
    fillLanguages(FALLBACK_LANGS);
  }
}

// ------------------------------------------------------------------- upload

function setFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".zip")) {
    log("Yalnızca .zip dosyası yükleyebilirsiniz.");
    return;
  }
  selectedFile = file;
  $("uploadInfo").textContent = `${file.name} — ${(file.size / 1048576).toFixed(1)} MB`;
  $("btnUpload").disabled = false;
}

$("dropZone").addEventListener("click", () => $("fileInput").click());
$("fileInput").addEventListener("change", (e) => setFile(e.target.files[0]));
["dragenter", "dragover"].forEach((ev) =>
  $("dropZone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("dropZone").classList.add("dragging");
  })
);
["dragleave", "drop"].forEach((ev) =>
  $("dropZone").addEventListener(ev, (e) => {
    e.preventDefault();
    $("dropZone").classList.remove("dragging");
  })
);
$("dropZone").addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));

$("btnUpload").addEventListener("click", async () => {
  if (!selectedFile) return;
  const body = new FormData();
  body.append("file", selectedFile);
  $("btnUpload").disabled = true;
  log(`Yükleniyor: ${selectedFile.name} ...`);
  try {
    const st = await api("/renpy/upload", { method: "POST", headers: headers(), body });
    projectId = st.id;
    log(`Analiz tamam — ${st.script_files} script dosyası, ${st.total_units} benzersiz metin, ${st.total_slots} konum.`);
    if (st.compiled_slots) {
      log(`${st.compiled_slots} metin derlenmiş .rpyc içinden okundu; bunlar için ayrı bir çeviri dosyası üretilecek.`);
    }
    if (st.unreadable_files && st.unreadable_files.length) {
      log(`Okunamayan dosyalar atlandı: ${st.unreadable_files.join(", ")}`);
    }
    render(st);
  } catch (e) {
    log("Yükleme hatası: " + e.message);
  } finally {
    $("btnUpload").disabled = false;
  }
});

// -------------------------------------------------------------------- render

function stat(num, label) {
  return `<div class="stat"><div class="num">${num}</div><div class="label">${label}</div></div>`;
}

const STATUS_TR = {
  ready: "hazır", translating: "çevriliyor", done: "tamamlandı",
  cancelled: "durduruldu", failed: "hata",
};

function render(st) {
  $("projectPanel").hidden = false;

  $("projectStats").innerHTML = [
    stat(st.script_files || 0, "Script Dosyası"),
    stat(st.total_units, "Benzersiz Metin"),
    stat(st.total_slots, "Toplam Konum"),
    stat(STATUS_TR[st.status] || st.status, "Durum"),
    stat(st.failed_units || 0, "Hata"),
  ].join("");

  $("overallBar").style.width = st.percent + "%";
  $("overallPct").textContent = st.percent + "%";
  $("overallNote").textContent =
    `${st.translated_units} / ${st.total_units} metin çevrildi` +
    (st.target_lang ? ` — hedef: ${st.target_lang}` : "");

  const note = $("compiledNote");
  if (st.compiled_slots) {
    note.hidden = false;
    note.textContent =
      `${st.compiled_slots} metin derlenmiş .rpyc dosyalarından geliyor (diyalog, menü ` +
      `seçenekleri ve arayüz metinleri — buton, sekme, mağaza/istatistik ekranları dahil). ` +
      `Bu dosyalar düzenlenemediği için çeviriler, indirilen zip'teki tl/ klasörü ve ` +
      `hymt_translate.rpy üzerinden oyuna uygulanır.`;
  } else {
    note.hidden = true;
  }

  const staleNote = $("staleRpycNote");
  if (st.stale_rpyc && st.stale_rpyc.length) {
    staleNote.hidden = false;
    staleNote.innerHTML =
      `⚠ Projenizde ${st.stale_rpyc.length} dosyanın hem .rpy hem eski bir .rpyc kopyası var. ` +
      `İndirilen zip'in içindeki <code>HYMT_DELETE_THESE_RPYC_FIRST.txt</code> dosyasını açın ve ` +
      `oradaki .rpyc dosyalarını çevrilen .rpy'leri kopyalamadan ÖNCE oyun klasörünüzden silin — ` +
      `yoksa Ren'Py eski derlenmiş sürümü çalıştırıp çeviriyle çakışabilir ve oyun içi hataya yol açabilir.`;
  } else {
    staleNote.hidden = true;
  }

  $("fileList").innerHTML = st.files.map((f) => `
    <div class="file-row">
      <div class="file-name" title="${f.file}">${f.file}</div>
      <div class="progress-track small"><div class="progress-fill" style="width:${f.percent}%"></div></div>
      <div class="file-count">${f.done}/${f.total}</div>
    </div>`).join("");

  const running = st.running || st.status === "translating";
  $("btnStart").hidden = running;
  $("btnStart").textContent = st.translated_units > 0 && st.status !== "done"
    ? "Kaldığı Yerden Devam Et" : "Çeviriyi Başlat";
  $("btnCancel").hidden = !running;

  if (running) startPolling(); else stopPolling();
}

// ------------------------------------------------------------------ polling

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(refresh, 2000);
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function refresh() {
  if (!projectId) return;
  try {
    const st = await api(`/renpy/${projectId}/status`, { headers: headers() });
    const wasRunning = !$("btnCancel").hidden;
    render(st);
    if (wasRunning && !(st.running || st.status === "translating")) {
      log(`Çeviri ${STATUS_TR[st.status] || st.status}. ${st.translated_units}/${st.total_units} metin.` +
          (st.failed_units ? ` ${st.failed_units} satırda model hatası oldu, kaynak korundu.` : ""));
    }
  } catch (e) {
    log("Durum alınamadı: " + e.message);
    stopPolling();
  }
}

// ------------------------------------------------------------------ actions

$("btnStart").addEventListener("click", async () => {
  if (!projectId) return;
  try {
    log("Çeviri başlatılıyor...");
    await api(`/renpy/${projectId}/start`, {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({ target_lang: $("targetLang").value }),
    });
    startPolling();
    refresh();
  } catch (e) {
    log("Başlatılamadı: " + e.message);
  }
});

$("btnCancel").addEventListener("click", async () => {
  try {
    await api(`/renpy/${projectId}/cancel`, { method: "POST", headers: headers() });
    log("Durdurma istendi — devam eden istekler bitince duracak.");
  } catch (e) {
    log("Durdurulamadı: " + e.message);
  }
});

$("btnDownload").addEventListener("click", async () => {
  if (!projectId) return;
  log("Paketleniyor...");
  try {
    // Fetched rather than linked so the API key header can be sent, and so a
    // failure surfaces as a log line instead of a broken download.
    const res = await fetch(`${apiBase()}/renpy/${projectId}/download`, { headers: headers() });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "renpy-translated.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    log(`İndirildi (${(blob.size / 1048576).toFixed(2)} MB). Zip'i oyunun kök klasörüne açın.`);
  } catch (e) {
    log("İndirilemedi: " + e.message);
  }
});

$("btnDelete").addEventListener("click", async () => {
  if (!projectId) return;
  try {
    await api(`/renpy/${projectId}`, { method: "DELETE", headers: headers() });
    log("Proje silindi.");
    stopPolling();
    projectId = null;
    $("projectPanel").hidden = true;
  } catch (e) {
    log("Silinemedi: " + e.message);
  }
});

// --------------------------------------------------------------- initialise

if (location.protocol === "http:" || location.protocol === "https:") {
  $("apiBase").value = location.origin;
}
loadLanguages();

// Pick up a job that is already running - e.g. after a page reload, or after
// the Space restarted and resumed the run on its own.
(async () => {
  try {
    const list = await api("/renpy", { headers: headers() });
    if (list.projects && list.projects.length) {
      const active = list.projects.find((p) => p.running) || list.projects[0];
      projectId = active.id;
      render(active);
      log(`Mevcut proje bulundu: ${active.name || active.id} (${STATUS_TR[active.status] || active.status}).`);
    } else {
      log("Arayüz hazır. Bir .rpy/.rpyc zip'i veya game klasörü yükleyin.");
    }
  } catch (e) {
    log("Arayüz hazır. API'ye bağlanılamadı: " + e.message);
  }
})();
