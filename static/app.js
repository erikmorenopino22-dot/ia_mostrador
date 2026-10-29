"use strict";
/* Mostrador: interfaz web que usa la API del backend. */

/* ---------- utilidades ---------- */
const $ = s => document.querySelector(s);
function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) { if (c == null || c === false) continue; e.append(c instanceof Node ? c : document.createTextNode(String(c))); }
  return e;
}
const fecha = t => t ? new Date(t).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" }) : "";
const fmt = n => n == null ? "–" : (Math.round(n * 10) / 10).toString().replace(".", ",");
const NIVEL = { logrado: "Logrado", parcial: "En parte", no_logrado: "No logrado" };
const ESTADO = { en_curso: "En curso", entregada: "Pendiente de revisar", revisada: "Revisada" };
function aviso(msg, tipo) {
  const box = $("#avisoGlobal"); box.innerHTML = "";
  if (msg) box.append(el("div", { class: "aviso" + (tipo === "error" ? " error" : "") }, msg));
}
const guardar = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} };
const leerLS = k => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (_) { return null; } };

/* ---------- API ---------- */
const S = { token: leerLS("mostrador-token"), rol: null, nombre: "", grupo: null, tab: null,
            casos: [], sesion: null, ocupado: false, esperando: null, detalle: null, editando: null, grupos: [], filtro: "entregada", filtroGrupo: "" };

async function api(metodo, ruta, cuerpo) {
  const r = await fetch("/api" + ruta, {
    method: metodo,
    headers: { "Content-Type": "application/json", ...(S.token ? { Authorization: "Bearer " + S.token } : {}) },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  }).catch(() => { throw new Error("No hay conexión con el servidor. Comprueba tu conexión a internet."); });
  let datos = null;
  try { datos = await r.json(); } catch (_) {}
  if (r.status === 401 && S.token) { salir(); throw new Error((datos && datos.detail) || "La sesión ha caducado. Vuelve a entrar."); }
  if (!r.ok) {
    let d = datos && datos.detail;
    if (Array.isArray(d)) d = "Revisa los datos: hay algún campo incompleto o con un formato no válido.";
    throw new Error(d || "Ha ocurrido un error. Inténtalo de nuevo.");
  }
  return datos;
}

/* ---------- preferencias de lectura (solo en este navegador) ---------- */
let prefs = { size: "normal", font: "atk", idioma: "es", espacio: false, voz: false, ...(leerLS("mostrador-prefs") || {}) };
function aplicarPrefs() {
  const h = document.documentElement;
  h.dataset.size = prefs.size; h.dataset.font = prefs.font; h.dataset.espacio = prefs.espacio ? "si" : "no";
  document.querySelectorAll('input[name="size"]').forEach(i => i.checked = i.value === prefs.size);
  document.querySelectorAll('input[name="font"]').forEach(i => i.checked = i.value === prefs.font);
  document.querySelectorAll('input[name="idioma"]').forEach(i => i.checked = i.value === prefs.idioma);
  $("#optEspacio").checked = prefs.espacio; $("#optVoz").checked = prefs.voz;
}
$("#ajustes").addEventListener("change", e => {
  const t = e.target;
  if (t.name === "size") prefs.size = t.value;
  if (t.name === "font") prefs.font = t.value;
  if (t.name === "idioma") prefs.idioma = t.value;
  if (t.id === "optEspacio") prefs.espacio = t.checked;
  if (t.id === "optVoz") { prefs.voz = t.checked; if (!t.checked) try { speechSynthesis.cancel(); } catch (_) {} }
  guardar("mostrador-prefs", prefs); aplicarPrefs();
});
$("#btnAjustes").addEventListener("click", () => {
  const p = $("#ajustes"); p.hidden = !p.hidden; $("#btnAjustes").setAttribute("aria-expanded", String(!p.hidden));
});
const hayVoz = "speechSynthesis" in window;
if (!hayVoz) $("#lblVoz").hidden = true;
function leer(texto) {
  if (!hayVoz) return;
  try { speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(texto); u.lang = prefs.idioma === "va" ? "ca-ES" : "es-ES"; u.rate = 0.95; speechSynthesis.speak(u); } catch (_) {}
}
const Reconocimiento = window.SpeechRecognition || window.webkitSpeechRecognition;
aplicarPrefs();

/* ---------- sesión de usuario ---------- */
function salir() {
  S.token = null; S.rol = null; guardar("mostrador-token", null);
  S.sesion = null; S.detalle = null; S.editando = null;
  pintarCabecera(); render();
}
$("#btnSalir").addEventListener("click", salir);

function pintarCabecera() {
  $("#quien").textContent = S.rol ? (S.rol === "profe" ? S.nombre : `${S.nombre}${S.grupo ? " (" + S.grupo + ")" : ""}`) : "";
  $("#btnSalir").hidden = !S.rol;
  const nav = $("#tabs"); nav.innerHTML = ""; nav.hidden = !S.rol;
  if (!S.rol) return;
  const tabs = S.rol === "profe"
    ? [["grupos", "Grupos"], ["casos", "Casos y rúbricas"], ["entregas", "Revisar entregas"]]
    : [["practicar", "Practicar"], ["mis", "Mis prácticas"]];
  if (!S.tab || !tabs.some(t => t[0] === S.tab)) S.tab = tabs[0][0];
  for (const [id, txt] of tabs) nav.append(el("button", { role: "tab", "aria-selected": String(id === S.tab), onclick: () => irA(id) }, txt));
}
function irA(tab) { S.tab = tab; S.detalle = null; S.editando = null; aviso(""); pintarCabecera(); cargarTab(); }

