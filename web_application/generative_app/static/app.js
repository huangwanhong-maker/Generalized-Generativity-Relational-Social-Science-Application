"use strict";

(() => {
  const app = document.getElementById("app");
  const dialog = document.getElementById("editor-dialog");
  const notifications = document.getElementById("notifications");
  const state = { user: null, csrf: "", projects: [], project: null, records: [], record: null, head: null, currentHead: null, legacy: false, history: [], revision: null, authMode: "register", routeSequence: 0 };
  let graphWorkspace = null;
  let editorSnapshot = "";
  let renderedHash = location.hash || "#/projects";
  let revisionSequence = 0;
  let toastTimer;
  const types = ["Entity", "State", "Event", "Process", "Relation", "Property"];
  const modes = ["observed", "reported", "inferred", "interpreted", "retrospective"];
  const modalities = ["realized", "intended", "possible", "unrealized", "unknown"];
  const statuses = ["unreviewed", "contested", "revised", "withdrawn"];
  const editable = ["title", "content", "record_type", "epistemic_mode", "modality", "status", "attributed_to", "method", "evidence", "uncertainty", "alternatives", "conditions", "consequences", "occurred_at"];
  const paths = {
    folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3Z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
    record: '<path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8m-8 4h6"/>',
    branch: '<circle cx="6" cy="4" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="6" cy="20" r="2"/><path d="M6 6v12M6 15c0-6 12-2 12-6"/>',
    leaf: '<path d="M20 3C9 2 3 7 5 15c8 4 15-2 15-12ZM4 21 16 9"/>',
    logout: '<path d="M9 4H4v16h5m5-12 4 4-4 4m-6-4h11"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    edit: '<path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14Z"/>',
    download: '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    evidence: '<path d="m4 13 5 5L20 6"/>',
    connection: '<circle cx="5" cy="12" r="3"/><circle cx="19" cy="5" r="3"/><circle cx="19" cy="19" r="3"/><path d="m8 11 8-5m-8 7 8 5"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
    state: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/>',
    event: '<path d="m13 2-9 12h7l-1 8L21 9h-8Z"/>',
    property: '<path d="M3 3h8l10 10-8 8L3 11Z"/><circle cx="7.5" cy="7.5" r="1"/>'
  };
  const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.record}</svg>`;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const cap = value => value ? String(value)[0].toUpperCase() + String(value).slice(1) : "Not specified";
  const routeProject = id => `#/projects/${encodeURIComponent(id)}`;
  const routeRecord = (pid, rid, revision = null) => `${routeProject(pid)}/records/${encodeURIComponent(rid)}${revision ? `?revision=${encodeURIComponent(revision)}` : ""}`;
  const apiProject = id => `/api/projects/${encodeURIComponent(id)}`;
  const apiRecord = (pid, rid) => `${apiProject(pid)}/records/${encodeURIComponent(rid)}`;
  const initials = name => String(name || "").trim().split(/\s+/).slice(0, 2).map(s => s[0]).join("").toUpperCase() || "G";
  const displayAuthor = value => typeof value === "object" && value !== null ? value.display_name || "Recorder not specified" : value || "Recorder not specified";
  const recordIcon = type => ({ Entity: "record", State: "state", Event: "event", Process: "branch", Relation: "connection", Property: "property" }[type] || "record");
  function date(value, full = false) {
    if (!value) return "Date not recorded";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return new Intl.DateTimeFormat(undefined, full ? { dateStyle: "medium", timeStyle: "short" } : { month: "short", day: "numeric", year: "numeric" }).format(d);
  }
  function toast(message) {
    clearTimeout(toastTimer);
    notifications.innerHTML = `<div class="toast">${esc(message)}</div>`;
    toastTimer = setTimeout(() => { notifications.innerHTML = ""; }, 5000);
  }
  function errorText(error) {
    let message = error.message || "Something went wrong. Please try again.";
    if (error.fields && typeof error.fields === "object") {
      const values = Object.entries(error.fields).map(([key, value]) => `${key.replaceAll("_", " ")}: ${Array.isArray(value) ? value.join(", ") : value}`);
      if (values.length) message += " " + values.join(". ");
    }
    return message;
  }
  async function api(path, { method = "GET", body } = {}) {
    let response;
    try {
      response = await fetch(path, {
        method,
        credentials: "same-origin",
        headers: { Accept: "application/json", ...(body !== undefined && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(method !== "GET" ? { "X-CSRF-Token": state.csrf } : {}) },
        ...(body !== undefined ? { body: body instanceof FormData ? body : JSON.stringify(body) } : {})
      });
    } catch (_) { throw new Error("The workspace is unavailable. Your unsaved text is still here; check the connection and try again."); }
    let data;
    try { data = await response.json(); } catch (_) { throw new Error("The server returned an unexpected response. Please try again."); }
    if (!response.ok) {
      const error = new Error(data.error?.message || `The request could not be completed (${response.status}).`);
      error.status = response.status;
      error.code = data.error?.code;
      error.fields = data.error?.fields;
      throw error;
    }
    return data;
  }
  function applySession(data) {
    state.user = data.user;
    state.csrf = data.csrf_token;
  }
  function brand() {
    return '<a class="brand" href="#/projects" aria-label="Generativity home"><span class="brand-mark" aria-hidden="true">g.</span><span><span class="brand-name">Generativity</span><span class="brand-subtitle">A living record of becoming</span></span></a>';
  }
  function auth() {
    const register = state.authMode === "register";
    app.innerHTML = `<div class="auth-page"><header class="auth-top">${brand()}<span class="small">A space for inquiry. A record for what comes next.</span></header>
      <main id="main" class="auth-body"><section class="auth-story"><span class="eyebrow">The context is part of the story</span><h1>Keep the story<br> behind what<br> <em>becomes.</em></h1><p class="intro">A thoughtful workspace for observations, evidence, and possibilities. Preserve how your understanding develops, one record at a time.</p><div class="auth-line"></div><div class="auth-principles"><div>${icon("connection")}<span><strong>Make the connections visible</strong>Keep the conditions and relationships behind an outcome.</span></div><div>${icon("branch")}<span><strong>Leave room for changing your mind</strong>Revisit a claim without erasing its earlier history.</span></div><div>${icon("lock")}<span><strong>Your projects, kept private</strong>Decide what to record in your own research space.</span></div></div></section>
      <section class="auth-card" aria-labelledby="auth-heading"><span class="eyebrow">Your personal workspace</span><h2 id="auth-heading">${register ? "Begin a new thread." : "Welcome back."}</h2><p class="muted">${register ? "A place to preserve more than the final result." : "Pick up where your inquiry left off."}</p><div class="auth-tabs" aria-label="Account access"><button class="auth-tab ${register ? "active" : ""}" data-action="register-tab" type="button" aria-pressed="${register}">Create account</button><button class="auth-tab ${!register ? "active" : ""}" data-action="login-tab" type="button" aria-pressed="${!register}">Sign in</button></div>
      <form id="auth-form">${register ? '<div class="field"><label class="label" for="display-name">Your name</label><input id="display-name" name="display_name" autocomplete="name" maxlength="80" required placeholder="How should we address you?"></div>' : ""}<div class="field"><label class="label" for="email">Email address</label><input id="email" name="email" type="email" autocomplete="email" maxlength="254" required placeholder="you@example.org"></div><div class="field"><label class="label" for="password">Password</label><input id="password" name="password" type="password" autocomplete="${register ? "new-password" : "current-password"}" ${register ? 'minlength="12"' : ""} maxlength="1024" required placeholder="${register ? "At least 12 characters" : "Your password"}">${register ? '<p class="field-help">Use a unique password with at least 12 characters.</p>' : ""}</div><div id="auth-error" role="alert"></div><button class="button full" type="submit">${register ? "Create your workspace" : "Sign in to your workspace"}${icon("arrow")}</button></form><p class="auth-caption">An experimental workspace informed by the<br>Generativity Standards Program.</p></section></main><footer class="auth-footer"><span>Preserve the trajectory. Keep possibilities open.</span><span>Private projects · Traceable revisions</span></footer></div>`;
    document.getElementById("auth-form").addEventListener("submit", submitAuth);
  }
  async function submitAuth(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('[type="submit"]');
    const errorNode = document.getElementById("auth-error");
    button.disabled = true;
    errorNode.innerHTML = "";
    try {
      const values = Object.fromEntries(new FormData(form));
      const result = await api(`/api/auth/${state.authMode}`, { method: "POST", body: values });
      applySession(result);
      form.reset();
      state.project = null;
      state.record = null;
      if (!location.hash || !location.hash.startsWith("#/projects")) location.hash = "#/projects";
      else await renderRoute();
      toast(state.authMode === "register" ? "Your workspace is ready. Start with your first project." : "Welcome back.");
    } catch (error) {
      errorNode.innerHTML = `<p class="error-box">${esc(errorText(error))}</p>`;
      button.disabled = false;
    }
  }
  function shell(body, crumbs = []) {
    const breadcrumb = crumbs.length ? `<a href="#/projects">Workspace</a>${crumbs.map((item, i) => `${icon("chevron")}${item.href ? `<a href="${esc(item.href)}">${esc(item.label)}</a>` : `<span class="crumb-current"${i === crumbs.length - 1 ? ' aria-current="page"' : ""}>${esc(item.label)}</span>`}`).join("")}` : '<span class="crumb-current" aria-current="page">Workspace</span>';
    app.innerHTML = `<div class="workspace"><aside class="sidebar">${brand()}<nav aria-label="Workspace navigation"><p class="nav-caption">Your workspace</p><a class="nav-link active" href="#/projects">${icon("folder")}Projects<span class="nav-count">${state.projects.length}</span></a></nav><div class="sidebar-note">${icon("leaf")}<strong>More than an outcome.</strong>Keep the observations, relations, and possibilities that made it possible.</div><div class="account"><span class="avatar" aria-hidden="true">${esc(initials(state.user.display_name))}</span><div class="account-details"><div class="account-name">${esc(state.user.display_name)}</div><div class="account-email">${esc(state.user.email)}</div></div><button class="button ghost icon-button" data-action="logout" title="Sign out" aria-label="Sign out">${icon("logout")}</button></div></aside><div class="main-area"><header class="topbar"><nav class="breadcrumb" aria-label="Breadcrumb">${breadcrumb}</nav><span class="topbar-note"><span class="status-dot" aria-hidden="true"></span>A space for thoughtful inquiry</span></header><main id="main" class="content" tabindex="-1">${body}</main></div></div>`;
  }
  const footnote = () => `<div class="workspace-footnote">${icon("branch")}<span>Every saved record becomes part of a project’s revision history. A preserved history shows what was recorded; the grounds of a claim remain open to inquiry.</span></div>`;
  function parseRoute() {
    const [pathname, query = ""] = location.hash.replace(/^#\/?/, "").split("?");
    const parts = pathname.split("/").filter(Boolean);
    const revision = new URLSearchParams(query).get("revision");
    if (!parts.length || (parts.length === 1 && parts[0] === "projects")) return { name: "projects" };
    if (parts[0] === "projects" && parts.length === 2) return { name: "project", project: parts[1], revision };
    if (parts[0] === "projects" && parts[2] === "records" && parts.length === 4) return { name: "record", project: parts[1], record: parts[3], revision };
    return { name: "missing" };
  }
  async function renderRoute({ keepRevision = false } = {}) {
    graphWorkspace?.destroy();
    graphWorkspace = null;
    if (!state.user) { auth(); return; }
    const sequence = ++state.routeSequence;
    const route = parseRoute();
    renderedHash = location.hash || "#/projects";
    if (!keepRevision) state.revision = null;
    shell('<div class="loading-area" role="status">Opening your records…</div>');
    try {
      const result = await api("/api/projects");
      if (sequence !== state.routeSequence) return;
      state.projects = result.projects;
      if (route.name === "projects") { state.project = null; state.record = null; projectsPage(); }
      else if (route.name === "project" || route.name === "record") {
        const data = await api(`${apiProject(route.project)}${route.revision ? `?revision=${encodeURIComponent(route.revision)}` : ""}`);
        if (sequence !== state.routeSequence) return;
        state.project = data.project;
        state.records = data.records;
        state.head = data.head ?? data.project.head;
        state.currentHead = data.current_head || state.head;
        state.legacy = Boolean(data.legacy);
        state.revision = route.revision ? state.head : null;
        if (route.name === "project") { state.record = null; projectPage(); }
        else {
          state.record = state.records.find(record => record.id === route.record);
          if (!state.record) { const error = new Error("This record is not present at the selected project revision."); error.status = 404; throw error; }
          state.history = [];
          recordPage(true);
          try {
            const history = await api(`${apiRecord(route.project, route.record)}/history?revision=${encodeURIComponent(state.head)}`);
            if (sequence !== state.routeSequence) return;
            state.history = history.history;
            renderHistory();
          } catch (error) {
            if (sequence === state.routeSequence) document.getElementById("history-content").innerHTML = `<p class="history-error">${esc(errorText(error))}</p><button class="button text" data-action="retry-route">Try again</button>`;
          }
        }
      } else missingPage();
      if (sequence === state.routeSequence) document.getElementById("main")?.focus({ preventScroll: true });
    } catch (error) {
      if (sequence !== state.routeSequence) return;
      if (error.status === 401) { await resetSession(); return; }
      shell(`<div class="page-error"><span class="eyebrow">Workspace unavailable</span><h1>We couldn’t open this page.</h1><p class="muted">${esc(errorText(error))}</p><div class="row"><button class="button" data-action="retry-route">Try again</button><a class="button secondary" href="#/projects">Your projects</a></div></div>`);
    }
  }
  async function resetSession() {
    applySession(await api("/api/session"));
    if (state.user) await renderRoute();
    else { state.authMode = "login"; auth(); toast("Please sign in to continue."); }
  }
  function missingPage() {
    shell('<div class="page-error"><span class="eyebrow">Page not found</span><h1>This path has no record.</h1><p class="muted">Return to your workspace to continue.</p><a class="button" href="#/projects">Your projects</a></div>');
  }
  function projectsPage() {
    const count = state.projects.reduce((total, p) => total + (p.record_count || 0), 0);
    shell(`<div class="page-heading"><div><span class="eyebrow">Your living archive</span><h1>Room for what becomes.</h1><p>Gather your observations, follow the connections, and preserve the story<br class="desktop-break"> behind your work. Every project begins with a possibility.</p></div><button class="button" data-action="new-project">${icon("plus")}New project</button></div><section class="stats" aria-label="Workspace summary"><div class="stat"><span class="stat-icon">${icon("folder")}</span><div><span class="stat-number">${state.projects.length}</span><span class="stat-label">${state.projects.length === 1 ? "Project in your workspace" : "Projects in your workspace"}</span></div></div><div class="stat"><span class="stat-icon">${icon("record")}</span><div><span class="stat-number">${count}</span><span class="stat-label">${count === 1 ? "Record preserved" : "Records preserved"}</span></div></div><div class="stat"><span class="stat-icon">${icon("lock")}</span><div><span class="stat-number">Private</span><span class="stat-label">Your space to explore</span></div></div></section><div class="section-toolbar"><div class="section-label">Your projects<span class="count">${state.projects.length}</span></div><div class="toolbar-controls"><label class="search-input">${icon("search")}<span class="sr-only">Search projects</span><input type="search" id="project-search" placeholder="Find a project…" autocomplete="off"></label></div></div><div class="project-grid" id="project-grid"></div>${footnote()}`, [{ label: "Projects" }]);
    renderProjects();
    document.getElementById("project-search").addEventListener("input", event => renderProjects(event.target.value));
  }
  function renderProjects(query = "") {
    const target = document.getElementById("project-grid");
    if (!state.projects.length) {
      target.innerHTML = `<section class="empty-state"><span class="empty-symbol">${icon("leaf")}</span><span class="eyebrow">Every inquiry starts somewhere</span><h2>What would you like to explore?</h2><p>Create a project for a question, a collaboration, or a changing situation. Then begin with one observation and the context around it.</p><button class="button" data-action="new-project">${icon("plus")}Create your first project</button></section>`;
      return;
    }
    const normalized = query.toLowerCase().trim();
    const filtered = state.projects.filter(p => `${p.name} ${p.description || ""}`.toLowerCase().includes(normalized));
    target.innerHTML = filtered.map(project => `<a class="project-card" href="${esc(routeProject(project.id))}"><div class="project-card-top"><span class="project-symbol">${icon("folder")}</span><span class="chip privacy">${icon("lock")}Private</span></div><h2>${esc(project.name)}</h2><p class="project-description">${esc(project.description || "An open space for observations, connections, and possibilities.")}</p><div class="project-meta"><span>${icon("record")}${project.record_count || 0} ${project.record_count === 1 ? "record" : "records"}</span><span>${icon("branch")}Revision history</span></div><div class="project-footer"><span>Created ${esc(date(project.created_at))}</span>${icon("arrow")}</div></a>`).join("") + (!normalized ? `<button class="new-project-card" data-action="new-project"><span class="plus-circle">${icon("plus")}</span><strong>Start something new</strong><span>Give a new inquiry<br>a place to grow.</span></button>` : "");
    if (!filtered.length) target.innerHTML = '<p class="no-results">No projects match your search. Try another name or phrase.</p>';
  }
  function projectPage() {
    const p = state.project;
    shell(`<div class="page-heading graph-heading"><div><span class="eyebrow">Project workspace</span><h1 class="break-text">${esc(p.name)}</h1><p class="break-text">${esc(p.description || "Follow the relationships, and keep the grounds of each account in view.")}</p></div><button class="button" data-action="new-record">${icon("plus")}New record</button></div><div id="graph-workspace"></div>`, [{ label: p.name }]);
    graphWorkspace = window.GSPGraph.mount(document.getElementById("graph-workspace"), { state, api, esc, icon, date, displayAuthor, chips, types, modes, apiProject, apiRecord, routeRecord, toast, errorText, dialog, openDialog, dialogHeader, editRecord, inputField, selectField, openFullRecord: (id, revision) => { location.hash = routeRecord(state.project.id, id, revision); } });
  }
  function chips(record) {
    return `${(record.record_roles || [record.record_type]).map(role => `<span class="chip">${esc(role)}</span>`).join("")}<span class="chip">${esc(cap(record.epistemic_mode))}</span><span class="chip modality">${record.modality === "unknown" ? "Occurrence unknown" : esc(cap(record.modality))}</span><span class="chip ${record.status === "contested" ? "contested" : record.status === "withdrawn" ? "withdrawn" : ""}">${esc(cap(record.status))}</span>`;
  }
  function renderRecords(query = "", type = "") {
    const target = document.getElementById("record-list");
    if (!state.records.length) {
      target.innerHTML = `<section class="empty-state"><span class="empty-symbol">${icon("record")}</span><span class="eyebrow">Begin with what you know</span><h2>A first record opens the thread.</h2><p>Describe something that happened, a relationship that matters, or a possibility you want to preserve. Uncertainty has a place here, too.</p><button class="button" data-action="new-record">${icon("plus")}Create your first record</button></section>`;
      return;
    }
    const term = query.trim().toLowerCase();
    const filtered = state.records.filter(r => (!type || r.record_type === type) && [r.title, r.content, r.attributed_to, r.evidence, r.uncertainty, r.conditions, r.alternatives].some(v => String(v || "").toLowerCase().includes(term)));
    target.innerHTML = filtered.map(record => `<a class="record-card" href="${esc(routeRecord(state.project.id, record.id))}"><span class="project-symbol">${icon(recordIcon(record.record_type))}</span><div><h2>${esc(record.title)}</h2><p class="excerpt">${esc(record.content)}</p><div class="record-chips">${chips(record)}</div></div><div class="record-card-side"><span>${esc(date(record.updated_at))}</span><span>${esc(displayAuthor(record.recorded_by))}</span>${icon("arrow")}</div></a>`).join("") || '<p class="no-results">No records match these filters. Try another phrase or record type.</p>';
  }
  function detail(label, value, wide = false) {
    return `<div class="detail-item${wide ? " wide" : ""}"><span class="detail-label">${esc(label)}</span>${value ? `<p>${esc(value)}</p>` : '<span class="missing">Not recorded</span>'}</div>`;
  }
  function recordPage(loadingHistory = false) {
    const r = state.record;
    const p = state.project;
    const related = (r.related_records || []).map(id => ({ id, record: state.records.find(item => item.id === id) }));
    shell(`${state.revision ? `<div class="old-revision"><span>Viewing a preserved revision <span class="mono">${esc(state.revision.slice(0, 10))}</span>. This is a historical view.</span><button class="button secondary small-button" data-action="current-revision">Return to current record</button></div>` : ""}<div class="page-heading record-reading-heading"><div><span class="eyebrow">${state.revision ? "Preserved record" : "Living record"}</span><h1>${esc(r.title)}</h1><div class="record-chips">${chips(r)}</div></div>${state.revision ? "" : `<button class="button" data-action="edit-record">${icon("edit")}Revise record</button>`}</div><div class="record-layout"><article class="record-article"><section class="record-section"><span class="eyebrow">What is recorded</span><p class="record-content">${esc(r.content)}</p></section><section class="record-section"><span class="eyebrow">Perspective &amp; evidence</span><div class="detail-grid">${detail("Observer or attributed source", r.attributed_to)}${detail("When the described situation occurred", r.occurred_at)}${detail("Method and basis", r.method, true)}${detail("Evidence and source references", r.evidence, true)}${detail("Uncertainty and limits", r.uncertainty, true)}</div></section><section class="record-section"><span class="eyebrow">Conditions &amp; possibilities</span><div class="detail-grid">${detail("Enabling or constraining conditions", r.conditions, true)}${detail("Alternatives and competing interpretations", r.alternatives, true)}${detail("Consequences and future possibilities", r.consequences, true)}</div></section><section class="record-section"><span class="eyebrow">Connected records</span>${related.length ? `<div class="related-links">${related.map(item => `<a href="${esc(routeRecord(p.id, item.id, state.head))}">${icon("connection")} ${esc(item.record?.title || item.id)}</a>`).join("")}</div><p class="field-help">Links open the related account at this same preserved project revision.</p>` : '<p class="missing">No connections have been recorded.</p>'}</section></article><aside class="record-sidebar"><section class="record-side-card"><h2>Record provenance</h2><div class="provenance-row"><span class="provenance-label">Recorded by</span><span class="provenance-value">${esc(displayAuthor(r.recorded_by))}</span></div><div class="provenance-row"><span class="provenance-label">First recorded</span><span class="provenance-value">${esc(date(r.created_at, true))}</span></div><div class="provenance-row"><span class="provenance-label">${state.revision ? "Updated in this revision" : "Last revised"}</span><span class="provenance-value">${esc(date(r.updated_at, true))}<br>${esc(displayAuthor(r.updated_by))}</span></div><div class="provenance-row"><span class="provenance-label">Record identifier</span><span class="provenance-value mono">${esc(r.id)}</span></div><p class="history-help">The recorder is the account that saved this text. The observer or attributed source may be someone else.</p></section><section class="record-side-card"><h2>Revision history</h2><div id="history-content">${loadingHistory ? '<p class="small muted" role="status">Loading preserved revisions…</p>' : ""}</div><p class="history-help">Earlier versions remain available. Revision dates describe changes to the record, not when the situation occurred. Up to 100 recent revisions are shown.</p></section></aside></div>${footnote()}`, [{ label: p.name, href: routeProject(p.id) }, { label: r.title }]);
    document.querySelector('.record-reading-heading').insertAdjacentHTML('afterend', `<div class="record-graph-return"><a class="button secondary small-button" href="${esc(routeProject(p.id))}${state.revision ? `?revision=${encodeURIComponent(state.head)}` : ""}">${icon("connection")}Open project graph</a></div>`);
    if (!loadingHistory) renderHistory();
  }
  function renderHistory() {
    const target = document.getElementById("history-content");
    if (!target) return;
    target.innerHTML = state.history.length ? `<ol class="history-list">${state.history.map((entry, index) => `<li class="history-entry${state.revision === entry.commit || (!state.revision && index === 0) ? " selected" : ""}"><button class="history-reason" data-action="view-revision" data-commit="${esc(entry.commit)}">${esc(entry.reason || "Record saved")}</button><span class="history-meta">${esc(displayAuthor(entry.author))}<br>${esc(date(entry.created_at, true))}<br><span class="mono">${esc(entry.commit.slice(0, 10))}</span></span>${state.revision === entry.commit ? '<span class="history-selected">Viewing this revision</span>' : !state.revision && index === 0 ? '<span class="history-selected">Current record</span>' : ""}</li>`).join("")}</ol>` : '<p class="small muted">No revision entries are available.</p>';
  }
  async function viewRevision(commit) {
    const sequence = state.routeSequence;
    const revisionRequest = ++revisionSequence;
    const pid = state.project.id;
    const rid = state.record.id;
    try {
      const result = await api(`${apiProject(pid)}${commit ? `?revision=${encodeURIComponent(commit)}` : ""}`);
      if (sequence !== state.routeSequence || revisionRequest !== revisionSequence || state.record?.id !== rid) return;
      state.records = result.records;
      state.record = state.records.find(record => record.id === rid);
      state.head = result.head;
      state.currentHead = result.current_head || result.head;
      if (!state.record) throw new Error("This record is absent from that project revision.");
      state.revision = commit;
      history.replaceState(null, "", routeRecord(pid, rid, commit));
      renderedHash = location.hash;
      const entries = await api(`${apiRecord(pid, rid)}/history?revision=${encodeURIComponent(state.head)}`);
      if (sequence !== state.routeSequence || revisionRequest !== revisionSequence) return;
      state.history = entries.history;
      recordPage();
      document.getElementById("main").focus({ preventScroll: true });
    } catch (error) { toast(errorText(error)); }
  }
  function formSnapshot() {
    const form = dialog.querySelector("form");
    return form ? JSON.stringify(Array.from(new FormData(form), ([name, value]) => [name, value instanceof File ? (value.name ? { name: value.name, size: value.size, type: value.type, lastModified: value.lastModified } : null) : value])) : "";
  }
  function canCloseEditor() {
    return !dialog.open || formSnapshot() === editorSnapshot || window.confirm("Discard the unsaved changes in this form?");
  }
  function openDialog(content, className = "") {
    dialog.className = className;
    dialog.innerHTML = content;
    dialog.showModal();
    editorSnapshot = formSnapshot();
    dialog.querySelector("input, textarea")?.focus();
  }
  function dialogHeader(title, description, eyebrow) {
    return `<header class="dialog-header"><div><span class="eyebrow">${esc(eyebrow)}</span><h2 id="dialog-title">${esc(title)}</h2><p>${esc(description)}</p></div><button class="button ghost icon-button" data-action="close-dialog" type="button" aria-label="Close dialog">${icon("close")}</button></header>`;
  }
  function newProject() {
    openDialog(`${dialogHeader("Make room for an inquiry.", "Give your project a name and a little context.", "New private project")}<form id="project-form"><div class="dialog-body"><div class="field"><label class="label" for="project-name">Project name</label><input id="project-name" name="name" maxlength="120" required placeholder="A question, a study, a possibility…"></div><div class="field"><label class="label optional-label" for="project-description">Description</label><textarea id="project-description" name="description" maxlength="2000" rows="4" placeholder="What are you exploring, and why does it matter?"></textarea></div><p class="notice">${icon("lock")} Only your account can access this project through this application. You can export its current records at any time.</p><div class="form-error" role="alert"></div></div><footer class="dialog-footer"><span class="small">A new home for your records.</span><div class="row"><button class="button secondary" data-action="close-dialog" type="button">Cancel</button><button class="button" type="submit">Create project${icon("arrow")}</button></div></footer></form>`, "project-dialog");
    document.getElementById("project-form").addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const button = form.querySelector('[type="submit"]');
      button.disabled = true;
      form.querySelector(".form-error").innerHTML = "";
      try {
        const result = await api("/api/projects", { method: "POST", body: Object.fromEntries(new FormData(form)) });
        dialog.close();
        location.hash = routeProject(result.project.id);
        toast("Project created. Your first record can begin here.");
      } catch (error) {
        form.querySelector(".form-error").innerHTML = `<p class="error-box">${esc(errorText(error))}</p>`;
        button.disabled = false;
      }
    });
  }
  function inputField(name, label, value, limit, { help = "", placeholder = "", required = false, multiline = false, wide = false, rows = 3 } = {}) {
    return `<div class="field${wide ? " wide" : ""}"><label class="label${required ? "" : " optional-label"}" for="field-${name}">${esc(label)}</label>${multiline ? `<textarea id="field-${name}" name="${name}" rows="${rows}" maxlength="${limit}" ${required ? "required" : ""} placeholder="${esc(placeholder)}"${help ? ` aria-describedby="help-${name}"` : ""}>${esc(value)}</textarea>` : `<input id="field-${name}" name="${name}" maxlength="${limit}" value="${esc(value)}" ${required ? "required" : ""} placeholder="${esc(placeholder)}"${help ? ` aria-describedby="help-${name}"` : ""}>`}${help ? `<p class="field-help" id="help-${name}">${esc(help)}</p>` : ""}</div>`;
  }
  function selectField(name, label, values, current, help, placeholder = "") {
    return `<div class="field"><label class="label" for="field-${name}">${esc(label)}</label><select id="field-${name}" name="${name}" required aria-describedby="help-${name}">${placeholder ? `<option value="" ${!current ? "selected" : ""}>${esc(placeholder)}</option>` : ""}${values.map(value => `<option value="${esc(value)}"${value === current ? " selected" : ""}>${esc(cap(value.replaceAll("_", " ")))}</option>`).join("")}</select><p class="field-help" id="help-${name}">${esc(help)}</p></div>`;
  }
  function editRecord(record = null, options = {}) {
    if (state.revision || state.legacy || graphWorkspace?.isReadOnly()) { toast("This snapshot cannot be edited here. Review its read-only notice in the project graph."); return; }
    const r = record || { modality: "unknown", status: "unreviewed" };
    const projectId = state.project.id;
    let expectedHead = state.head;
    let pendingTransaction = null;
    const recordId = record?.id || crypto.randomUUID();
    const relationId = crypto.randomUUID();
    const incidenceIds = [crypto.randomUUID(), crypto.randomUUID()];
    const relatedOptions = state.records.filter(item => item.id !== record?.id);
    openDialog(`${dialogHeader(record ? "Let the record develop." : "Begin with a record.", record ? "Preserve a new revision and explain what changed." : "Record what you know, and leave space for what you don’t.", record ? "Revise record" : "New project record")}<form id="record-form"><div class="dialog-body"><p class="form-intro">Describe the situation in your own words. The record type organizes this account; it does not settle what is real or true.</p>${inputField("title", "Record title", r.title, 160, { required: true, placeholder: "What does this record describe?" })}<div class="record-main-field">${inputField("content", "What would you like to record?", r.content, 20000, { required: true, multiline: true, rows: 5, placeholder: "Describe an observation, a relationship, a change, or a possibility…" })}</div><div class="field-grid">${selectField("record_type", "Primary recording role", types, r.record_type, "Choose the primary role for this account. Other roles and distinctions can be described in the text.", "Choose a record type")}${selectField("epistemic_mode", "Primary knowledge basis", modes, r.epistemic_mode, "Choose the primary basis. Describe mixed sources or additional methods under Perspective & evidence.", "How is this known?")}${selectField("modality", "Occurrence or possibility", modalities, r.modality, "Did this occur, was it intended, or is its occurrence unknown?")}${selectField("status", "Assessment status", statuses, r.status, "Assigned by you, without independent review. A contested account can describe a realized occurrence; dispute and occurrence are separate.")}</div><details class="form-section"><summary>Perspective &amp; evidence<span class="summary-meta">Who, when, and on what grounds</span></summary><div class="form-section-content">${inputField("attributed_to", "Observer or attributed source", r.attributed_to, 300, { help: "The observer or source may differ from you, the account recording this text.", placeholder: "A person, an instrument, a publication…" })}${inputField("occurred_at", "When the described situation occurred", r.occurred_at, 100, { help: "Approximate dates, intervals, and unknown times are welcome. This differs from the automatic recording time.", placeholder: "For example: early September, date uncertain" })}${inputField("method", "Method and basis", r.method, 2000, { multiline: true, placeholder: "How was this observed, reported, or inferred?" })}${inputField("evidence", "Evidence and source references", r.evidence, 5000, { multiline: true, help: "Plain text references or links. Source files are not uploaded or independently verified.", placeholder: "Identify supporting material and where it can be found." })}${inputField("uncertainty", "Uncertainty and limits", r.uncertainty, 3000, { multiline: true, placeholder: "What remains unknown, incomplete, or open to challenge?" })}</div></details><details class="form-section"><summary>Conditions &amp; possibilities<span class="summary-meta">The context around an outcome</span></summary><div class="form-section-content">${inputField("conditions", "Enabling or constraining conditions", r.conditions, 3000, { multiline: true, placeholder: "Which encounters, relations, resources, or constraints mattered?" })}${inputField("alternatives", "Alternatives and competing interpretations", r.alternatives, 3000, { multiline: true, placeholder: "What other interpretations or paths remain visible?" })}${inputField("consequences", "Consequences and future possibilities", r.consequences, 3000, { multiline: true, placeholder: "What changed, and what might now become possible?" })}</div></details><details class="form-section"><summary>Connected records<span class="summary-meta">${relatedOptions.length} available in this project</span></summary><div class="form-section-content">${relatedOptions.length ? `<p class="field-help">Connect this account to up to 50 other records. Describe the relationship in your text; a link alone does not establish causation.</p><div class="related-options">${relatedOptions.map(item => `<label class="related-option"><input type="checkbox" name="related_records" value="${esc(item.id)}"${(r.related_records || []).includes(item.id) ? " checked" : ""}><span>${esc(item.title)} <span class="muted small">· ${esc(item.record_type)}</span></span></label>`).join("")}</div>` : '<p class="field-help">Add another record to this project to make a connection.</p><br>'}</div></details>${record ? inputField("revision_reason", "Why are you revising this record?", "", 2000, { required: true, multiline: true, rows: 2, placeholder: "What changed in the evidence, description, or your understanding?", help: "This reason accompanies the preserved revision." }) : ""}<div class="form-error" role="alert"></div><div id="conflict-container"></div><p class="form-intro">Saving preserves this text in the project’s history. Avoid including sensitive information you do not intend to retain.</p></div><footer class="dialog-footer"><span class="small">${icon("branch")} Earlier revisions stay available.</span><div class="row"><button class="button secondary" data-action="close-dialog" type="button">Cancel</button><button class="button" type="submit">${record ? "Save revision" : "Save record"}${icon("arrow")}</button></div></footer></form>`);
    const form = document.getElementById("record-form");
    const roleSection = document.createElement("fieldset");
    roleSection.className = "record-roles-field";
    roleSection.innerHTML = `<legend>Additional recording roles</legend><p class="field-help">An account can have several roles. Its primary role is always included.</p><div class="role-checkboxes">${types.map(role => `<label class="related-option"><input type="checkbox" name="record_roles" value="${role}" ${(r.record_roles || [r.record_type]).includes(role) ? "checked" : ""}><span>${role}</span></label>`).join("")}</div>`;
    form.querySelector(".field-grid").insertAdjacentElement("afterend", roleSection);
    form.elements.record_type.addEventListener("change", event => { const box = roleSection.querySelector(`input[value="${event.target.value}"]`); if (box) box.checked = true; });
    document.getElementById("help-record_type").textContent = "Choose the primary presentation role. Additional roles can overlap without creating another record.";
    document.getElementById("help-evidence").textContent = "Describe sources here. Use the record's Files module to retain material; preservation does not independently verify its content.";
    const connectTo = options.connectTo || (!record ? graphWorkspace?.selectedRecord()?.id : null);
    if (!record && connectTo) {
      const target = state.records.find(item => item.id === connectTo);
      const section = document.createElement("details"); section.className = "form-section"; section.open = Boolean(options.connectTo);
      section.innerHTML = `<summary>Connect this new record<span class="summary-meta">One shared revision</span></summary><div class="form-section-content"><label class="related-option"><input type="checkbox" name="create_connection" ${options.connectTo ? "checked" : ""}><span>Create a relation with ${esc(target?.title || connectTo)}</span></label><p class="field-help">Both the new account and its relation are drafts until saved together.</p>${inputField("connection_predicate", "Relationship predicate", "", 160, { placeholder: "How are they related?" })}${inputField("connection_content", "Describe this connection and its grounds", "", 3000, { multiline: true, rows: 2 })}<div class="field-grid">${inputField("connection_new_role", "Role of the new record", "", 120)}${inputField("connection_existing_role", "Role of the existing record", "", 120)}</div><div class="field"><label class="label" for="connection-scope">What is related?</label><select id="connection-scope" name="connection_scope"><option value="represented_target">The represented targets</option><option value="record">The records themselves</option></select></div><p class="field-help">This initial connection is undirected. Its participant details can be revised in the Relation panel.</p><div class="field"><label class="label" for="connection-completeness">Does this pair cover the declared participant scope?</label><select id="connection-completeness" name="connection_completeness"><option value="">Choose the scope of this account?</option><option value="complete">Yes, complete within the stated scope</option><option value="incomplete">No, the participant account is incomplete</option></select></div>${inputField("connection_limitations", "Participant limitations", "", 3000, { multiline: true, rows: 2, help: "Required for an incomplete account. Do not invent missing participants." })}</div>`;
      form.querySelector(".form-error").insertAdjacentElement("beforebegin", section);
      const update = () => { for (const name of ["connection_predicate", "connection_content", "connection_new_role", "connection_existing_role", "connection_completeness"]) form.elements[name].required = form.elements.create_connection.checked; form.elements.connection_limitations.required = form.elements.create_connection.checked && form.elements.connection_completeness.value === "incomplete"; };
      form.elements.create_connection.addEventListener("change", update); form.elements.connection_completeness.addEventListener("change", update); update();
    }
    form.querySelector(".form-error").insertAdjacentHTML("beforebegin", selectField("change_category", "What kind of change is this?", ["description", "represented_change", "evidence_or_interpretation", "classification", "maintenance"], "description", "Describe the kind of revision, separately from when a represented situation occurred."));
    editorSnapshot = formSnapshot();
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const button = form.querySelector('[type="submit"]');
      const errors = form.querySelector(".form-error");
      button.disabled = true;
      errors.innerHTML = "";
      const values = new FormData(form);
      const body = Object.fromEntries(editable.map(key => [key, String(values.get(key) || "")]));
      body.related_records = values.getAll("related_records");
      body.record_roles = [...new Set([body.record_type, ...values.getAll("record_roles")])];
      body.expected_head = expectedHead;
      if (record) body.revision_reason = String(values.get("revision_reason") || "");
      try {
        let result;
        if (!state.legacy) {
          const changes = { ...body }; delete changes.expected_head; delete changes.revision_reason;
          const operations = [record ? { op: "record.update", record_id: recordId, changes } : { op: "record.create", record: { id: recordId, ...changes, modules: {} } }];
          if (!record && connectTo && values.has("create_connection")) {
            const predicate = String(values.get("connection_predicate")).trim();
            operations.push({ op: "record.create", record: { id: relationId, title: `${body.title} · ${predicate}`.slice(0, 160), content: String(values.get("connection_content")), record_type: "Relation", record_roles: ["Relation"], epistemic_mode: body.epistemic_mode, modality: body.modality, status: "unreviewed", related_records: [], modules: { "gsp.relation": { version: "1", required: false, data: { predicate, predicate_definition: "", participants: [{ id: incidenceIds[0], record_id: recordId, role: String(values.get("connection_new_role")), reference_scope: String(values.get("connection_scope")), orientation: "undirected" }, { id: incidenceIds[1], record_id: connectTo, role: String(values.get("connection_existing_role")), reference_scope: String(values.get("connection_scope")), orientation: "undirected" }], participants_complete: values.get("connection_completeness") === "complete", participant_limitations: String(values.get("connection_limitations") || ""), context: "", identity_criterion: "", temporal_scope: "" } } } } });
          }
          const logical = { protocol_version: window.GSPGraph.PROTOCOL, expected_head: expectedHead, reason: record ? body.revision_reason : `Create record: ${body.title}`, change_categories: [String(values.get("change_category") || "description")], operations };
          const signature = JSON.stringify(logical);
          if (!pendingTransaction || pendingTransaction.signature !== signature) pendingTransaction = { signature, body: { ...logical, transaction_id: crypto.randomUUID() } };
          const saved = await api(`${apiProject(projectId)}/transactions`, { method: "POST", body: pendingTransaction.body });
          result = { ...saved, record: { id: recordId } };
        } else {
          delete body.record_roles;
          result = await api(record ? apiRecord(projectId, record.id) : `${apiProject(projectId)}/records`, { method: record ? "PUT" : "POST", body });
        }
        dialog.close();
        if (graphWorkspace) { if (options.position) graphWorkspace.placeRecord(result.record.id, options.position); await graphWorkspace.refresh(result.head, result.record.id); }
        else { const next = routeRecord(projectId, result.record.id); if (location.hash === next) await renderRoute(); else location.hash = next; }
        toast(record ? "Revision preserved. The earlier account remains in history." : "Record saved. A new part of your project’s story.");
      } catch (error) {
        if (error.status === 409) {
          const container = document.getElementById("conflict-container");
          container.innerHTML = `<div class="conflict-panel"><strong>This project changed while you were writing.</strong><p>Your unsaved draft is still in the form. Review the latest project state before choosing how to continue.</p><button class="button secondary small-button" type="button" id="compare-latest">Review latest saved state</button><div id="conflict-preview"></div></div>`;
          document.getElementById("compare-latest").addEventListener("click", async event => {
            const compare = event.currentTarget;
            compare.disabled = true;
            try {
              const latest = await api(apiProject(projectId));
              const latestRecord = record ? latest.records.find(item => item.id === record.id) : null;
              const preview = document.getElementById("conflict-preview");
              preview.innerHTML = `<div class="conflict-preview"><p>Current project version: <span class="mono">${esc((latest.head || latest.project.head || "").slice(0, 12))}</span>. ${latest.records.length} records.</p>${latestRecord ? `<strong>Latest saved record</strong><pre>${esc(editable.map(key => `${key.replaceAll("_", " ")}: ${Array.isArray(latestRecord[key]) ? latestRecord[key].join(", ") : latestRecord[key] || "[not recorded]"}`).join("\n\n"))}\n\nConnected records: ${esc((latestRecord.related_records || []).join(", ") || "[none]")}</pre>` : '<p>Your draft is a new record. Existing project records have not been replaced.</p>'}<p>Keeping your draft uses all the form’s values for the next revision. You can still edit them before saving.</p><div class="row"><button type="button" class="button secondary small-button" id="keep-draft">Use current version and keep my draft</button>${latestRecord ? '<button type="button" class="button secondary small-button" id="reload-draft">Replace draft with latest</button>' : ""}</div></div>`;
              document.getElementById("keep-draft").addEventListener("click", () => {
                expectedHead = latest.head || latest.project.head;
                container.innerHTML = '<p class="notice">Your draft is preserved and now based on the project version you reviewed. Review your text, then save when ready.</p>';
              });
              document.getElementById("reload-draft")?.addEventListener("click", () => {
                if (!window.confirm("Replace your unsaved draft with the latest saved record? Your unsaved text will be discarded.")) return;
                state.head = latest.head || latest.project.head;
                state.records = latest.records;
                dialog.close();
                editRecord(latestRecord);
              });
            } catch (failure) {
              document.getElementById("conflict-preview").innerHTML = `<p class="error-box">${esc(errorText(failure))}</p>`;
              compare.disabled = false;
            }
          });
          container.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else {
          errors.innerHTML = `<p class="error-box">${esc(errorText(error))}</p>`;
          errors.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
        button.disabled = false;
      }
    });
  }
  document.addEventListener("click", async event => {
    if (event.target instanceof Element && event.target.closest(".skip-link")) {
      event.preventDefault();
      const main = document.getElementById("main");
      main?.setAttribute("tabindex", "-1");
      main?.focus();
      return;
    }
    const button = event.target instanceof Element ? event.target.closest("[data-action]") : null;
    if (!button || button.disabled) return;
    const action = button.dataset.action;
    if (action === "register-tab" || action === "login-tab") { state.authMode = action === "register-tab" ? "register" : "login"; auth(); }
    else if (action === "close-dialog") { if (canCloseEditor()) dialog.close(); }
    else if (action === "new-project") newProject();
    else if (action === "new-record") editRecord();
    else if (action === "edit-record") editRecord(state.record);
    else if (action === "view-revision") await viewRevision(button.dataset.commit);
    else if (action === "current-revision") await viewRevision(null);
    else if (action === "retry-route") await renderRoute();
    else if (action === "logout") {
      button.disabled = true;
      try { applySession(await api("/api/auth/logout", { method: "POST", body: {} })); state.projects = []; state.records = []; state.record = null; state.project = null; state.authMode = "login"; ++state.routeSequence; auth(); toast("You are signed out."); }
      catch (error) { toast(errorText(error)); button.disabled = false; }
    }
  });
  dialog.addEventListener("cancel", event => { if (!canCloseEditor()) event.preventDefault(); });
  window.addEventListener("beforeunload", event => { if (dialog.open && formSnapshot() !== editorSnapshot) { event.preventDefault(); event.returnValue = ""; } });
  window.addEventListener("hashchange", () => {
    if (dialog.open) {
      if (!canCloseEditor()) {
        history.replaceState(null, "", renderedHash);
        return;
      }
      dialog.close();
    }
    renderRoute();
  });
  async function boot() {
    try { applySession(await api("/api/session")); await renderRoute(); }
    catch (error) {
      app.innerHTML = `<main id="main" class="boot-screen"><div class="brand-mark" aria-hidden="true">g.</div><h1>Let’s reconnect.</h1><p>${esc(errorText(error))}</p><button class="button" id="retry-boot">Try again</button></main>`;
      document.getElementById("retry-boot").addEventListener("click", boot);
    }
  }
  boot();
})();
