// Lo que comparten las dos páginas: formato, tooltip, el panel lateral (año, pesos, tema) y el dibujo del mapa.
// El año y los pesos viajan entre páginas en la URL (?anio=2025&pesos=real).
window.P = (() => {
  const D = window.DATOS;
  const ANIOS = D.totales.map(t => t.anio);
  const url = new URLSearchParams(location.search);
  const st = {
    anio: ANIOS.includes(+url.get("anio")) ? +url.get("anio") : ANIOS.filter(a => D.corte[a] === "anual").pop(),
    pesos: url.get("pesos") === "nominal" ? "nominal" : "real",
  };

  // ---------- formato ----------
  const nf = (n, d = 0) => n.toLocaleString("es-AR", { minimumFractionDigits: d, maximumFractionDigits: d });
  function plata(n, corto) {
    const a = Math.abs(n);
    if (a >= 1e12) return "$ " + nf(n / 1e12, 2) + (corto ? " bill." : " billones");
    if (a >= 1e9) return "$ " + nf(n / 1e9, a >= 1e11 ? 0 : 1) + (corto ? " mil M" : " mil millones");
    if (a >= 1e6) return "$ " + nf(n / 1e6, a >= 1e8 ? 0 : 1) + (corto ? " M" : " millones");
    return "$ " + nf(n);
  }
  const pct = (x, d = 1) => isFinite(x) ? nf(100 * x, d) + " %" : "—";
  const f = a => st.pesos === "real" ? D.factor[a] : 1;
  const m = (r, k = "devengado") => r[k] * f(r.anio);
  const titulo = s => s.toLowerCase().replace(/(^|\s|\()(\p{L})/gu, (x, p, c) => p + c.toUpperCase())
    .replace(/\b(De|Del|La|Las|Los|Y|E|En|A|Al|Para|Por|Con|Sin|O)\b/g, w => w.toLowerCase())
    .replace(/^(\p{L})/u, c => c.toUpperCase());
  const MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
  const [pa, pm] = D.pesos_de.split("-");
  const pesosDe = `${MESES[+pm - 1]} de ${pa}`;
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const parcial = a => D.corte[a] !== "anual";

  // ---------- tooltip (siempre textContent: las etiquetas vienen del dataset) ----------
  const tip = document.getElementById("tip");
  function mostrar(ev, titulo, filas) {
    tip.replaceChildren(el("div", "t", titulo));
    for (const [k, v] of filas) { const r = el("div", "r"); r.append(el("b", null, v), el("span", null, k)); tip.append(r); }
    tip.classList.add("on");
    mover(ev);
  }
  function mover(ev) {
    let x, y;
    if (ev.clientX != null && ev.type !== "focus") { x = ev.clientX; y = ev.clientY; }
    else { const b = ev.currentTarget.getBoundingClientRect(); x = b.left + b.width / 2; y = b.top; }
    const w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(window.innerWidth - w - 8, Math.max(8, x + 14)) + "px";
    tip.style.top = (y - h - 12 < 8 ? y + 18 : y - h - 12) + "px";
  }
  const ocultar = () => tip.classList.remove("on");
  function conTip(nodo, fnTitulo, fnFilas) {
    nodo.tabIndex = 0;
    const on = ev => mostrar(ev, fnTitulo(), fnFilas());
    nodo.addEventListener("pointerenter", on); nodo.addEventListener("pointermove", mover);
    nodo.addEventListener("pointerleave", ocultar); nodo.addEventListener("focus", on); nodo.addEventListener("blur", ocultar);
  }
  const filasMontos = r => [
    ["sancionado", plata(m(r, "sancionado"))], ["vigente", plata(m(r, "vigente"))],
    ["devengado", plata(m(r))], ["ejecución", pct(r.devengado / r.vigente)]];

  // ---------- panel lateral ----------
  let render = () => {};
  const segA = document.getElementById("anios");
  for (const a of ANIOS) {
    const b = el("button", null, String(a));
    b.type = "button";
    if (parcial(a)) { b.append(el("sup", null, "*")); b.title = "Hasta " + D.corte[a]; }
    b.dataset.anio = a;
    b.onclick = () => { st.anio = a; cambio(); };
    segA.append(b);
  }
  document.querySelectorAll("[data-pesos]").forEach(b => b.onclick = () => { st.pesos = b.dataset.pesos; cambio(); });
  function cambio() {
    const q = `?anio=${st.anio}&pesos=${st.pesos}`;
    history.replaceState(null, "", q + location.hash);
    // los enlaces a la otra página se llevan el año y los pesos
    document.querySelectorAll("a[data-pagina]").forEach(a => {
      a.dataset.base ||= a.getAttribute("href");
      const [base, ancla] = a.dataset.base.split("#");
      a.href = base + q + (ancla ? "#" + ancla : "");
    });
    document.querySelectorAll("[data-anio]").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.anio === st.anio)));
    document.querySelectorAll("[data-pesos]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.pesos === st.pesos)));
    render();
  }
  const temas = ["auto", "claro", "oscuro"];
  let tema = 0;
  try { tema = Math.max(0, temas.indexOf(localStorage.getItem("presu-tema") || "auto")); } catch (e) {}
  const btnTema = document.getElementById("tema");
  function aplicarTema() {
    const t = temas[tema];
    if (t === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.dataset.theme = t === "claro" ? "light" : "dark";
    btnTema.textContent = "Tema: " + t;
  }
  btnTema.onclick = () => { tema = (tema + 1) % 3; try { localStorage.setItem("presu-tema", temas[tema]); } catch (e) {} aplicarTema(); };
  aplicarTema();
  // en el celular el panel es una barra arriba y las secciones se abren con un botón
  const lateral = document.getElementById("lateral"), menu = document.getElementById("menu");
  menu.onclick = () => { const on = lateral.classList.toggle("abierta"); menu.setAttribute("aria-expanded", String(on)); };
  lateral.querySelectorAll("nav a").forEach(a => a.addEventListener("click", () => {
    lateral.classList.remove("abierta"); menu.setAttribute("aria-expanded", "false");
  }));

  // ---------- mapa de las comunas ----------
  // siete tonos de la escala secuencial, repartidos parejo entre el mínimo y el máximo
  const escala = (min, max) => v => max > min ? 1 + Math.min(6, Math.floor(7 * (v - min) / (max - min))) : 4;
  function mapa(caja, { valor, etiqueta, elegida, alElegir, enlazar, rotulo }) {
    const { ancho, alto } = D.mapa;
    const NS = "http://www.w3.org/2000/svg";
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", `-4 -4 ${ancho + 8} ${alto + 8}`);
    s.setAttribute("role", "group");
    s.setAttribute("aria-label", rotulo);
    const nodo = (t, a, txt) => { const n = document.createElementNS(NS, t); for (const k in a) n.setAttribute(k, a[k]); if (txt != null) n.textContent = txt; s.append(n); return n; };
    const vals = D.mapa.comunas.map(c => valor(c.comuna)).filter(v => v != null && isFinite(v));
    const min = Math.min(...vals), max = Math.max(...vals), tono = escala(min, max);
    const caminos = [];
    for (const c of D.mapa.comunas) {
      const v = valor(c.comuna);
      const p = nodo("path", { d: c.d, fill: v != null && isFinite(v) ? `var(--seq-${tono(v)})` : "var(--seq-0)" });
      p.dataset.comuna = c.comuna;
      if (c.comuna === elegida) p.classList.add("elegida");
      if (enlazar) enlazar(p, c.comuna);
      if (alElegir) {
        p.addEventListener("click", () => alElegir(c.comuna));
        p.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); alElegir(c.comuna); } });
      }
      caminos.push(p);
    }
    // la elegida va al final para que su borde no quede tapado por las vecinas
    const sel = caminos.find(p => p.classList.contains("elegida"));
    if (sel) s.append(sel);
    for (const c of D.mapa.comunas) {
      nodo("text", { x: c.x, y: c.y - (etiqueta ? 12 : 0) }, c.comuna);
      if (etiqueta) nodo("text", { x: c.x, y: c.y + 14, class: "valor" }, etiqueta(c.comuna));
    }
    caja.replaceChildren(s);
    return { min, max };
  }
  function leyenda(caja, min, max, fmt, unidad) {
    const esc = el("div", "escala");
    for (let i = 1; i <= 7; i++) { const t = el("span"); t.style.background = `var(--seq-${i})`; esc.append(t); }
    caja.replaceChildren(el("span", null, fmt(min)), esc, el("span", null, fmt(max)), ...(unidad ? [el("span", null, unidad)] : []));
  }

  return {
    D, ANIOS, st, nf, plata, pct, f, m, titulo, pesosDe, el, parcial, conTip, mostrar, ocultar, filasMontos, mapa, leyenda,
    iniciar(fn) { render = fn; cambio(); },
    cambiar: cambio,
  };
})();