async function cargarTab() {
  render();
  try {
    if (S.tab === "practicar" || S.tab === "casos") S.casos = await api("GET", "/casos");
    if (S.tab === "mis") S.mis = await api("GET", "/sesiones");
    if (S.tab === "grupos" || S.tab === "entregas") S.grupos = await api("GET", "/grupos");
    if (S.tab === "grupos") { S.estado = await api("GET", "/estado"); S.profesores = await api("GET", "/profesores"); }
    if (S.tab === "entregas") await cargarEntregas();
  } catch (e) { aviso(e.message, "error"); }
  render();
}
async function cargarEntregas() {
  const q = new URLSearchParams();
  if (S.filtro !== "todas") q.set("estado", S.filtro);
  if (S.filtroGrupo) q.set("grupo_id", S.filtroGrupo);
  S.entregas = await api("GET", "/entregas?" + q);
}

function render() {
  const v = $("#vista"); v.innerHTML = "";
  if (S.configurar) { v.append(vistaConfiguracion()); return; }
  if (!S.rol) { v.append(vistaLogin()); return; }
  const vistas = {
    practicar: () => S.sesion ? vistaChat() : vistaListaCasos(),
    mis: () => S.detalle ? vistaDetalle(S.detalle, false) : vistaMis(),
    grupos: vistaGrupos,
    casos: () => S.editando ? editorCaso(S.editando) : vistaCasos(),
    entregas: () => S.detalle ? vistaDetalle(S.detalle, true) : vistaEntregas(),
  };
  v.append(vistas[S.tab]());
}

/* ---------- acceso ---------- */
let modoLogin = "alumno";
function vistaLogin() {
  const f = el("section", { class: "login" });
  const sel = el("div", { class: "seg", role: "radiogroup", "aria-label": "Tipo de acceso" },
    [["alumno", "Soy alumno/a"], ["profe", "Soy profesor/a"]].map(([v, t]) =>
      el("label", {}, el("input", { type: "radio", name: "modo", value: v, checked: modoLogin === v, onchange: () => { modoLogin = v; render(); } }), " " + t)));
  const caja = el("div", { class: "caja" }, el("h2", { class: "seccion", style: "margin:0" }, "Entrar"), sel);
  const estado = el("p", { role: "status" });
  const campo = (id, label, attrs, ayuda) => el("div", { class: "campo" }, el("label", { for: id }, label, ayuda ? el("span", { class: "ayuda" }, ayuda) : null), el("input", { id, ...attrs }));
  if (modoLogin === "alumno") {
    caja.append(
      campo("lCodigo", "Código del grupo", { type: "text", autocomplete: "off", autocapitalize: "characters", required: true }, "Te lo da tu profesora. Son 6 letras y números."),
      campo("lAlias", "Tu nombre en la aplicación", { type: "text", autocomplete: "nickname", maxlength: "40", required: true }, "Usa el que te indique tu profesora, por ejemplo tu nombre y la inicial del apellido."),
      campo("lPin", "PIN", { type: "password", inputmode: "numeric", pattern: "[0-9]*", maxlength: "8", autocomplete: "current-password", required: true }, "De 4 a 8 números. La primera vez que entras, el PIN que escribas será el tuyo."));
  } else {
    caja.append(
      campo("lEmail", "Correo", { type: "email", autocomplete: "username", required: true }),
      campo("lPass", "Contraseña", { type: "password", autocomplete: "current-password", required: true }));
  }
  const btn = el("button", { class: "btn primary", onclick: async () => {
    btn.disabled = true; estado.textContent = "Entrando…";
    try {
      const r = modoLogin === "alumno"
        ? await api("POST", "/alumno/entrar", { codigo: $("#lCodigo").value.trim(), alias: $("#lAlias").value.trim(), pin: $("#lPin").value.trim() })
        : await api("POST", "/profe/login", { email: $("#lEmail").value.trim(), password: $("#lPass").value });
      S.token = r.token; S.rol = r.rol; S.nombre = r.nombre; S.grupo = r.grupo; guardar("mostrador-token", r.token);
      S.tab = null; pintarCabecera(); cargarTab();
    } catch (e) { estado.textContent = e.message; btn.disabled = false; }
  } }, "Entrar");
  caja.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.tagName === "INPUT") btn.click(); });
  caja.append(btn, estado);
  f.append(caja);
  return f;
}

