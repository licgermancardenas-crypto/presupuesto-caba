// Lo que comparten las dos páginas: formato, tooltip, el panel lateral (año, pesos, medida, filtros, tema),
// el motor que filtra y suma la tabla de hechos, y los gráficos que responden a los filtros.
// Todo el estado viaja en la URL (?anio=2025&pesos=real&m=devengado&f=jur.3,prog.41), así pasa de una página a
// la otra y un enlace copiado abre la misma vista.
window.P = (() => {
  const D = window.DATOS, HX = window.HECHOS;
  const ANIOS = HX.anios.map(x => x[0]);
  const parcial = a => D.corte[a] !== "anual";

  // ---------- tabla de hechos: columnas e índices ----------
  const dims = HX.dims, C = HX.cols, N = C.prog.length;
  const RANGO = {};
  { let k = 0; for (const [a, n] of HX.anios) { RANGO[a] = [k, k + n]; k += n; } }
  const ANIO = new Int16Array(N);
  for (const a of ANIOS) ANIO.fill(a, ...RANGO[a]);
  const derivar = (col, tabla) => Int32Array.from(col, i => i < 0 ? -1 : tabla[i][0]);
  const COL = {
    prog: Int32Array.from(C.prog), obra: Int32Array.from(C.obra), fun: Int32Array.from(C.fun),
    ppal: Int32Array.from(C.ppal), fte: Int32Array.from(C.fte), com: Int32Array.from(C.com),
  };
  COL.jur = derivar(COL.prog, dims.prog);
  COL.fin = derivar(COL.fun, dims.fun);
  COL.inc = derivar(COL.ppal, dims.ppal);
  // los montos vienen en miles de pesos nominales
  const MS = Float64Array.from(C.s, x => x * 1000), MV = Float64Array.from(C.v, x => x * 1000), MD = Float64Array.from(C.d, x => x * 1000);

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
  const titulo = s => s.toLowerCase().replace(/(^|\s|\(|-|\.)(\p{L})/gu, (x, p, c) => p + c.toUpperCase())
    .replace(/\b(De|Del|La|Las|Los|Y|E|En|A|Al|Para|Por|Con|Sin|O)\b/g, w => w.toLowerCase())
    .replace(/^(\p{L})/u, c => c.toUpperCase());
  const MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
  const [pa, pm] = D.pesos_de.split("-");
  const pesosDe = `${MESES[+pm - 1]} de ${pa}`;
  const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (t, a, txt) => { const n = document.createElementNS(NS, t); for (const k in a) n.setAttribute(k, a[k]); if (txt != null) n.textContent = txt; return n; };

  // ---------- dimensiones ----------
  const DIM = {
    jur:  { nombre: "Jurisdicción", todas: "Todas las jurisdicciones", et: i => titulo(dims.jur[i]) },
    prog: { nombre: "Programa", todas: "Todos los programas", et: i => titulo(dims.prog[i][1]), padre: "jur" },
    obra: { nombre: "Obra", todas: "Todas las obras", et: i => titulo(dims.obra[i][1]), padre: "prog" },
    fin:  { nombre: "Finalidad", todas: "Todas las finalidades", et: i => titulo(dims.fin[i]) },
    fun:  { nombre: "Función", todas: "Todas las funciones", et: i => titulo(dims.fun[i][1]), padre: "fin" },
    inc:  { nombre: "Objeto del gasto", todas: "Todos los objetos", et: i => titulo(dims.inc[i]) },
    ppal: { nombre: "Partida", todas: "Todas las partidas", et: i => titulo(dims.ppal[i][1]), padre: "inc" },
    fte:  { nombre: "Fuente", todas: "Todas las fuentes", et: i => titulo(dims.fte[i]) },
  };
  const padreDe = { prog: i => dims.prog[i][0], obra: i => dims.obra[i][0], fun: i => dims.fun[i][0], ppal: i => dims.ppal[i][0] };
  const hijos = d => Object.keys(DIM).filter(k => DIM[k].padre === d);

  // ---------- estado ----------
  const url = new URLSearchParams(location.search);
  const MEDIDAS = {
    devengado: { nombre: "Devengado", m: MD }, vigente: { nombre: "Crédito vigente", m: MV },
    sancionado: { nombre: "Sancionado", m: MS }, ejecucion: { nombre: "Ejecución" },
  };
  const st = {
    anio: ANIOS.includes(+url.get("anio")) ? +url.get("anio") : ANIOS.filter(a => !parcial(a)).pop(),
    pesos: url.get("pesos") === "nominal" ? "nominal" : "real",
    medida: MEDIDAS[url.get("m")] ? url.get("m") : "devengado",
    f: {},
  };
  for (const par of (url.get("f") || "").split(",")) {
    const [d, i] = par.split(".");
    if (DIM[d] && Number.isInteger(+i) && +i >= 0 && +i < dims[d].length) st.f[d] = +i;
  }
  const f = a => st.pesos === "real" ? D.factor[a] : 1;

  // fijar un valor también fija sus padres; cambiarlo borra los hijos que ya no le corresponden
  function fijar(d, i) {
    st.f[d] = i;
    for (let x = d, j = i; DIM[x].padre; ) { const p = DIM[x].padre; j = padreDe[x](j); st.f[p] = j; x = p; }
    const limpiar = x => { for (const h of hijos(x)) { if (h in st.f && padreDe[h](st.f[h]) !== st.f[x]) { delete st.f[h]; } limpiar(h); } };
    limpiar(d);
  }
  function quitar(d) { delete st.f[d]; for (const h of hijos(d)) quitar(h); }

  // ---------- filtrar y sumar ----------
  // recorre las filas de un año (o de todos) que pasan los filtros, salvo los de `excluir`
  function recorrer(anio, excluir, fn) {
    const act = Object.entries(st.f).filter(([d]) => !excluir.includes(d)).map(([d, i]) => [COL[d], i]);
    const [a, b] = anio == null ? [0, N] : RANGO[anio];
    fila: for (let k = a; k < b; k++) {
      for (const [col, i] of act) if (col[k] !== i) continue fila;
      fn(k);
    }
  }
  // suma sancionado, vigente y devengado (nominales) por grupo; `por` es una dimensión o una función de la fila
  function sumar({ anio = st.anio, por = null, excluir = [], filtro = null } = {}) {
    const out = new Map();
    const clave = por == null ? () => 0 : typeof por === "function" ? por : (c => k => c[k])(por === "anio" ? ANIO : COL[por]);
    recorrer(anio, excluir, k => {
      if (filtro && !filtro(k)) return;
      const g = clave(k);
      let o = out.get(g);
      if (!o) out.set(g, o = { s: 0, v: 0, d: 0 });
      o.s += MS[k]; o.v += MV[k]; o.d += MD[k];
    });
    return out;
  }
  const total = (anio = st.anio, excluir = []) => sumar({ anio, excluir }).get(0) || { s: 0, v: 0, d: 0 };
  const esEjec = () => st.medida === "ejecucion";
  // el valor de la medida elegida para una suma de un año
  const valor = (o, anio = st.anio) => esEjec() ? (o.v ? o.d / o.v : NaN) : o[{ devengado: "d", vigente: "v", sancionado: "s" }[st.medida]] * f(anio);
  const fmt = (v, corto) => esEjec() ? pct(v, 0) : plata(v, corto);
  const filasMontos = (o, anio = st.anio) => [
    ["sancionado", plata(o.s * f(anio))], ["vigente", plata(o.v * f(anio))],
    ["devengado", plata(o.d * f(anio))], ["ejecución", pct(o.d / o.v)]];

  // ---------- tooltip (siempre textContent: las etiquetas vienen del dataset) ----------
  const tip = document.getElementById("tip");
  function mostrar(ev, titulo, filas, pie) {
    tip.replaceChildren(el("div", "t", titulo));
    for (const [k, v] of filas) { const r = el("div", "r"); r.append(el("b", null, v), el("span", null, k)); tip.append(r); }
    if (pie) tip.append(el("div", "pie", pie));
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
  function conTip(nodo, fnTitulo, fnFilas, pie) {
    nodo.tabIndex = 0;
    const on = ev => mostrar(ev, fnTitulo(), fnFilas(), pie);
    nodo.addEventListener("pointerenter", on); nodo.addEventListener("pointermove", mover);
    nodo.addEventListener("pointerleave", ocultar); nodo.addEventListener("focus", on); nodo.addEventListener("blur", ocultar);
  }
  const alActivar = (nodo, fn) => {
    nodo.addEventListener("click", fn);
    nodo.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); } });
  };

  // ---------- panel lateral ----------
  let render = () => {};
  const segA = document.getElementById("anios");
  if (segA) for (const a of ANIOS) {
    const b = el("button", null, String(a));
    b.type = "button";
    if (parcial(a)) { b.append(el("sup", null, "*")); b.title = "Hasta " + D.corte[a]; }
    b.dataset.anio = a;
    b.onclick = () => { st.anio = a; cambio(); };
    segA.append(b);
  }
  document.querySelectorAll("[data-pesos]").forEach(b => b.onclick = () => { st.pesos = b.dataset.pesos; cambio(); });
  const selM = document.getElementById("medida");
  if (selM) {
    for (const [k, m] of Object.entries(MEDIDAS)) selM.append(new Option(m.nombre, k));
    selM.onchange = () => { st.medida = selM.value; cambio(); };
  }

  // selectores de filtro: cada uno ofrece sólo lo que tiene gasto con los demás filtros puestos
  const SELECTORES = [
    { id: "f-jur", dims: ["jur"] }, { id: "f-prog", dims: ["prog"] }, { id: "f-obra", dims: ["obra"] },
    { id: "f-fun", dims: ["fin", "fun"] }, { id: "f-inc", dims: ["inc", "ppal"] }, { id: "f-fte", dims: ["fte"] },
  ];
  const descendientes = d => [d, ...hijos(d).flatMap(descendientes)];
  function selectores() {
    for (const { id, dims: ds } of SELECTORES) {
      const sel = document.getElementById(id);
      if (!sel) continue;
      const [d0, d1] = ds;
      const hay = sumar({ por: d1 || d0, excluir: descendientes(d0) });
      const actual = d1 && d1 in st.f ? `${d1}.${st.f[d1]}` : d0 in st.f ? `${d0}.${st.f[d0]}` : "";
      sel.replaceChildren(new Option(DIM[d0].todas, ""));
      if (!d1) {
        const ops = [...hay.keys()].filter(i => i >= 0).map(i => [i, DIM[d0].et(i)]).sort((a, b) => a[1].localeCompare(b[1], "es"));
        for (const [i, t] of ops) sel.append(new Option(t, `${d0}.${i}`));
        // lo elegido se muestra aunque con los otros filtros no tenga gasto
        if (d0 in st.f && !hay.has(st.f[d0])) sel.append(new Option(DIM[d0].et(st.f[d0]), `${d0}.${st.f[d0]}`));
      } else {
        const grupos = new Map();
        for (const i of hay.keys()) { const p = padreDe[d1](i); if (!grupos.has(p)) grupos.set(p, []); grupos.get(p).push(i); }
        const orden = [...grupos.keys()].sort((a, b) => DIM[d0].et(a).localeCompare(DIM[d0].et(b), "es"));
        for (const p of orden) {
          const og = document.createElement("optgroup"); og.label = DIM[d0].et(p);
          og.append(new Option("Toda la " + DIM[d0].nombre.toLowerCase() + ": " + DIM[d0].et(p), `${d0}.${p}`));
          for (const i of grupos.get(p).sort((a, b) => DIM[d1].et(a).localeCompare(DIM[d1].et(b), "es")))
            og.append(new Option(DIM[d1].et(i), `${d1}.${i}`));
          sel.append(og);
        }
      }
      sel.value = actual;
      sel.disabled = sel.options.length <= 1;
    }
  }
  for (const { id, dims: ds } of SELECTORES) {
    const sel = document.getElementById(id);
    if (!sel) continue;
    sel.onchange = () => {
      if (!sel.value) quitar(ds[0]);
      else { const [d, i] = sel.value.split("."); quitar(ds[0]); fijar(d, +i); }
      cambio();
    };
  }

  // los filtros activos, arriba del contenido, cada uno con su cruz
  function activos() {
    const box = document.getElementById("activos");
    if (!box) return;
    const orden = Object.keys(DIM).filter(d => d in st.f);
    box.replaceChildren();
    box.classList.toggle("on", orden.length > 0);
    if (!orden.length) return;
    box.append(el("span", "lab", "Filtrando"));
    for (const d of orden) {
      const b = el("button", "chip"); b.type = "button";
      b.append(el("small", null, DIM[d].nombre), document.createTextNode(DIM[d].et(st.f[d])), el("span", "x", "×"));
      b.setAttribute("aria-label", `Quitar filtro ${DIM[d].nombre}: ${DIM[d].et(st.f[d])}`);
      b.onclick = () => { quitar(d); cambio(); };
      box.append(b);
    }
    const l = el("button", "limpiar", "Limpiar todo"); l.type = "button";
    l.onclick = () => { st.f = {}; cambio(); };
    box.append(l);
  }

  const consulta = () => {
    const fs = Object.keys(DIM).filter(d => d in st.f).map(d => `${d}.${st.f[d]}`).join(",");
    return `?anio=${st.anio}&pesos=${st.pesos}&m=${st.medida}` + (fs ? "&f=" + fs : "");
  };
  function cambio() {
    const q = consulta();
    history.replaceState(null, "", q + location.hash);
    // los enlaces a la otra página se llevan el estado
    document.querySelectorAll("a[data-pagina]").forEach(a => {
      a.dataset.base ||= a.getAttribute("href");
      const [base, ancla] = a.dataset.base.split("#");
      a.href = base + q + (ancla ? "#" + ancla : "");
    });
    document.querySelectorAll("[data-anio]").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.anio === st.anio)));
    document.querySelectorAll("[data-pesos]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.pesos === st.pesos)));
    if (selM) selM.value = st.medida;
    document.querySelectorAll(".lead-pesos").forEach(e => e.textContent = st.pesos === "real" ? "pesos de " + pesosDe : "pesos corrientes de cada año");
    const av = document.getElementById("aviso-2026");
    if (av) av.classList.toggle("on", parcial(st.anio));
    selectores(); activos();
    ocultar();
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
  // en el celular el panel es una barra arriba; filtros y secciones se abren con un botón
  const lateral = document.getElementById("lateral"), menu = document.getElementById("menu");
  menu.onclick = () => { const on = lateral.classList.toggle("abierta"); menu.setAttribute("aria-expanded", String(on)); };
  lateral.querySelectorAll("nav a").forEach(a => a.addEventListener("click", () => {
    lateral.classList.remove("abierta"); menu.setAttribute("aria-expanded", "false");
  }));

  // ---------- gráfico por jerarquía: barras o treemap, con filtro cruzado y bajada de nivel ----------
  // Muestra el primer nivel de la jerarquía que no está filtrado. Clic en un elemento lo filtra (y así baja un
  // nivel); el camino de arriba permite volver. En el último nivel, lo elegido queda resaltado entre sus pares.
  const vistas = {}, abiertos = {};
  function jerarquia(id, niveles, { resto, max = 12 } = {}) {
    const caja = document.getElementById(id);
    const vista = esEjec() ? "barras" : (vistas[id] || "barras");
    let nivel = niveles.findIndex(d => !(d in st.f));
    if (nivel < 0) nivel = niveles.length - 1;
    const d = niveles[nivel];
    const grupos = sumar({ por: d, excluir: descendientes(d) });
    const sinClave = grupos.get(-1); grupos.delete(-1);
    let items = [...grupos].map(([i, o]) => ({ i, o, v: valor(o), et: DIM[d].et(i) }))
      .filter(x => esEjec() ? x.o.v > 0 : x.v > 0).sort((a, b) => b.v - a.v);
    // el total incluye lo que no tiene clave (p. ej. gasto sin obra) sólo cuando se muestra como resto
    const tot = items.reduce((t, x) => t + (esEjec() ? 0 : x.v), 0) + (resto && sinClave && !esEjec() ? Math.max(0, valor(sinClave)) : 0);
    caja.replaceChildren();

    // camino y cambio de vista
    const barra = el("div", "herr-graf");
    const camino = el("nav", "camino"); camino.setAttribute("aria-label", "Nivel");
    const paso = (txt, fn, actual) => {
      const b = el(actual ? "span" : "button", actual ? "aqui" : null, txt);
      if (!actual) { b.type = "button"; b.onclick = fn; }
      camino.append(b);
    };
    paso(DIM[niveles[0]].todas, () => { quitar(niveles[0]); cambio(); }, nivel === 0 && !(niveles[0] in st.f));
    for (let j = 0; j < niveles.length; j++) {
      const dj = niveles[j];
      if (!(dj in st.f)) break;
      camino.append(el("span", "sep", "›"));
      const ultimo = j === niveles.length - 1 || !(niveles[j + 1] in st.f);
      paso(DIM[dj].et(st.f[dj]), () => { for (const h of hijos(dj)) quitar(h); cambio(); }, ultimo && j === niveles.length - 1);
    }
    barra.append(camino);
    const seg = el("div", "seg chico"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Vista");
    for (const [k, t] of [["barras", "Barras"], ["treemap", "Rectángulos"]]) {
      const b = el("button", null, t); b.type = "button";
      b.setAttribute("aria-pressed", String(vista === k));
      if (k === "treemap" && esEjec()) { b.disabled = true; b.title = "La ejecución es un porcentaje: no se reparte en rectángulos"; }
      b.onclick = () => { vistas[id] = k; jerarquia(id, niveles, { resto, max }); };
      seg.append(b);
    }
    barra.append(seg);
    caja.append(barra);

    if (!items.length) {
      caja.append(el("p", "vacio", sinClave && resto
        ? `Nada de esto tiene ${DIM[d].nombre.toLowerCase()}s identificadas en ${st.anio}: todo el gasto va sin ${DIM[d].nombre.toLowerCase()}.`
        : "No hay gasto con estos filtros en " + st.anio + "."));
      return;
    }
    const elegido = d in st.f ? st.f[d] : null;
    const titulo = x => x.et;
    const tipFilas = x => [...(esEjec() ? [] : [["del total", pct(x.v / tot)]]), ...filasMontos(x.o)];
    const pie = nivel < niveles.length - 1 ? "Clic para filtrar y ver " + DIM[niveles[nivel + 1]].nombre.toLowerCase() + "s" : "Clic para filtrar";
    const elegir = x => { if (elegido === x.i) quitar(d); else fijar(d, x.i); cambio(); };

    if (vista === "treemap") {
      const W = Math.max(280, caja.clientWidth || 600), H = W < 500 ? 300 : 380;
      const vis = items.slice(0, 40);
      const rects = cuadros(vis.map(x => x.v), W, H);
      const s = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "treemap", role: "group", "aria-label": DIM[d].nombre + " en rectángulos" });
      vis.forEach((x, n) => {
        const [rx, ry, rw, rh] = rects[n];
        const g = svgEl("g", { class: "celda" + (elegido === x.i ? " elegida" : elegido != null ? " apagada" : "") });
        g.append(svgEl("rect", { x: rx + 1, y: ry + 1, width: Math.max(0, rw - 2), height: Math.max(0, rh - 2), rx: 3 }));
        if (rw > 70 && rh > 34) {
          const chars = Math.floor((rw - 12) / 7);
          g.append(svgEl("text", { x: rx + 7, y: ry + 18, class: "et" }, x.et.length > chars ? x.et.slice(0, chars - 1) + "…" : x.et));
          g.append(svgEl("text", { x: rx + 7, y: ry + 34, class: "va" }, fmt(x.v, true) + " · " + pct(x.v / tot, 0)));
        }
        conTip(g, () => titulo(x), () => tipFilas(x), pie);
        g.setAttribute("aria-label", `${x.et}: ${fmt(x.v)}`);
        alActivar(g, () => elegir(x));
        s.append(g);
      });
      caja.append(s);
      if (items.length > vis.length) caja.append(el("p", "nota", `Se muestran los ${vis.length} más grandes de ${items.length}.`));
      return;
    }

    const lista = el("div", "barras");
    const maxv = Math.max(...items.map(x => x.v), 1e-9);
    const todos = abiertos[id] || items.length <= max + 2;
    for (const x of todos ? items : items.slice(0, max)) {
      const fila = el("div", "fila clic" + (elegido === x.i ? " elegida" : elegido != null ? " apagada" : ""));
      const et = el("div", "et", x.et); et.title = x.et;
      const pista = el("div", "pista"), b = el("div", "barra");
      b.style.width = Math.max(0.3, 100 * x.v / maxv) + "%"; pista.append(b);
      const num = el("div", "num", fmt(x.v, true));
      if (!esEjec()) num.append(el("small", null, pct(x.v / tot)));
      fila.append(et, pista, num);
      conTip(fila, () => titulo(x), () => tipFilas(x), pie);
      alActivar(fila, () => elegir(x));
      lista.append(fila);
    }
    if (sinClave && resto && !esEjec() && valor(sinClave) > 0) {
      const fila = el("div", "fila resto");
      const pista = el("div", "pista"), b = el("div", "barra");
      b.style.width = Math.max(0.3, 100 * valor(sinClave) / maxv) + "%"; pista.append(b);
      const num = el("div", "num", fmt(valor(sinClave), true)); num.append(el("small", null, pct(valor(sinClave) / tot)));
      fila.append(el("div", "et", resto), pista, num);
      lista.append(fila);
    }
    caja.append(lista);
    if (items.length > max + 2) {
      const b = el("button", "mas", todos ? "Mostrar menos" : `Mostrar los ${items.length}`); b.type = "button";
      b.onclick = () => { abiertos[id] = !todos; jerarquia(id, niveles, { resto, max }); };
      caja.append(b);
    }
  }

  // treemap "squarified": filas de rectángulos lo más cuadrados posible
  function cuadros(vals, W, H) {
    const tot = vals.reduce((a, b) => a + b, 0);
    const area = vals.map(v => v * W * H / tot);
    const out = [];
    let x = 0, y = 0, w = W, h = H, i = 0;
    while (i < area.length) {
      const lado = Math.min(w, h);
      const peor = f => { const s = f.reduce((a, b) => a + b, 0); return Math.max(lado * lado * Math.max(...f) / (s * s), s * s / (lado * lado * Math.min(...f))); };
      let fila = [area[i]], j = i + 1;
      while (j < area.length && peor([...fila, area[j]]) <= peor(fila)) fila.push(area[j++]);
      const s = fila.reduce((a, b) => a + b, 0);
      if (w >= h) { const cw = s / h; let yy = y; for (const a of fila) { out.push([x, yy, cw, a / cw]); yy += a / cw; } x += cw; w -= cw; }
      else { const rh = s / w; let xx = x; for (const a of fila) { out.push([xx, y, a / rh, rh]); xx += a / rh; } y += rh; h -= rh; }
      i = j;
    }
    return out;
  }

  // ---------- mapa de las comunas ----------
  const GEO = Object.fromEntries(D.mapa.comunas.map(c => [c.comuna, c]));
  // gasto de cada comuna como unidad ejecutora, con los filtros puestos
  function comunas(anio = st.anio) {
    const g = sumar({ anio, por: "com" });
    g.delete(0);
    return g;
  }
  // siete tonos de la escala secuencial, repartidos parejo entre el mínimo y el máximo
  const escala = (min, max) => v => max > min ? 1 + Math.min(6, Math.floor(7 * (v - min) / (max - min))) : 4;
  function mapa(caja, { valor, elegida, alElegir, enlazar, rotulo }) {
    const { ancho, alto } = D.mapa;
    const s = svgEl("svg", { viewBox: `-4 -4 ${ancho + 8} ${alto + 8}`, role: "group", "aria-label": rotulo });
    const vals = D.mapa.comunas.map(c => valor(c.comuna)).filter(v => v != null && isFinite(v));
    const min = Math.min(...vals), max = Math.max(...vals), tono = escala(min, max);
    let sel = null;
    for (const c of D.mapa.comunas) {
      const v = valor(c.comuna);
      const p = svgEl("path", { d: c.d, fill: v != null && isFinite(v) ? `var(--seq-${tono(v)})` : "var(--seq-0)" });
      p.dataset.comuna = c.comuna;
      if (c.comuna === elegida) { p.classList.add("elegida"); sel = p; }
      if (enlazar) enlazar(p, c.comuna);
      if (alElegir) alActivar(p, () => alElegir(c.comuna));
      s.append(p);
    }
    // la elegida va al final para que su borde no quede tapado por las vecinas
    if (sel) s.append(sel);
    for (const c of D.mapa.comunas) s.append(svgEl("text", { x: c.x, y: c.y }, c.comuna));
    caja.replaceChildren(s);
    return { min: vals.length ? min : 0, max: vals.length ? max : 0 };
  }
  function leyenda(caja, min, max, fmtV, unidad) {
    const esc = el("div", "escala");
    for (let i = 1; i <= 7; i++) { const t = el("span"); t.style.background = `var(--seq-${i})`; esc.append(t); }
    caja.replaceChildren(el("span", null, fmtV(min)), esc, el("span", null, fmtV(max)), ...(unidad ? [el("span", null, unidad)] : []));
  }

  return {
    D, HX, DIM, dims, COL, MEDIDAS, ANIOS, GEO, st, nf, plata, pct, f, titulo, pesosDe, el, svgEl, parcial,
    conTip, mostrar, ocultar, alActivar, filasMontos, sumar, total, valor, fmt, esEjec, fijar, quitar,
    jerarquia, comunas, mapa, leyenda,
    iniciar(fn) { render = fn; cambio(); },
    cambiar: cambio,
  };
})();
