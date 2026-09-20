/* ============================================================
   JayuAI — cerebro hablante (app.js)
   Partículas doradas que vibran con la voz real (Web Audio
   Analyser) + chat, micrófono, paneles y PWA.
   ============================================================ */
"use strict";

/* ---------------- helpers ---------------- */
const $ = (id) => document.getElementById(id);
const json = async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error || "HTTP " + r.status); return j; };
const setLed = (state) => {
  const led = $("led");
  led.className = "status-led " + (state || "on");
  $("topbar-text").textContent = state === "busy" ? "Pensando…" : state === "ok" ? "En línea · cerebro local activo" : "Conectando…";
};

/* ---------------- estado del chat ---------------- */
let sessionId = "web-" + Math.random().toString(36).slice(2, 8);
let vozActivada = true;

/* ============================================================
   CEREBRO: partículas de oro que vibran con el audio de la voz
   ============================================================ */
class Cerebro {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.particles = [];
    this.energy = 0;          // 0..1 (vibración real por audio)
    this.speaking = false;    // cuando la voz suena de verdad
    this.state = "idle";      // idle | pensando | hablando

    this.resize();
    window.addEventListener("resize", () => this.resize());
    this.initParticles();
    this.setupAudio();
    this.loop();
  }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    this.w = r.width; this.h = r.height;
    this.canvas.width = this.w * this.dpr;
    this.canvas.height = this.h * this.dpr;
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  initParticles() {
    this.particles = [];
    const n = 110;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const rad = 0.32 + Math.random() * 0.42;   // órbita alrededor del núcleo
      this.particles.push({
        a, rad: rad * this.w * 0.5,
        speed: (0.15 + Math.random() * 0.5) * (Math.random() < 0.5 ? -1 : 1),
        size: 1.1 + Math.random() * 2.6,
        hue: 43 + Math.floor(Math.random() * 14),   // tonos dorados
        off: Math.random() * Math.PI * 2,
      });
    }
  }

  /* ---- audio: analizador que mueve las partículas ---- */
  setupAudio() {
    this.audio = new Audio();
    this.audioCtx = null;
    this.analyser = null;
    this.audio.addEventListener("play", () => {
      try {
        if (!this.audioCtx) {
          this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          const src = this.audioCtx.createMediaElementSource(this.audio);
          this.analyser = this.audioCtx.createAnalyser();
          this.analyser.fftSize = 256;
          src.connect(this.analyser);
          this.analyser.connect(this.audioCtx.destination);
        }
      } catch (e) { console.warn("analizador de audio no disponible", e); }
    });
  }

  setState(s) {
    this.state = s;
    const label = {
      idle: "escuchando…", pensando: "pensando…",
      hablando: "hablando…", error: "sin conexión",
    }[s] || "…";
    if (s !== "hablando") this.speaking = false;
    $("brain-label").textContent = s === "hablando" ? "" : label;
  }

  speak(texto) {
    if (!texto) return Promise.resolve();
    return fetch("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: texto }),
    })
      .then(json)
      .then((r) => {
        this.speaking = true;
        this.setState("hablando");
        this.audio.src = r.url;
        return this.audio.play().then(() => {
          const watch = setInterval(() => {
            if (this.audio.ended) {
              clearInterval(watch);
              this.speaking = false;
              this.setState("idle");
            }
          }, 150);
        });
      })
      .catch((e) => { console.warn("voz:", e); this.setState("idle"); });
  }

  stop() { try { this.audio.pause(); } catch (e) {} this.speaking = false; }

  /* ---- frame: dibuja el núcleo + partículas vibrantes ---- */
  frameEnergy() {
    // energía de la voz real (si hay analizador) o falsa si no habla
    let e = 0;
    if (this.speaking && this.analyser && this.audioCtx) {
      const data = new Uint8Array(this.analyser.frequencyBinCount);
      this.analyser.getByteFrequencyData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i];
      e = sum / (data.length * 255);
    } else if (this.speaking) {
      e = 0.25 + 0.15 * Math.sin(Date.now() / 120); // sin analizer (fallback suave)
    }
    // suavizado
    this.energy += (e - this.energy) * 0.25;
    if (!this.speaking) this.energy *= 0.9;
    return this.energy;
  }

  pulse(freq) {
    $("pulse-ring").classList.remove("ping");
    void $("pulse-ring").offsetWidth;
    $("pulse-ring").classList.add("ping");
  }

  loop() {
    const ctx = this.ctx, w = this.w, h = this.h;
    const cx = w / 2, cy = h / 2;
    const energy = this.frameEnergy();
    const t = Date.now() / 1000;
    const pensando = this.state === "pensando";

    ctx.clearRect(0, 0, w, h);

    // halo interno tenue
    const glow = ctx.createRadialGradient(cx, cy, 8, cx, cy, w * 0.42);
    glow.addColorStop(0, "rgba(245,197,66,0.16)");
    glow.addColorStop(1, "rgba(245,197,66,0)");
    ctx.fillStyle = glow;
    ctx.beginPath(); ctx.arc(cx, cy, w * 0.42, 0, Math.PI * 2); ctx.fill();

    // núcleo brillante
    const coreR = w * (0.13 + 0.02 * Math.sin(t * 1.4));
    const g = ctx.createRadialGradient(cx - coreR * 0.3, cy - coreR * 0.3, 2, cx, cy, coreR);
    g.addColorStop(0, "#fff8e0");
    g.addColorStop(0.55, "rgba(245,197,66,0.95)");
    g.addColorStop(1, "rgba(90,66,10,0.9)");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(cx, cy, coreR, 0, Math.PI * 2); ctx.fill();

    // ojitos (personalidad del cerebro)
    const eyeY = cy - coreR * 0.15, eyeDX = coreR * 0.42, eyeR = coreR * 0.16;
    ["#", "#"].forEach((_, i) => {
      const ex = cx + (i === 0 ? -eyeDX : eyeDX);
      ctx.fillStyle = "rgba(20,12,0,0.75)";
      ctx.beginPath(); ctx.arc(ex, eyeY, eyeR, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.beginPath(); ctx.arc(ex + eyeR * 0.3, eyeY - eyeR * 0.3, eyeR * 0.35, 0, Math.PI * 2); ctx.fill();
    });

    // partículas doradas en órbita, vibran con la energía
    const vib = energy * (4 + this.w * 0.03) + (pensando ? 1.2 : 0.0);
    for (const p of this.particles) {
      p.a += p.speed * 0.0065;
      const wob = Math.sin(t * 2.2 + p.off) * (2 + vib);
      const x = cx + Math.cos(p.a) * p.rad + wob;
      const y = cy + Math.sin(p.a) * p.rad + Math.cos(t * 1.8 + p.off) * vib * 0.6;
      const size = p.size * (1 + energy * 1.6);
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${p.hue}, 90%, ${62 + energy * 20}%, ${0.55 + energy * 0.4})`;
      ctx.fill();
    }

    // anillo exterior que late con la energía
    const ringR = w * (0.40 + 0.03 * Math.sin(t * 1.1) + energy * 0.05);
    ctx.strokeStyle = `rgba(245,197,66,${0.18 + energy * 0.3})`;
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(cx, cy, ringR, 0, Math.PI * 2); ctx.stroke();

    requestAnimationFrame(() => this.loop());
  }
}

/* ============================================================
   CHAT
   ============================================================ */
const chatLog = $("chat-log");

function addMsg(role, text, meta) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  if (meta) {
    const m = document.createElement("span");
    m.className = "meta";
    m.innerHTML = meta;
    div.appendChild(m);
  }
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

function enviarChat() {
  const input = $("chat-text");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  addMsg("user", text);
  setLed("busy");
  cerebro.setState("pensando");

  fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, session_id: sessionId }),
  })
    .then(json)
    .then((r) => {
      setLed("ok");
      cerebro.setState("idle");
      const meta = `<b>${r.provider}/${r.model}</b> · intento: ${r.intent} · modo: ${r.mode}`;
      addMsg("jayu", r.reply, meta);
      if (vozActivada && r.reply) cerebro.speak(r.reply);
    })
    .catch((e) => {
      setLed("ok");
      cerebro.setState("idle");
      addMsg("jayu", "Error: " + e.message);
    });
}

$("chat-form").addEventListener("submit", (e) => { e.preventDefault(); enviarChat(); });

/* micrófono -> /api/listen (STT local) */
$("btn-mic").addEventListener("click", () => {
  const btn = $("btn-mic");
  btn.classList.add("rec");
  cerebro.pulse();
  addMsg("user", "🎙 escuchando…");
  setLed("busy");
  cerebro.setState("pensando");
  fetch("/api/listen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ seconds: 6 }),
  })
    .then(json)
    .then((r) => {
      btn.classList.remove("rec");
      setLed("ok");
      chatLog.lastChild && chatLog.lastChild.remove();
      if (r.text) {
        $("chat-text").value = r.text;
        enviarChat();
      } else {
        addMsg("jayu", "No te he escuchado (STT local). Prueba más cerca del micrófono.");
      }
    })
    .catch((e) => {
      btn.classList.remove("rec");
      setLed("ok");
      addMsg("jayu", "Micrófono: " + e.message);
    });
});

/* ============================================================
   PANELES (estado, oro, skills, memoria, aprendizaje)
   ============================================================ */
function renderEstado(st) {
  $("est-modelo").textContent = st.skills ? "cerebro local" : "—";
  const provs = Object.entries(st.providers || {}).map(([n, p]) =>
    `${n}${p.reachable ? " ✓" : " ✗"}` + (p.models && p.models.length ? ` (${p.models.length})` : ""));
  $("est-proveedor").textContent = provs.join(" · ") || "ninguno";
  $("est-autonomia").textContent = st.autonomy_level || "—";
  $("est-mt5").textContent = st.mt5_available ? "disponible" : "no";
  $("est-trading").textContent = st.trading_mode || "—";
  const tts = st.voice && st.voice.tts;
  $("est-tts").textContent = tts && tts.installed ? (tts.voice || tts.engine) : "no";
  const stt = st.voice && st.voice.stt;
  $("est-stt").textContent = stt && stt.installed ? "listo" : "no";

  const skills = st.skills || {};
  const names = Object.keys(skills);
  $("n-skills").textContent = names.length;
  $("skills").innerHTML = names.map((n) =>
    `<li><span>${n}</span><span class="cat">${skills[n].category}</span></li>`).join("");
}

function renderOro(g) {
  const d = g.drivers || {};
  const vivo = d.en_vivo || {};
  const au = vivo.XAUUSD || {};
  const ag = vivo.XAGUSD || {};
  const dxy = vivo.DXY || {};
  $("oro-precio").textContent = au.precio != null ? au.precio : "pendiente";
  $("oro-trend").textContent = (d.metricas && d.metricas.tendencia) || au.tendencia || "—";
  $("oro-dxy").textContent = dxy.precio != null ? dxy.precio : "pendiente";
  const ratio = d.metricas && d.metricas.ratio_oro_plata;
  $("oro-ratio").textContent = ratio != null ? ratio : (ag.precio ? "—" : "pendiente");

  const lv = g.levels || {};
  const est = lv.estructura;
  $("oro-estructura").textContent = est && typeof est === "string" ? est.slice(0, 40) : (est ? (est.tipo || "—") : "—");

  const cal = g.calendar || {};
  const items = (cal.semanas || []).slice(0, 3).map((s) =>
    `<div class="cal-item">${s.cadena || ""}</div>`).join("");
  $("oro-calendar").innerHTML = items || "<div class='cal-item'>agenda macro…</div>";
}

function renderMemoria(m) {
  const rows = m.entradas || [];
  $("memoria").innerHTML = rows.slice(0, 6).map((r) =>
    `<li><b>[${r.category}]</b> ${(r.key || "").slice(0, 34)}${(r.key||"").length > 34 ? "…" : ""}</li>`).join("") ||
    "<li>(vacía)</li>";
}

function renderAprendizaje(a) {
  if (!a.ok) return;
  $("ap-total").textContent = a.total !== undefined ? a.total : "—";
  const u = a.utilidad || {};
  $("ap-utiles").textContent = u.utiles !== undefined ? u.utiles : "—";
}

function refreshPanels() {
  fetch("/api/status").then(json).then(renderEstado).catch(() => {});
  fetch("/api/markets/gold").then(json).then(renderOro).catch(() => {});
  fetch("/api/memory").then(json).then(renderMemoria).catch(() => {});
  fetch("/api/learning").then(json).then(renderAprendizaje).catch(() => {});
}

/* ============================================================
   PWA / instalación
   ============================================================ */
let promptInstalar = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  promptInstalar = e;
  $("btn-instalar").hidden = false;
});
$("btn-instalar").addEventListener("click", async () => {
  if (promptInstalar) { promptInstalar.prompt(); promptInstalar = null; $("btn-instalar").hidden = true; }
});

/* toggle voz */
$("toggle-voz").addEventListener("change", (e) => {
  vozActivada = e.target.checked;
  if (!vozActivada) cerebro.stop();
});

/* ============================================================
   ARRANQUE
   ============================================================ */
const cerebro = new Cerebro($("brain"));
setLed("ok");
refreshPanels();
setInterval(refreshPanels, 15000);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

// saludo de bienvenida
setTimeout(() => {
  addMsg("jayu", "Hola, soy JayuAI, tu cerebro local experto en oro (XAUUSD), macro, DXY y bonos del Tesoro. Pregúntame cualquier cosa — análisis en vivo, agenda macro o los mercados. 📈");
}, 600);