/* ---------- alumnado: casos y chat ---------- */
function vistaListaCasos() {
  const f = document.createDocumentFragment();
  f.append(el("h2", { class: "seccion" }, "Elige un caso para practicar"));
  if (!S.casos.length) { f.append(el("div", { class: "vacio" }, "Tu profesora todavía no ha publicado casos.")); return f; }
  const g = el("div", { class: "casos" });
  for (const c of S.casos) g.append(el("article", { class: "caso" },
    c.modulo ? el("span", { class: "modulo" }, c.modulo) : null, el("h3", {}, c.titulo), el("p", {}, c.situacion),
    el("div", {}, el("button", { class: "btn primary", onclick: () => empezar(c.id) }, "Empezar práctica"))));
  f.append(g);
  return f;
}
async function empezar(casoId) {
  try {
    S.sesion = await api("POST", "/sesiones", { caso_id: casoId, idioma: prefs.idioma });
    render(); if (prefs.voz) leer(S.sesion.mensajes[0].t);
  } catch (e) { aviso(e.message, "error"); }
}
async function accion(tipo, texto) {
  const s = S.sesion; if (!s || S.ocupado) return;
  if (tipo === "mensaje" && !texto.trim()) return;
  S.ocupado = true; S.esperando = tipo === "mensaje" ? { r: "alumno", t: texto.trim() } : null; S.tipoEspera = tipo;
  aviso(""); render();
  try {
    const ruta = tipo === "mensaje" ? "mensajes" : tipo;
    const antes = s.mensajes.length;
    S.sesion = await api("POST", `/sesiones/${s.id}/${ruta}`, tipo === "mensaje" ? { texto: texto.trim() } : undefined);
    S.ocupado = false; S.esperando = null; render();
    const nuevo = S.sesion.mensajes.slice(antes).filter(m => m.r !== "alumno").pop();
    if (prefs.voz && nuevo && tipo !== "terminar") leer(nuevo.t);
  } catch (e) {
    S.ocupado = false; S.esperando = null; render();
    if (tipo === "mensaje") { const ta = $("#entradaTexto"); if (ta) ta.value = texto; }
    aviso(e.message, "error");
  }
}
function desplazar() { const l = $(".log"); if (l) l.scrollTop = l.scrollHeight; }
function burbuja(m, alias) {
  const quien = m.r === "cliente" ? "Cliente" : m.r === "alumno" ? (alias || "Tú") : "Pista";
  return el("div", { class: "msg " + m.r },
    el("span", { class: "quien" }, quien),
    el("span", { class: "cuerpo" + (m.t ? "" : " pensando") }, m.t || "Pensando…"),
    (m.r !== "alumno" && m.t && hayVoz) ? el("div", {}, el("button", { class: "btn small quiet oir", onclick: () => leer(m.t), "aria-label": "Escuchar este mensaje" }, "🔊 Escuchar")) : null);
}
function vistaChat() {
  const s = S.sesion, terminado = s.estado !== "en_curso";
  const esc = el("section", { class: "escena" });
  esc.append(el("div", { class: "escena-cab" },
    el("div", {}, s.modulo ? el("span", { class: "modulo" }, s.modulo) : null, el("h2", {}, s.caso_titulo), el("p", {}, s.situacion)),
    el("div", { class: "acciones" },
      !terminado ? el("button", { class: "btn amber", disabled: S.ocupado, onclick: () => accion("terminar") }, "Terminar y ver valoración") : null,
      el("button", { class: "btn quiet", disabled: S.ocupado, onclick: () => { S.sesion = null; cargarTab(); } }, terminado ? "Volver a los casos" : "Salir (se guarda)"))));
  if (!terminado && s.rubrica.length) esc.append(el("details", { class: "rubrica-alumno" }, el("summary", {}, "Qué se valora en este caso"),
    el("ul", {}, s.rubrica.map(r => el("li", {}, `${r.texto} (${fmt(r.puntos)} p.)`)))));
  const log = el("div", { class: "log", role: "log", "aria-live": "polite", "aria-label": "Conversación con el cliente" });
  s.mensajes.forEach(m => log.append(burbuja(m)));
  if (S.ocupado && S.tipoEspera === "mensaje") { log.append(burbuja(S.esperando)); log.append(burbuja({ r: "cliente", t: "" })); }
  if (S.ocupado && S.tipoEspera === "pista") log.append(burbuja({ r: "pista", t: "" }));
  esc.append(log);
  if (!terminado) {
    const ta = el("textarea", { id: "entradaTexto", placeholder: "Escribe lo que le dices al cliente…", "aria-label": "Tu respuesta al cliente", disabled: S.ocupado, maxlength: "1200" });
    ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); accion("mensaje", ta.value); } });
    const botones = el("div", { class: "botones" });
    if (Reconocimiento) botones.append(el("button", { class: "btn quiet", disabled: S.ocupado, onclick: () => dictar(ta), "aria-label": "Dictar con el micrófono" }, "🎤 Dictar"));
    botones.append(el("button", { class: "btn amber", disabled: S.ocupado, onclick: () => accion("pista") }, "Pedir pista"));
    botones.append(el("button", { class: "btn primary", disabled: S.ocupado, onclick: () => accion("mensaje", ta.value) }, "Enviar"));
    esc.append(el("div", { class: "entrada" }, ta, botones));
    esc.append(el("div", { class: "estado-linea", id: "estadoLinea" },
      S.ocupado && S.tipoEspera === "terminar" ? "Preparando la valoración… puede tardar hasta un minuto." : "Pulsa Intro para enviar. Mayúsculas + Intro para cambiar de línea."));
  } else esc.append(bloqueValoracion(s, false));
  setTimeout(() => { desplazar(); const t = $("#entradaTexto"); if (t && !S.ocupado) t.focus(); }, 0);
  return esc;
}
function dictar(ta) {
  try {
    const r = new Reconocimiento(); r.lang = prefs.idioma === "va" ? "ca-ES" : "es-ES";
    const linea = $("#estadoLinea"); if (linea) linea.textContent = "Escuchando… habla ahora.";
    r.onresult = e => { ta.value = (ta.value ? ta.value + " " : "") + e.results[0][0].transcript; ta.focus(); };
    r.onerror = () => { if (linea) linea.textContent = "No se puede usar el micrófono. Escribe tu respuesta."; };
    r.onend = () => { if (linea && linea.textContent.startsWith("Escuchando")) linea.textContent = ""; };
    r.start();
  } catch (_) { aviso("El dictado por voz no funciona en este navegador."); }
}

/* ---------- valoración ---------- */
function totalProfe(s) { return s.rubrica.reduce((a, r) => a + (Number(s.evaluacion_profe?.puntos?.[r.id]) || 0), 0); }
function bloqueValoracion(s, modoProfe) {
  const box = el("div", { class: "valoracion" });
  const max = s.rubrica.reduce((a, r) => a + r.puntos, 0);
  const ev = s.evaluacion_profe;
  if (ev && !modoProfe) box.append(el("div", { class: "caja profe" },
    el("h3", {}, "Nota de tu profesora"), el("div", { class: "total" }, `${fmt(totalProfe(s))} de ${fmt(max)} puntos`),
    s.rubrica.map(r => el("div", { class: "crit" }, el("span", { class: "txt" }, r.texto), el("span", {}, `${fmt(Number(ev.puntos?.[r.id]) || 0)} / ${fmt(r.puntos)}`))),
    ev.comentario ? el("p", {}, el("strong", {}, "Comentario: "), ev.comentario) : null));
  const p = s.propuesta_ia;
  if (!p) { if (!ev) box.append(el("p", {}, "Esta práctica todavía no tiene valoración.")); return box; }
  const totIA = p.criterios.reduce((a, c) => a + c.puntos, 0);
  box.append(el("div", { class: "caja" },
    el("h3", {}, modoProfe ? "Propuesta de la IA" : "Valoración orientativa"),
    el("p", { class: "nota-ia" }, modoProfe ? "Es una propuesta automática para ayudarte a revisar. La nota final la decides tú." : "La ha preparado la IA para ayudarte a aprender. La nota final la pone tu profesora."),
    el("div", { class: "total" }, `${fmt(totIA)} de ${fmt(max)} puntos`),
    p.criterios.map(c => {
      const r = s.rubrica.find(x => x.id === c.id) || { texto: c.id, puntos: 0 };
      return el("div", { class: "crit" }, el("span", { class: "txt" }, r.texto),
        el("span", {}, el("span", { class: "nivel " + c.nivel }, NIVEL[c.nivel]), ` ${fmt(c.puntos)} / ${fmt(r.puntos)}`),
        c.evidencia ? el("span", { class: "ev" }, c.evidencia) : null);
    }),
    p.fortalezas ? el("p", {}, el("strong", {}, "Lo que has hecho bien: "), p.fortalezas) : null,
    p.mejorar ? el("p", {}, el("strong", {}, "Para mejorar: "), p.mejorar) : null));
  return box;
}

/* ---------- alumnado: mis prácticas ---------- */
function tablaSesiones(filas, columnas) {
  return el("div", { class: "tabla" }, el("table", {},
    el("thead", {}, el("tr", {}, columnas.map(h => el("th", { scope: "col" }, h)))),
    el("tbody", {}, filas)));
}
function vistaMis() {
  const f = document.createDocumentFragment();
  f.append(el("h2", { class: "seccion" }, "Mis prácticas"));
  if (!S.mis) { f.append(el("p", { class: "pensando" }, "Cargando…")); return f; }
  if (!S.mis.length) { f.append(el("div", { class: "vacio" }, "Aún no has hecho ninguna práctica. Empieza una en la pestaña Practicar.")); return f; }
  f.append(tablaSesiones(S.mis.map(s => el("tr", {},
    el("td", {}, s.caso_titulo), el("td", {}, fecha(s.inicio)),
    el("td", {}, el("span", { class: "estado " + s.estado }, ESTADO[s.estado])),
    el("td", {}, s.puntos_profe != null ? `${fmt(s.puntos_profe)} / ${fmt(s.puntos_max)}` : "–"),
    el("td", {}, el("button", { class: "btn small", onclick: () => abrirSesion(s.id, false) }, s.estado === "en_curso" ? "Continuar" : "Ver")))),
    ["Caso", "Fecha", "Estado", "Nota", ""]));
  return f;
}
async function abrirSesion(id, modoProfe) {
  try {
    const s = await api("GET", "/sesiones/" + id);
    if (!modoProfe && s.estado === "en_curso") { S.sesion = s; S.tab = "practicar"; pintarCabecera(); render(); return; }
    S.detalle = s; render();
  } catch (e) { aviso(e.message, "error"); }
}

/* ---------- detalle (ambos) ---------- */
function vistaDetalle(s, modoProfe) {
  const f = el("section", { class: "escena" });
  f.append(el("div", { class: "escena-cab" },
    el("div", {}, el("span", { class: "modulo" }, modoProfe ? `${s.alias} (${s.grupo})` : s.modulo), el("h2", {}, s.caso_titulo),
      el("p", {}, fecha(s.inicio) + (s.pistas ? `  (pidió ${s.pistas} pista${s.pistas > 1 ? "s" : ""})` : ""))),
    el("div", { class: "acciones" }, el("button", { class: "btn quiet", onclick: () => { S.detalle = null; cargarTab(); } }, "Volver a la lista"))));
  const log = el("div", { class: "log", "aria-label": "Conversación" });
  s.mensajes.forEach(m => log.append(burbuja(m, modoProfe ? s.alias : null)));
  f.append(log, bloqueValoracion(s, modoProfe));
  if (modoProfe && s.estado !== "en_curso") f.append(formNota(s));
  return f;
}
function formNota(s) {
  const previa = s.evaluacion_profe?.puntos || {};
  const caja = el("div", { class: "caja profe" }, el("h3", {}, "Tu nota"));
  const inputs = {}, max = s.rubrica.reduce((a, r) => a + r.puntos, 0);
  const totalEl = el("div", { class: "total", "aria-live": "polite" });
  const actualizar = () => { totalEl.textContent = `${fmt(s.rubrica.reduce((a, r) => a + (Number(inputs[r.id].value) || 0), 0))} de ${fmt(max)} puntos`; };
  for (const r of s.rubrica) {
    const ia = s.propuesta_ia?.criterios.find(c => c.id === r.id);
    const inp = el("input", { type: "number", class: "num", min: "0", max: String(r.puntos), step: "0.5", value: String(previa[r.id] ?? ia?.puntos ?? 0), id: "n_" + r.id });
    inp.addEventListener("input", actualizar); inputs[r.id] = inp;
    caja.append(el("div", { class: "gradeo" }, el("label", { for: "n_" + r.id }, r.texto),
      el("span", {}, inp, el("span", { class: "max" }, "/ " + fmt(r.puntos))),
      ia ? el("span", { class: "ev" }, `IA: ${NIVEL[ia.nivel]}, ${fmt(ia.puntos)} p.`) : null));
  }
  const com = el("textarea", { id: "comentarioProfe" }); com.value = s.evaluacion_profe?.comentario || "";
  const estado = el("span", { role: "status" });
  const btn = el("button", { class: "btn primary", onclick: async () => {
    const puntos = {}; for (const r of s.rubrica) puntos[r.id] = Number(inputs[r.id].value) || 0;
    btn.disabled = true; estado.textContent = "Guardando…";
    try { S.detalle = await api("PUT", `/sesiones/${s.id}/nota`, { puntos, comentario: com.value }); render(); aviso("Nota guardada. El alumno ya puede verla."); }
    catch (e) { estado.textContent = e.message; btn.disabled = false; }
  } }, "Guardar nota");
  caja.append(totalEl, el("div", { class: "campo" }, el("label", { for: "comentarioProfe" }, "Comentario para el alumno"), com), el("div", { class: "fila-acciones" }, btn, estado));
  actualizar();
  return el("div", { class: "valoracion" }, caja);
}

/* ---------- primer arranque ---------- */
function vistaConfiguracion() {
  const f = el("section", { class: "login" });
  const campo = (id, label, attrs, ayuda) => el("div", { class: "campo" }, el("label", { for: id }, label, ayuda ? el("span", { class: "ayuda" }, ayuda) : null), el("input", { id, ...attrs }));
  const estado = el("p", { role: "status" });
  const btn = el("button", { class: "btn primary", onclick: async () => {
    if ($("#cPass").value !== $("#cPass2").value) { estado.textContent = "Las contraseñas no coinciden."; return; }
    btn.disabled = true; estado.textContent = "Guardando…";
    try {
      const r = await api("POST", "/configuracion-inicial", { codigo: $("#cCodigo").value.trim(), nombre: $("#cNombre").value.trim(), email: $("#cEmail").value.trim(), password: $("#cPass").value });
      S.configurar = false; S.token = r.token; S.rol = r.rol; S.nombre = r.nombre; guardar("mostrador-token", r.token);
      S.tab = "grupos"; pintarCabecera(); cargarTab(); aviso("Todo listo. Crea un grupo y comparte su código y la dirección de esta página con el alumnado.");
    } catch (e) { estado.textContent = e.message; btn.disabled = false; }
  } }, "Crear cuenta y empezar");
  f.append(el("div", { class: "caja" },
    el("h2", { class: "seccion", style: "margin:0" }, "Configura Mostrador"),
    el("p", {}, "Es la primera vez que se abre en este equipo. Crea la cuenta de la profesora o profesor que lo va a administrar."),
    campo("cCodigo", "Código de configuración", { type: "text", inputmode: "numeric", autocomplete: "off" }, "Aparece en la ventana negra donde se está ejecutando Mostrador y en el archivo CODIGO_CONFIGURACION.txt de su carpeta."),
    campo("cNombre", "Tu nombre", { type: "text", autocomplete: "name" }),
    campo("cEmail", "Correo (lo usarás para entrar)", { type: "email", autocomplete: "username" }),
    campo("cPass", "Contraseña", { type: "password", autocomplete: "new-password" }, "Mínimo 10 caracteres."),
    campo("cPass2", "Repite la contraseña", { type: "password", autocomplete: "new-password" }),
    btn, estado));
  return f;
}

/* ---------- profesorado: grupos ---------- */
function bloqueAcceso() {
  const e = S.estado; if (!e) return null;
  const caja = el("div", { class: "caja", style: "margin-bottom:1rem" }, el("h3", { style: "margin-top:0" }, "Cómo entra el alumnado"));
  if (e.direcciones.length) caja.append(el("p", {}, "Desde cualquier ordenador, tablet o móvil conectado a la misma red, abre el navegador y escribe:"),
    el("div", { class: "codigo", style: "letter-spacing:.02em;word-break:break-all" }, e.direcciones[0]),
    el("p", {}, "Después cada persona entra con el código de su grupo."));
  else caja.append(el("p", {}, "Este equipo no está conectado a ninguna red, así que solo se puede usar desde aquí. Conéctalo a la red del aula para que entre el alumnado."));
  if (!e.ia.ok) caja.append(el("div", { class: "aviso error" }, "La IA no está lista: " + e.ia.motivo + " Hasta que se arregle, el cliente virtual no podrá responder."));
  else if (e.ia.nombre) caja.append(el("p", { class: "nota-ia" }, `IA de Mostrador lista en este equipo (construida sobre el modelo abierto ${e.ia.base}). Las conversaciones no salen del centro.`));
  if (e.copias && e.copias.activas) {
    const st = el("span", { role: "status" });
    const txt = e.copias.ultima ? "Última copia de seguridad: " + fecha(e.copias.ultima) + "." : "Todavía no hay ninguna copia de seguridad.";
    const linea = el("span", { class: "nota-ia", style: "margin:0" }, txt + " Se hace una al día automáticamente.");
    caja.append(el("div", { class: "fila-acciones", style: "margin-top:.4rem" }, linea,
      el("button", { class: "btn small quiet", onclick: async ev => {
        ev.target.disabled = true; st.textContent = "Copiando…";
        try { const r = await api("POST", "/copias"); st.textContent = "Copia guardada: " + r.archivo; linea.textContent = "Última copia de seguridad: " + fecha(new Date()) + ". Se hace una al día automáticamente."; } catch (er) { st.textContent = er.message; }
        ev.target.disabled = false;
      } }, "Hacer copia ahora"), st));
  }
  return caja;
}
function bloqueProfesorado() {
  const lista = S.profesores || [];
  const caja = el("div", { class: "caja", style: "margin-top:1.5rem" }, el("h3", { style: "margin-top:0" }, "Profesorado con acceso"),
    el("ul", {}, lista.map(p => el("li", {}, `${p.nombre} (${p.email})`))));
  const n = el("input", { type: "text", id: "pNombre", autocomplete: "off" }), m = el("input", { type: "email", id: "pEmail", autocomplete: "off" }), w = el("input", { type: "password", id: "pPass", autocomplete: "new-password" });
  const st = el("span", { role: "status" });
  caja.append(el("details", {}, el("summary", { style: "cursor:pointer;font-weight:700" }, "Dar acceso a otra profesora o profesor"),
    el("div", { class: "form", style: "margin-top:.6rem" },
      el("div", { class: "campo" }, el("label", { for: "pNombre" }, "Nombre"), n),
      el("div", { class: "campo" }, el("label", { for: "pEmail" }, "Correo"), m),
      el("div", { class: "campo" }, el("label", { for: "pPass" }, "Contraseña inicial", el("span", { class: "ayuda" }, "Mínimo 10 caracteres. Comunícasela en persona.")), w),
      el("div", { class: "fila-acciones" }, el("button", { class: "btn primary", onclick: async () => {
        try { await api("POST", "/profesores", { nombre: n.value.trim(), email: m.value.trim(), password: w.value }); aviso("Cuenta creada."); cargarTab(); }
        catch (e) { st.textContent = e.message; }
      } }, "Crear cuenta"), st))));
  return caja;
}
function vistaGrupos() {
  const f = document.createDocumentFragment();
  const acceso = bloqueAcceso(); if (acceso) f.append(acceso);
  const nombre = el("input", { type: "text", id: "gNombre", placeholder: "Por ejemplo: 1º Farmacia A", maxlength: "120" });
  f.append(el("h2", { class: "seccion" }, "Grupos"),
    el("div", { class: "caja", style: "margin-bottom:1rem" },
      el("div", { class: "campo" }, el("label", { for: "gNombre" }, "Nuevo grupo", el("span", { class: "ayuda" }, "Se genera un código para que el alumnado entre.")), nombre),
      el("div", { class: "fila-acciones", style: "margin-top:.6rem" }, el("button", { class: "btn primary", onclick: async () => {
        if (!nombre.value.trim()) return;
        try { await api("POST", "/grupos", { nombre: nombre.value.trim() }); cargarTab(); } catch (e) { aviso(e.message, "error"); }
      } }, "Crear grupo"))));
  if (!S.grupos.length) { f.append(el("div", { class: "vacio" }, "Crea un grupo para empezar."), bloqueProfesorado()); return f; }
  const g = el("div", { class: "grupos" });
  for (const gr of S.grupos) {
    const lista = el("div");
    g.append(el("article", { class: "caso" },
      el("h3", {}, gr.nombre), el("div", { class: "codigo", "aria-label": "Código " + gr.codigo.split("").join(" ") }, gr.codigo),
      el("p", {}, `${gr.alumnos} alumno${gr.alumnos === 1 ? "" : "s"}${gr.activo ? "" : " (cerrado: no se puede entrar)"}`),
      el("div", { class: "fila-acciones" },
        el("button", { class: "btn small", onclick: () => verAlumnos(gr, lista) }, "Ver alumnado"),
        el("button", { class: "btn small quiet", onclick: async () => { try { await api("POST", `/grupos/${gr.id}/activo?activo=${!gr.activo}`); cargarTab(); } catch (e) { aviso(e.message, "error"); } } }, gr.activo ? "Cerrar grupo" : "Reabrir grupo"),
        gr.activo ? null : botonEliminarGrupo(gr)),
      lista));
  }
  f.append(g, bloqueProfesorado());
  return f;
}
function botonEliminarGrupo(gr) {
  let confirmar = false;
  const b = el("button", { class: "btn small quiet", onclick: async () => {
    if (!confirmar) { confirmar = true; b.textContent = "Pulsa otra vez: se borran el alumnado y todas sus prácticas"; return; }
    try { const r = await api("DELETE", "/grupos/" + gr.id); aviso(`Grupo eliminado con ${r.alumnos} alumnos y ${r.practicas} prácticas.`); cargarTab(); }
    catch (e) { aviso(e.message, "error"); }
  } }, "Eliminar grupo y sus datos");
  return b;
}
async function verAlumnos(gr, cont) {
  try {
    const al = await api("GET", `/grupos/${gr.id}/alumnos`);
    cont.innerHTML = "";
    if (!al.length) { cont.append(el("p", {}, "Todavía no ha entrado nadie.")); return; }
    for (const a of al) {
      const pin = el("input", { type: "text", inputmode: "numeric", class: "num", placeholder: "PIN", "aria-label": "Nuevo PIN para " + a.alias, maxlength: "8" });
      const st = el("span", { role: "status" });
      cont.append(el("div", { class: "rub-fila" }, el("span", {}, a.alias), pin,
        el("button", { class: "btn small quiet", onclick: async () => {
          try { await api("POST", `/alumnos/${a.id}/pin`, { pin: pin.value.trim() }); st.textContent = "PIN cambiado"; pin.value = ""; }
          catch (e) { st.textContent = "PIN de 4 a 8 números"; }
        } }, "Cambiar PIN")), st);
    }
  } catch (e) { aviso(e.message, "error"); }
}

/* ---------- profesorado: casos ---------- */
const nuevoId = () => "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
function vistaCasos() {
  const f = document.createDocumentFragment();
  f.append(el("div", { class: "fila-acciones", style: "justify-content:space-between;margin-bottom:.8rem" },
    el("h2", { class: "seccion", style: "margin:0" }, "Casos y rúbricas"),
    el("button", { class: "btn primary", onclick: () => { S.editando = { nuevo: true, titulo: "", modulo: "Dispensación de productos farmacéuticos", situacion: "", personaje: "", saludo: "", rubricaVisible: true, publicado: true, rubrica: [{ id: nuevoId(), texto: "Saluda y trata al cliente con amabilidad", puntos: 1 }] }; render(); } }, "Crear caso")));
  if (!S.casos.length) { f.append(el("div", { class: "vacio" }, "No hay casos. Crea uno para que el alumnado pueda practicar.")); return f; }
  const g = el("div", { class: "casos" });
  for (const c of S.casos) {
    const total = c.rubrica.reduce((a, r) => a + r.puntos, 0);
    g.append(el("article", { class: "caso" }, c.modulo ? el("span", { class: "modulo" }, c.modulo) : null, el("h3", {}, c.titulo),
      el("p", {}, `${c.rubrica.length} criterios, ${fmt(total)} puntos${c.publicado ? "" : ". Oculto para el alumnado"}`),
      el("div", {}, el("button", { class: "btn", onclick: () => { S.editando = JSON.parse(JSON.stringify(c)); render(); } }, "Editar"))));
  }
  f.append(g);
  return f;
}
function editorCaso(c) {
  const form = el("section", { class: "form caja" });
  const campo = (id, etiqueta, ayuda, area, prop) => {
    const inp = area ? el("textarea", { id }) : el("input", { type: "text", id });
    inp.value = c[prop] || ""; inp.addEventListener("input", () => c[prop] = inp.value);
    return el("div", { class: "campo" }, el("label", { for: id }, etiqueta, ayuda ? el("span", { class: "ayuda" }, ayuda) : null), inp);
  };
  form.append(el("h2", { class: "seccion", style: "margin:0" }, c.nuevo ? "Nuevo caso" : "Editar caso"),
    campo("fTitulo", "Título del caso", null, false, "titulo"),
    campo("fModulo", "Módulo", null, false, "modulo"),
    campo("fSituacion", "Situación que ve el alumno", "Lo que aparece al empezar.", true, "situacion"),
    campo("fPersonaje", "Cómo es el cliente (el alumnado no lo ve)", "Quién es, qué quiere, qué información tiene oculta y cuándo debe revelarla, cómo reacciona.", true, "personaje"),
    campo("fSaludo", "Primera frase del cliente", null, false, "saludo"));
  const rubBox = el("div", { class: "campo" });
  const pintarRub = () => {
    rubBox.innerHTML = "";
    rubBox.append(el("label", {}, "Rúbrica", el("span", { class: "ayuda" }, `Cada fila es algo que el alumno debería hacer. Total: ${fmt(c.rubrica.reduce((a, r) => a + (Number(r.puntos) || 0), 0))} puntos.`)));
    c.rubrica.forEach((r, i) => {
      const t = el("input", { type: "text", "aria-label": `Criterio ${i + 1}`, placeholder: "Qué debe hacer el alumno" }); t.value = r.texto; t.addEventListener("input", () => r.texto = t.value);
      const p = el("input", { type: "number", class: "num", min: "0", step: "0.5", "aria-label": `Puntos del criterio ${i + 1}` }); p.value = String(r.puntos);
      p.addEventListener("change", () => { r.puntos = Math.max(0, Number(p.value) || 0); pintarRub(); });
      rubBox.append(el("div", { class: "rub-fila" }, t, p, el("button", { class: "btn small quiet", "aria-label": `Quitar criterio ${i + 1}`, onclick: () => { c.rubrica.splice(i, 1); pintarRub(); } }, "Quitar")));
    });
    rubBox.append(el("button", { class: "btn small", onclick: () => { c.rubrica.push({ id: nuevoId(), texto: "", puntos: 1 }); pintarRub(); } }, "Añadir criterio"));
  };
  pintarRub(); form.append(rubBox);
  const check = (id, prop, txt) => { const i = el("input", { type: "checkbox", id }); i.checked = !!c[prop]; i.addEventListener("change", () => c[prop] = i.checked); return el("label", { class: "check", for: id }, i, txt); };
  form.append(check("fVis", "rubricaVisible", "Mostrar la rúbrica al alumno durante la práctica"), check("fPub", "publicado", "Visible para el alumnado"));
  const estado = el("span", { role: "status" });
  let confirmar = false;
  const btnBorrar = c.nuevo ? null : el("button", { class: "btn quiet", onclick: async () => {
    if (!confirmar) { confirmar = true; btnBorrar.textContent = "Pulsa otra vez para eliminar"; return; }
    try { const r = await api("DELETE", "/casos/" + c.id); aviso(r.archivado ? "El caso tiene prácticas hechas, así que se ha ocultado en lugar de borrarlo." : "Caso eliminado."); S.editando = null; cargarTab(); }
    catch (e) { estado.textContent = e.message; }
  } }, "Eliminar caso");
  form.append(el("div", { class: "fila-acciones" },
    el("button", { class: "btn primary", onclick: async () => {
      const datos = { titulo: c.titulo.trim(), modulo: c.modulo, situacion: c.situacion, personaje: c.personaje, saludo: c.saludo,
        rubricaVisible: c.rubricaVisible, publicado: c.publicado, rubrica: c.rubrica.filter(r => r.texto.trim()) };
      if (!datos.titulo) { estado.textContent = "Ponle un título al caso."; return; }
      if (!datos.rubrica.length) { estado.textContent = "Añade al menos un criterio a la rúbrica."; return; }
      estado.textContent = "Guardando…";
      try { await (c.nuevo ? api("POST", "/casos", datos) : api("PUT", "/casos/" + c.id, datos)); S.editando = null; aviso("Caso guardado."); cargarTab(); }
      catch (e) { estado.textContent = e.message; }
    } }, "Guardar caso"),
    el("button", { class: "btn quiet", onclick: () => { S.editando = null; render(); } }, "Cancelar"), btnBorrar, estado));
  return form;
}

/* ---------- profesorado: entregas ---------- */
function vistaEntregas() {
  const f = document.createDocumentFragment();
  const selEstado = el("select", { "aria-label": "Filtrar por estado", onchange: e => { S.filtro = e.target.value; cargarTab(); } },
    [["entregada", "Pendientes de revisar"], ["revisada", "Revisadas"], ["en_curso", "En curso"], ["todas", "Todas"]].map(([v, t]) => el("option", { value: v, selected: v === S.filtro }, t)));
  const selGrupo = el("select", { "aria-label": "Filtrar por grupo", onchange: e => { S.filtroGrupo = e.target.value; cargarTab(); } },
    el("option", { value: "" }, "Todos los grupos"), S.grupos.map(g => el("option", { value: String(g.id), selected: String(g.id) === S.filtroGrupo }, g.nombre)));
  f.append(el("div", { class: "fila-acciones", style: "justify-content:space-between;margin-bottom:.8rem" },
    el("h2", { class: "seccion", style: "margin:0" }, "Revisar entregas"),
    el("div", { class: "fila-filtros" }, selGrupo, selEstado, el("button", { class: "btn", onclick: cargarTab }, "Actualizar"))));
  if (!S.entregas) { f.append(el("p", { class: "pensando" }, "Cargando entregas…")); return f; }
  if (!S.entregas.length) { f.append(el("div", { class: "vacio" }, "No hay prácticas en este estado.")); return f; }
  f.append(tablaSesiones(S.entregas.map(e => el("tr", {},
    el("td", {}, e.alias), el("td", {}, e.grupo), el("td", {}, e.caso_titulo), el("td", {}, fecha(e.inicio)),
    el("td", {}, el("span", { class: "estado " + e.estado }, ESTADO[e.estado])),
    el("td", {}, e.puntos_ia != null ? `${fmt(e.puntos_ia)} / ${fmt(e.puntos_max)}` : "–"),
    el("td", {}, e.puntos_profe != null ? `${fmt(e.puntos_profe)} / ${fmt(e.puntos_max)}` : "–"),
    el("td", {}, el("button", { class: "btn small", onclick: () => abrirSesion(e.id, true) }, e.estado === "entregada" ? "Revisar" : "Ver")))),
    ["Alumno/a", "Grupo", "Caso", "Fecha", "Estado", "Propuesta IA", "Nota final", ""]));
  return f;
}

/* ---------- arranque ---------- */
(async () => {
  try { const e = await api("GET", "/estado"); if (e.necesita_configuracion) { S.token = null; guardar("mostrador-token", null); S.configurar = true; pintarCabecera(); render(); return; } } catch (_) {}
  if (S.token) {
    try { const yo = await api("GET", "/yo"); S.rol = yo.rol; S.nombre = yo.nombre; S.grupo = yo.grupo; }
    catch (_) { S.token = null; guardar("mostrador-token", null); }
  }
  pintarCabecera();
  if (S.rol) cargarTab(); else render();
})();
