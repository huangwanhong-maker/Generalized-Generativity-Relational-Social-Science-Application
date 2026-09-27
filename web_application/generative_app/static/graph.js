"use strict";

/* A projection of one retained project revision. Canvas positions never write records. */
window.GSPGraph = (() => {
  const PROTOCOL = "gsp-record-protocol/0.2";
  const moduleValue = (record, name) => record?.modules?.[name];
  const supported = value => value && String(value.version) === "1";
  const uuid = () => crypto.randomUUID();

  function mount(root, context) {
    const { state, api, esc, icon, date, displayAuthor, chips, types, modes, apiProject, apiRecord, routeRecord, toast, errorText, dialog, openDialog, dialogHeader, editRecord, inputField, selectField } = context;
    const projectId = state.project.id;
    const base = apiProject(projectId);
    let alive = true, requestSequence = 0, inspectorSequence = 0;
    let spacetime = null;
    let cy = null, graph = { nodes: [], edges: [], warnings: [] }, history = [];
    let canvasWidth = 0, canvasHeight = 0;
    const resizeObserver = new ResizeObserver(entries => {
      const width = entries[0]?.contentRect.width || 0;
      const height = entries[0]?.contentRect.height || 0;
      const widthChanged = Math.abs(width - canvasWidth) >= 2;
      if (!cy || (!widthChanged && Math.abs(height - canvasHeight) < 2)) return;
      canvasWidth = width; canvasHeight = height;
      requestAnimationFrame(() => { if (alive && cy) { cy.resize(); if (widthChanged && cy.nodes().length) cy.fit(cy.elements(":visible"), 40); } });
    });
    let selected = state.graphSelection || null, tab = "overview", view = "graph", connecting = false, picked = [];
    let query = "", roleFilter = "";
    const localKey = `gsp:layout:general:${state.user.id}:${projectId}`;
    const currentRecord = () => state.records.find(record => record.id === selected);
    const mutationBlocked = () => (graph.warnings || []).some(warning => ["unsupported_profile", "unsupported_required_module"].includes(warning.code));
    const readOnly = () => Boolean(state.revision) || state.legacy || mutationBlocked();
    const revisionQuery = () => `?revision=${encodeURIComponent(state.head)}`;
    function positions() {
      try { return JSON.parse(localStorage.getItem(localKey) || "{}"); } catch (_) { return {}; }
    }
    function rememberPositions() {
      if (!cy || !alive) return;
      const stored = positions();
      cy.nodes().forEach(node => { stored[node.id()] = node.position(); });
      try { localStorage.setItem(localKey, JSON.stringify(stored)); } catch (_) { /* Layout storage is optional. */ }
    }
    function button(label, action, secondary = true, extra = "") {
      return `<button class="button ${secondary ? "secondary" : ""} small-button" type="button" data-graph-action="${action}" ${extra}>${label}</button>`;
    }
    function renderShell() {
      cy?.destroy(); cy = null;
      root.innerHTML = `<div id="snapshot-banner"></div><div class="graph-project-strip"><span class="chip privacy">${icon("lock")}Private project</span><span id="snapshot-label" class="small muted"></span><details class="export-menu"><summary>Export this project ${icon("download")}</summary><div><a id="graph-json-export">Records as JSON</a><a id="graph-package-export">Snapshot with files</a><a href="${esc(base)}/bundle">Complete Git history</a><p>Full history includes earlier text, reasons and detached files.</p></div></details></div><div class="graph-toolbar"><div class="workspace-tabs" role="tablist" aria-label="Project view"><button role="tab" data-graph-view="graph" aria-selected="${view === "graph"}">${icon("connection")}Graph</button><button role="tab" data-graph-view="list" aria-selected="${view === "list"}">${icon("record")}List</button><button role="tab" data-graph-view="spacetime" aria-selected="${view === "spacetime"}">${icon("clock")}Spacetime</button></div><div class="graph-filter-controls"><label class="search-input">${icon("search")}<span class="sr-only">Search records</span><input type="search" id="record-search" placeholder="Find a record…" value="${esc(query)}"></label><label><span class="sr-only">Filter by record role</span><select id="record-filter"><option value="">All roles</option>${types.map(role => `<option ${role === roleFilter ? "selected" : ""}>${esc(role)}</option>`).join("")}</select></label></div><label class="snapshot-picker"><span class="sr-only">Project revision</span><select id="project-revision"><option value="">Current project</option></select></label></div><div class="graph-commandbar"><div class="row">${button(`${icon("connection")}Connect records`, "connect")}${button("Connection form", "relation-form")}</div><span id="graph-filter-summary" class="graph-filter-summary" role="status"></span></div><div id="connect-instructions"></div><div class="graph-layout"><section class="graph-stage" aria-label="Record graph workspace"><div id="graph-canvas" role="img" aria-label="Graph of records and declared relationships. Use List view or the record selector for keyboard access."></div><div id="record-list" class="graph-record-list" hidden></div><div id="spacetime-panel" hidden aria-label="Event order and ontology trajectories"></div><div class="graph-empty" id="graph-empty" hidden><span class="empty-symbol">${icon("leaf")}</span><h2>Give a thought a place to grow.</h2><p>Start with a record. Connections can develop around it.</p><button class="button" data-action="new-record">${icon("plus")}Create your first record</button></div><div class="graph-view-tools" aria-label="Graph view controls">${button("+", "zoom-in", true, 'aria-label="Zoom in"')}${button("−", "zoom-out", true, 'aria-label="Zoom out"')}${button("Fit", "fit")}${button("Arrange", "arrange")}</div><div class="graph-legend"><span><i class="legend-record"></i>Record</span><span><i class="legend-relation"></i>Relation record</span><span><i class="legend-reference"></i>Neutral reference</span></div></section><aside class="graph-inspector" id="graph-inspector" aria-label="Selected record"></aside></div><div class="graph-bottom"><p>Double-click empty canvas to add a record, or use New record. Positions and lines do not establish chronology or causation.</p><span class="mono" id="graph-head"></span></div><div id="graph-warnings"></div>`;
      root.querySelector("#record-search").addEventListener("input", event => { query = event.target.value; applyFilters(); });
      root.querySelector("#record-filter").addEventListener("change", event => { roleFilter = event.target.value; applyFilters(); });
      root.querySelector("#project-revision").addEventListener("change", event => void loadSnapshot(event.target.value || null));
      root.addEventListener("click", onClick);
      spacetime = window.GSPSpaceTime.mount(root.querySelector("#spacetime-panel"), { api, base, esc, icon, errorText, selectRecord: selectNode, isReadOnly: readOnly });
    }
    function updateHeader() {
      root.querySelector("#snapshot-label").textContent = `${state.records.length} records · ${state.revision ? "preserved revision" : "current snapshot"}`;
      root.querySelector("#graph-head").textContent = state.head.slice(0, 10);
      root.querySelector("#graph-json-export").href = `${base}/export${revisionQuery()}`;
      root.querySelector("#graph-package-export").href = `${base}/package${revisionQuery()}`;
      root.querySelector("#snapshot-banner").innerHTML = state.revision
        ? `<div class="old-revision"><span>Historical project · ${esc(state.head.slice(0, 10))}. Records, labels and files are read-only at this revision.</span>${button("Return to current project", "current")}</div>`
        : state.legacy
          ? `<div class="migration-banner"><div><strong>This project uses the earlier record format.</strong><p>Its original records are preserved. Preview an explicit upgrade to enable graph editing and modules.</p></div>${button("Preview upgrade", "migrate-preview")}</div>` : mutationBlocked() ? '<div class="notice"><strong>This project needs an additional interpreter before editing.</strong><p>A required module or declared project profile is unsupported here. Retained content remains available for reading and export.</p></div>' : "";
      root.querySelectorAll('[data-graph-action="connect"], [data-graph-action="relation-form"]').forEach(item => { item.disabled = readOnly(); });
      const addButton = document.querySelector('.graph-heading [data-action="new-record"]');
      if (addButton) addButton.disabled = readOnly();
      const selector = root.querySelector("#project-revision");
      selector.innerHTML = `<option value="">Current project</option>${history.map(entry => `<option value="${esc(entry.commit)}" ${state.revision === entry.commit ? "selected" : ""}>${esc(date(entry.created_at))} · ${esc((entry.reason || "Project revision").slice(0, 64))} · ${esc(entry.commit.slice(0, 7))}</option>`).join("")}`;
      if (state.revision && !history.some(entry => entry.commit === state.revision)) selector.add(new Option(`Preserved ${state.revision.slice(0, 10)}`, state.revision, true, true));
    }
    async function loadSnapshot(commit = null, { accepted = false, select = selected } = {}) {
      const request = ++requestSequence;
      try {
        const data = await api(`${base}${commit ? `?revision=${encodeURIComponent(commit)}` : ""}`);
        const chosenHead = data.head || data.project.head;
        const [projection, timeline] = await Promise.all([api(`${base}/graph?revision=${encodeURIComponent(chosenHead)}`), api(`${base}/history`)]);
        if (!alive || request !== requestSequence) return;
        state.project = data.project; state.records = data.records; state.head = chosenHead;
        state.currentHead = data.current_head || chosenHead; state.legacy = Boolean(data.legacy);
        // A recovered receipt can point to an accepted revision older than today's head.
        // Preserve that exact result as history instead of labelling it current.
        state.revision = (commit && !accepted) || state.currentHead !== chosenHead ? chosenHead : null;
        graph = projection; history = timeline.history || [];
        spacetime.setSnapshot(chosenHead, state.records);
        selected = state.records.some(record => record.id === select) ? select : null;
        state.graphSelection = selected;
        connecting = false; picked = [];
        updateHeader(); draw(); renderInspector(); renderConnectBar();
        if (accepted && selected) { const heading = root.querySelector(".inspector-header h2"); heading?.setAttribute("tabindex", "-1"); heading?.focus({ preventScroll: true }); }
      } catch (error) { if (alive && request === requestSequence) { root.querySelector("#graph-warnings").innerHTML = `<p class="error-box">${esc(errorText(error))}</p>${button("Try loading again", "retry")}`; } }
    }
    function draw() {
      cy?.destroy(); cy = null;
      const canvas = root.querySelector("#graph-canvas");
      root.querySelector("#graph-empty").hidden = state.records.length > 0;
      if (window.cytoscape) {
        const remembered = positions();
        const elements = [
          ...graph.nodes.map((node, index) => ({ data: { ...node, label: node.label || node.id, relation: (node.record_roles || [node.record_type]).includes("Relation") ? 1 : 0 }, position: remembered[node.id] || { x: 120 + index % 4 * 160, y: 110 + Math.floor(index / 4) * 125 } })),
          ...graph.edges.map((edge, index) => ({ data: { ...edge, id: edge.id || `edge-${index}`, label: edge.role || "", neutral: edge.kind === "related" || edge.kind === "neutral_reference" || edge.kind === "reference" ? 1 : 0 } }))
        ];
        cy = window.cytoscape({ container: canvas, elements, layout: { name: "preset" }, minZoom: .18, maxZoom: 2.6, wheelSensitivity: .22, boxSelectionEnabled: false, selectionType: "single", style: [
          { selector: "node", style: { "shape": "round-rectangle", "background-color": "#eaf0e1", "border-color": "#aabf9b", "border-width": 1.3, "width": 120, "height": 56, "label": "data(label)", "color": "#334b3a", "font-family": "Inter, Segoe UI, sans-serif", "font-size": 11, "text-valign": "center", "text-halign": "center", "text-wrap": "ellipsis", "text-max-width": 100, "text-max-lines": 2 } },
          { selector: "node[relation = 1]", style: { "shape": "diamond", "width": 120, "height": 86, "background-color": "#f3ebd9", "border-color": "#c5b183", "text-max-width": 85 } },
          { selector: "edge", style: { "width": 1.5, "line-color": "#9fae91", "target-arrow-color": "#9fae91", "curve-style": "bezier", "label": "data(label)", "font-size": 9, "color": "#69785d", "text-rotation": "autorotate", "text-background-color": "#fafbf6", "text-background-opacity": .95, "text-background-padding": 3, "text-margin-y": -7 } },
          { selector: 'edge[orientation = "in"], edge[orientation = "out"]', style: { "target-arrow-shape": "triangle" } },
          { selector: "edge[neutral = 1]", style: { "line-style": "dashed", "line-color": "#adb8b4", "target-arrow-shape": "none", "label": "" } },
          { selector: "node:selected", style: { "border-color": "#315b43", "border-width": 3, "background-color": "#dce9d2" } },
          { selector: ".picked", style: { "border-width": 3, "border-color": "#9b7739", "background-color": "#f1e4c8" } },
          { selector: ".filtered", style: { "display": "none" } }
        ] });
        cy.on("tap", "node", event => selectNode(event.target.id()));
        cy.on("dbltap", event => { if (event.target === cy && !readOnly()) editRecord(null, { position: event.position }); });
        cy.on("dragfree", "node", rememberPositions);
        cy.on("tap", "edge", event => { const id = event.target.data("relation_id"); if (id) selectNode(id); });
        if (selected) cy.getElementById(selected).select();
        if (state.records.length) cy.fit(cy.elements(), 55);
      } else {
        canvas.innerHTML = '<div class="graph-load-note">The graph renderer is unavailable. The List view and forms remain available.</div>';
        view = "list";
      }
      root.querySelector("#graph-warnings").innerHTML = (graph.warnings || []).length ? `<details class="graph-warning-list"><summary>${graph.warnings.length} projection ${graph.warnings.length === 1 ? "note" : "notes"}</summary>${graph.warnings.map(warning => { const record = state.records.find(item => item.id === warning.record_id); return `<p>${record ? `<strong>${esc(record.title)}:</strong> ` : ""}${esc(typeof warning === "string" ? warning : warning.message || "Some retained material is not interpreted in this view.")}${warning.module_id ? ` <span class="mono">${esc(warning.module_id)}</span>` : ""}</p>`; }).join("")}</details>` : "";
      applyFilters(); changeView(view);
    }
    function applyFilters() {
      const term = query.trim().toLowerCase();
      const visible = new Set(state.records.filter(record => (!roleFilter || (record.record_roles || [record.record_type]).includes(roleFilter)) && [record.title, record.content, record.attributed_to, record.evidence].some(value => String(value || "").toLowerCase().includes(term))).map(record => record.id));
      let hiddenEdges = 0;
      cy?.batch(() => {
        cy.nodes().forEach(node => node.toggleClass("filtered", !visible.has(node.id())));
        cy.edges().forEach(edge => { const hidden = !visible.has(edge.source().id()) || !visible.has(edge.target().id()); edge.toggleClass("filtered", hidden); });
      });
      hiddenEdges = graph.edges.filter(edge => !visible.has(edge.source) || !visible.has(edge.target)).length;
      root.querySelector("#graph-filter-summary").textContent = `${visible.size} shown · ${state.records.length - visible.size} records and ${hiddenEdges} connections hidden`;
      root.querySelector("#record-list").innerHTML = state.records.filter(record => visible.has(record.id)).map(record => `<button class="graph-list-record ${selected === record.id ? "selected" : ""}" data-select-record="${esc(record.id)}"><span class="project-symbol">${icon((record.record_roles || [record.record_type]).includes("Relation") ? "connection" : "record")}</span><span><strong>${esc(record.title)}</strong><span class="graph-list-content">${esc(record.content.slice(0, 180))}</span><span class="record-chips">${chips(record)}</span></span>${icon("chevron")}</button>`).join("") || '<p class="no-results">No records match this view.</p>';
    }
    function changeView(next) {
      view = next;
      root.querySelectorAll("[data-graph-view]").forEach(item => item.setAttribute("aria-selected", String(item.dataset.graphView === next)));
      root.querySelector("#graph-canvas").hidden = next !== "graph";
      root.querySelector("#record-list").hidden = next !== "list";
      root.querySelector("#spacetime-panel").hidden = next !== "spacetime";
      root.querySelector(".graph-filter-controls").hidden = next === "spacetime";
      root.querySelector(".graph-commandbar").hidden = next === "spacetime";
      root.querySelector(".graph-bottom p").textContent = next === "spacetime" ? "Event boundaries select a partial view of represented topology. Unknown scope remains visible in the coverage list. Changing the boundary does not write a revision." : "Double-click empty canvas to add a record, or use New record. Positions and lines do not establish chronology or causation.";
      if (next === "spacetime" && connecting) { connecting = false; picked = []; renderConnectBar(); }
      spacetime?.show(next === "spacetime");
      root.querySelector(".graph-view-tools").hidden = next !== "graph";
      root.querySelector(".graph-legend").hidden = next !== "graph";
      root.querySelector("#graph-empty").hidden = state.records.length > 0 || next !== "graph";
      if (next === "graph") cy?.resize();
    }
    function selectNode(id) {
      if (connecting) { if (!picked.includes(id)) picked.push(id); renderConnectBar(); return; }
      selected = id; tab = "overview"; state.graphSelection = id;
      cy?.nodes().unselect(); cy?.getElementById(id).select();
      renderInspector(); applyFilters();
      const heading = root.querySelector(".inspector-header h2"); heading?.setAttribute("tabindex", "-1"); heading?.focus({ preventScroll: true });
    }
    function renderConnectBar() {
      root.querySelector("#connect-instructions").innerHTML = connecting ? `<div class="connect-bar"><div><strong>Choose the records to connect.</strong><p>Select nodes on the canvas or in List view. Add, repeat or change participants in the form.</p><span>${picked.length} selected: ${esc(picked.map(id => state.records.find(r => r.id === id)?.title || id).join(" · "))}</span></div><div class="row">${button("Review connection", "review-connection", false)}${button("Cancel", "cancel-connect")}</div></div>` : "";
      cy?.nodes().forEach(node => node.toggleClass("picked", picked.includes(node.id())));
      // The instruction panel moves the canvas even when its dimensions stay the same.
      // Refresh the renderer's page offset so pointer selection still matches the drawing.
      cy?.resize();
    }
    function moduleData(record, name) { const value = moduleValue(record, name); return supported(value) ? value.data || {} : null; }
    function renderInspector() {
      const panel = root.querySelector("#graph-inspector");
      const record = currentRecord();
      ++inspectorSequence;
      if (!record) {
        panel.innerHTML = `<div class="inspector-welcome"><span class="eyebrow">A closer reading</span><h2>Every connection has a story.</h2><p>Select a record to read its account, explore its relationships, and open its files or notes.</p><label class="label" for="record-selector">Choose a record</label><select id="record-selector"><option value="">Select from this snapshot…</option>${state.records.map(item => `<option value="${esc(item.id)}">${esc(item.title)}</option>`).join("")}</select><div class="inspector-hint">${icon("connection")}A diamond is a relation record. It has its own identity, grounds and history.</div></div>`;
        panel.querySelector("#record-selector").addEventListener("change", event => { if (event.target.value) selectNode(event.target.value); });
        return;
      }
      const modules = record.modules || {};
      const tabs = [["overview", "Overview"], ["temporal", "Time & trajectory"], ...(modules["gsp.relation"] ? [["relation", "Relation"]] : []), ...(modules["gsp.files"] ? [["files", "Files"]] : []), ...(modules["gsp.notes"] ? [["notes", "Notes"]] : []), ["history", "History"]];
      if (!tabs.some(([id]) => id === tab)) tab = "overview";
      panel.innerHTML = `<header class="inspector-header"><span class="eyebrow">${esc((record.record_roles || [record.record_type]).join(" · "))}</span><h2>${esc(record.title)}</h2><button class="button ghost icon-button inspector-close" data-graph-action="deselect" aria-label="Close selected record">${icon("close")}</button><div class="inspector-tabs" role="tablist" aria-label="Record modules">${tabs.map(([id, title]) => `<button role="tab" aria-selected="${tab === id}" data-inspector-tab="${id}">${title}</button>`).join("")}</div></header><div class="inspector-body" id="inspector-body"></div><footer class="inspector-footer"><span class="mono">${esc(record.id.slice(0, 13))}…</span><span>${state.revision ? "Preserved" : "Snapshot"} ${esc(state.head.slice(0, 7))}</span></footer>`;
      const body = panel.querySelector("#inspector-body");
      if (tab === "overview") {
        const unsupported = Object.entries(modules).filter(([name, value]) => !["gsp.files", "gsp.notes", "gsp.relation", "gsp.event_order", "gsp.temporal_extent"].includes(name) || !supported(value));
        body.innerHTML = `<div class="record-chips">${chips(record)}</div><p class="inspector-content">${esc(record.content)}</p><dl class="inspector-facts"><dt>Attributed source</dt><dd>${esc(record.attributed_to || "Not recorded")}</dd><dt>Method and grounds</dt><dd>${esc(record.method || "Not recorded")}</dd><dt>Evidence references</dt><dd>${esc(record.evidence || "Not recorded")}</dd><dt>Uncertainty</dt><dd>${esc(record.uncertainty || "Not recorded")}</dd><dt>Recorded by</dt><dd>${esc(displayAuthor(record.recorded_by))} · ${esc(date(record.created_at))}</dd></dl>${(record.record_roles || [record.record_type]).includes("Relation") && !modules["gsp.relation"] ? '<p class="notice">Unstructured relation account. No participant roles or predicate have been inferred from its text.</p>' : ""}<div class="inspector-actions">${!readOnly() ? button(`${icon("edit")}Revise record`, "edit-selected") + button("Create connected record", "create-connected") : ""}${button("Read full account", "full-record")}</div>${!readOnly() ? `<section class="module-options"><h3>Add to this record</h3><div class="row">${!modules["gsp.files"] ? button(`${icon("folder")}Files`, "enable-files") : ""}${!modules["gsp.notes"] ? button(`${icon("record")}Notes`, "enable-notes") : ""}${(record.record_roles || [record.record_type]).includes("Relation") && !modules["gsp.relation"] ? button("Structure relation", "structure-relation") : ""}</div><p>Modules retain material with this record and its revisions.</p></section>` : ""}${unsupported.map(([name, value]) => `<details class="unsupported-module"><summary>${esc(name)} · unsupported ${value.required ? "required" : "optional"} module</summary><p>This data is preserved and read-only in this application.</p><pre>${esc(JSON.stringify(value, null, 2))}</pre></details>`).join("")}`;
      } else if (tab === "temporal") renderTemporal(body, record);
      else if (tab === "relation") renderRelation(body, record);
      else if (tab === "files") renderFiles(body, record);
      else if (tab === "notes") renderNotes(body, record);
      else if (tab === "history") void renderRecordHistory(body, record, inspectorSequence);
    }
    function temporalBoundary(boundary) {
      if (boundary?.kind === "event") return state.records.find(item => item.id === boundary.event_id)?.title || boundary.event_id;
      return boundary?.kind === "unbounded" ? "Unbounded within this account's scope" : "Unknown / not recorded";
    }
    function renderTemporal(body, record) {
      const extent = moduleData(record, "gsp.temporal_extent"), order = moduleData(record, "gsp.event_order");
      const isEvent = (record.record_roles || [record.record_type]).includes("Event");
      const relatedOrders = state.records.filter(item => {
        const data = moduleData(item, "gsp.event_order");
        return data && (data.before === record.id || data.after === record.id);
      });
      const supportedExtent = !record.modules?.["gsp.temporal_extent"] || supported(record.modules["gsp.temporal_extent"]);
      body.innerHTML = `<span class="eyebrow">Time &amp; trajectory</span><p class="field-help">Temporal boundaries describe the represented situation. They are independent of when this record was saved.</p><dl class="inspector-facts"><dt>Described time</dt><dd>${esc(record.occurred_at || "Not recorded")}</dd><dt>Start boundary · inclusive</dt><dd>${esc(temporalBoundary(extent?.start))}</dd><dt>End boundary · exclusive</dt><dd>${esc(temporalBoundary(extent?.end))}</dd><dt>Grounds for these boundaries</dt><dd>${esc(extent?.basis || "No temporal extent recorded")}</dd><dt>Trajectory subject</dt><dd>${extent?.subject_record_id ? `<button class="button-link" data-select-record="${esc(extent.subject_record_id)}">${esc(state.records.find(item => item.id === extent.subject_record_id)?.title || extent.subject_record_id)}</button>` : "This record; no additional subject grouping"}</dd></dl>${!supportedExtent ? '<p class="notice">This temporal module version is unsupported. Its retained data remains available in Overview.</p>' : !readOnly() ? button(extent ? "Revise temporal extent" : "Describe temporal extent", "edit-temporal") + (extent ? button("Remove temporal extent", "remove-temporal_extent") : "") : ""}${order ? `<section class="module-options"><h3>Precedence account</h3><p>${esc(temporalBoundary({ kind: "event", event_id: order.before }))} → ${esc(temporalBoundary({ kind: "event", event_id: order.after }))}</p><p>Claimed order: before. Assessment: ${esc(record.status)}. Occurrence: ${esc(record.modality)}. Revise the record's assessment to withdraw this constraint while preserving its history.</p>${!readOnly() ? button("Revise event order", "edit-order") : ""}</section>` : ""}${isEvent ? `<section class="module-options"><h3>Order around this event</h3><ul class="temporal-order-links">${relatedOrders.map(item => `<li><button class="button-link" data-select-record="${esc(item.id)}">${esc(item.title)}</button><br><span class="small muted">${esc(item.status)} · ${esc(item.modality)}</span></li>`).join("") || '<li>No precedence accounts recorded. This does not mean the event is simultaneous with another.</li>'}</ul>${!readOnly() ? button("Add event order", "temporal-order") : ""}</section>` : ""}<p class="field-help">Unknown boundaries are not treated as unbounded. A subject grouping is an attributed connection among descriptions, not an identity determination.</p>`;
    }
    function temporalDialog() {
      const record = currentRecord(); if (!record) return;
      const priorModule = moduleValue(record, "gsp.temporal_extent");
      if (priorModule && !supported(priorModule)) return;
      const prior = priorModule?.data || {};
      const events = state.records.filter(item => (item.record_roles || [item.record_type]).includes("Event"));
      function boundaryFields(name, label, boundary) {
        return `<fieldset class="temporal-bound-editor"><legend>${label}</legend><div class="field"><label class="label" for="temporal-${name}-kind">Boundary description</label><select id="temporal-${name}-kind" name="${name}_kind">${[["unknown", "Unknown / not recorded"], ["event", "At a recorded event"], ["unbounded", "Unbounded within this account's scope"]].map(([value, text]) => `<option value="${value}" ${(boundary?.kind || "unknown") === value ? "selected" : ""}>${text}</option>`).join("")}</select></div><div class="field" data-temporal-event-field="${name}"><label class="label" for="temporal-${name}-event">Event boundary</label><select id="temporal-${name}-event" name="${name}_event"><option value="">Choose an event…</option>${events.map(item => `<option value="${esc(item.id)}" ${boundary?.event_id === item.id ? "selected" : ""}>${esc(item.title)}</option>`).join("")}</select></div></fieldset>`;
      }
      mutationDialog({ title: "Describe this record's temporal extent.", description: "Choose event boundaries for the represented situation, with grounds for the account.", category: "evidence_or_interpretation", body: `<p class="notice">${esc(record.title)}. A start event is included; an end event is excluded. Unknown boundaries keep presence indeterminate. Unbounded is an explicit claim within your stated scope.</p>${boundaryFields("start", "Start · inclusive", prior.start)}${boundaryFields("end", "End · exclusive", prior.end)}<div class="field"><label class="label optional-label" for="temporal-subject">Group this description under a subject</label><select id="temporal-subject" name="subject_record_id"><option value="">No additional grouping</option>${state.records.map(item => `<option value="${esc(item.id)}" ${prior.subject_record_id === item.id ? "selected" : ""}>${esc(item.title)}</option>`).join("")}</select><p class="field-help">For example, group successive State records under the Entity they describe. This does not resolve identity or competing accounts.</p></div>${inputField("temporal_basis", "Grounds and scope for these temporal boundaries", prior.basis, 2000, { required: true, multiline: true, rows: 3, placeholder: "How is this interval known, and within what scope?" })}`, onReady: form => {
        for (const name of ["start", "end"]) {
          const update = () => {
            const isEvent = form.elements[`${name}_kind`].value === "event";
            form.querySelector(`[data-temporal-event-field="${name}"]`).hidden = !isEvent;
            form.elements[`${name}_event`].required = isEvent;
          };
          form.elements[`${name}_kind`].addEventListener("change", update); update();
        }
      }, prepare: form => {
        const values = new FormData(form);
        const boundary = name => values.get(`${name}_kind`) === "event" ? { kind: "event", event_id: String(values.get(`${name}_event`)) } : { kind: String(values.get(`${name}_kind`)) };
        const data = { start: boundary("start"), end: boundary("end"), basis: String(values.get("temporal_basis") || "").trim() };
        if (values.get("subject_record_id")) data.subject_record_id = String(values.get("subject_record_id"));
        return [{ op: "module.set", record_id: record.id, module_id: "gsp.temporal_extent", module: { version: "1", required: true, data } }];
      }, saved: "Temporal extent preserved with its grounds." });
      tab = "temporal";
    }
    function orderDialog(record = null) {
      if (readOnly()) return;
      const events = state.records.filter(item => (item.record_roles || [item.record_type]).includes("Event"));
      if (!events.length) { toast("Create an Event record before describing event order."); return; }
      const relationId = record?.id || uuid(), prior = moduleData(record, "gsp.event_order") || {};
      if (record?.modules?.["gsp.event_order"] && !supported(record.modules["gsp.event_order"])) return;
      let priorRelation = moduleData(record, "gsp.relation") || {};
      let incidenceIds = [priorRelation.participants?.find(item => item.orientation === "in")?.id || uuid(), priorRelation.participants?.find(item => item.orientation === "out")?.id || uuid()];
      const selectedEvent = events.some(item => item.id === selected) ? selected : "";
      const eventSelector = (name, label, chosen) => `<div class="field"><label class="label" for="order-${name}">${label}</label><select id="order-${name}" name="${name}" required><option value="">Choose an event…</option>${events.map(item => `<option value="${esc(item.id)}" ${item.id === chosen ? "selected" : ""}>${esc(item.title)}</option>`).join("")}</select></div>`;
      mutationDialog({ title: record ? "Revise the event precedence account." : "Describe an order between events.", description: "An ordering account is a Relation record with its own grounds and revision history.", select: relationId, category: "evidence_or_interpretation", body: `<p class="notice">Declare strict precedence: the first event happened before the second in this account. Recording order, visual proximity and absence of an arrow do not establish temporal order. Conflicting claims remain inspectable and can prevent a consistent projection.</p><div class="field-grid">${eventSelector("before", "Earlier event", prior.before || selectedEvent)}${eventSelector("after", "Later event", prior.after)}</div>${inputField("order_title", "Ordering account title", record?.title, 160, { placeholder: "Optional; otherwise named after the events" })}${inputField("order_content", "Account and grounds for this ordering", record?.content, 20000, { required: true, multiline: true, rows: 3 })}${selectField("order_epistemic_mode", "Primary knowledge basis", modes, record?.epistemic_mode || "", "The claim remains attributed; an arrow is not independent proof.", "How is this order known?")}${selectField("order_modality", "Occurrence or possibility of this ordering", ["realized", "intended", "possible", "unrealized", "unknown"], record?.modality || "unknown", "Describe whether this is an account of an actual sequence or a possible, intended, unrealized or unknown one.")}`, prepare: form => {
        const values = new FormData(form), before = String(values.get("before")), after = String(values.get("after"));
        const name = id => events.find(item => item.id === id)?.title || id;
        const title = String(values.get("order_title") || "").trim() || `${name(before)} precedes ${name(after)}`.slice(0, 160);
        const core = { title, content: String(values.get("order_content") || "").trim(), epistemic_mode: String(values.get("order_epistemic_mode")), modality: String(values.get("order_modality")) };
        const orderModule = { version: "1", required: true, data: { before, after } };
        const relationModule = { version: "1", required: record?.modules?.["gsp.relation"]?.required || false, data: { ...priorRelation, predicate: priorRelation.predicate || "precedes", predicate_definition: priorRelation.predicate_definition ?? "The represented first event strictly precedes the represented second event in this attributed account.", participants: [{ id: incidenceIds[0], record_id: before, role: priorRelation.participants?.find(item => item.orientation === "in")?.role || "before", reference_scope: "represented_target", orientation: "in" }, { id: incidenceIds[1], record_id: after, role: priorRelation.participants?.find(item => item.orientation === "out")?.role || "after", reference_scope: "represented_target", orientation: "out" }], participants_complete: record ? priorRelation.participants_complete !== false : true, participant_limitations: priorRelation.participant_limitations || "", context: priorRelation.context || "", identity_criterion: priorRelation.identity_criterion || "An attributed claim of strict event precedence.", temporal_scope: priorRelation.temporal_scope || "" } };
        if (record) return [{ op: "record.update", record_id: record.id, changes: core }, { op: "module.set", record_id: record.id, module_id: "gsp.relation", module: relationModule }, { op: "module.set", record_id: record.id, module_id: "gsp.event_order", module: orderModule }];
        return [{ op: "record.create", record: { id: relationId, ...core, record_type: "Relation", record_roles: ["Relation"], status: "unreviewed", related_records: [], modules: { "gsp.relation": relationModule, "gsp.event_order": orderModule } } }];
      }, onReviewed: latest => {
        const reviewed = latest.records.find(item => item.id === relationId);
        if (record && reviewed) {
          record = reviewed;
          priorRelation = moduleData(reviewed, "gsp.relation") || {};
          incidenceIds = [priorRelation.participants?.find(item => item.orientation === "in")?.id || uuid(), priorRelation.participants?.find(item => item.orientation === "out")?.id || uuid()];
        }
      }, saved: "Event ordering account preserved." });
      tab = "temporal";
    }
    function renderRelation(body, record) {
      const relation = moduleData(record, "gsp.relation");
      if (!relation) { body.innerHTML = '<p class="notice">This relation module version is unsupported; its data is preserved.</p>'; return; }
      body.innerHTML = `<span class="eyebrow">Declared relationship</span><h3>${esc(relation.predicate)}</h3><p class="small">${esc(relation.predicate_definition || "No predicate definition supplied.")}</p><div class="participant-list">${(relation.participants || []).map(participant => { const target = state.records.find(r => r.id === participant.record_id); return `<div class="participant-card"><span class="chip">${esc(participant.role)}</span><button class="button-link" data-select-record="${esc(participant.record_id)}">${esc(target?.title || "Referenced record unavailable")}</button><span>${participant.reference_scope === "record" ? "The record itself" : "Its represented target"} · ${esc(participant.orientation)}</span></div>`; }).join("")}</div><dl class="inspector-facts"><dt>Participant scope</dt><dd>${relation.participants_complete ? "Listed participants declared complete" : esc(relation.participant_limitations || "Incomplete")}</dd><dt>Context</dt><dd>${esc(relation.context || "Not recorded")}</dd><dt>Identity criterion</dt><dd>${esc(relation.identity_criterion || "Not recorded")}</dd><dt>Temporal scope</dt><dd>${esc(relation.temporal_scope || "Not recorded")}</dd></dl><p class="field-help">Orientation describes the incidence, without establishing causation or evidential strength.</p>${!readOnly() ? record.modules?.["gsp.event_order"] ? button("Revise event order", "edit-order") : button("Revise relation", "edit-relation") + button("Remove structure", "remove-relation") : ""}`;
    }
    function renderFiles(body, record) {
      const files = moduleData(record, "gsp.files");
      if (!files) { body.innerHTML = '<p class="notice">This file module version is unsupported; its data is preserved.</p>'; return; }
      body.innerHTML = `<p class="field-help">Retained material is available at this project revision. Preserving bytes does not independently verify their content.</p><div class="retained-files">${(files.items || []).map(file => `<article class="retained-file"><a class="file-download" href="${esc(apiRecord(projectId, record.id))}/files/${esc(file.file_id)}${revisionQuery()}">${icon("download")}<strong>${esc(file.filename)}</strong></a><span class="small muted">${esc(formatSize(file.byte_length))} · ${esc(file.media_type)}</span><details><summary>Custody details</summary><dl class="inspector-facts"><dt>SHA-256</dt><dd class="mono">${esc(file.sha256)}</dd><dt>Attached</dt><dd>${esc(date(file.uploaded_at, true))} · ${esc(displayAuthor(file.uploaded_by))}</dd><dt>File identifier</dt><dd class="mono">${esc(file.file_id)}</dd></dl></details>${!readOnly() ? `<div class="row">${button("Replace", "replace-file", true, `data-file-id="${esc(file.file_id)}"`)}${button("Detach", "detach-file", true, `data-file-id="${esc(file.file_id)}"`)}</div>` : ""}</article>`).join("") || '<p class="missing">No files are attached.</p>'}</div>${!readOnly() ? button(`${icon("plus")}Attach a file`, "attach-file", false) + (!(files.items || []).length ? button("Remove Files module", "remove-files") : "") : ""}`;
    }
    function renderNotes(body, record) {
      const notes = moduleData(record, "gsp.notes");
      if (!notes) { body.innerHTML = '<p class="notice">This notes module version is unsupported; its data is preserved.</p>'; return; }
      body.innerHTML = `<p class="field-help">Supplementary notes retained with the record. They have the same project access as the account.</p><p class="inspector-content">${esc(notes.text || "No notes recorded yet.")}</p>${!readOnly() ? button("Edit notes", "edit-notes") + button("Remove Notes module", "remove-notes") : ""}`;
    }
    async function renderRecordHistory(body, record, sequence) {
      body.innerHTML = '<p class="small muted" role="status">Reading record history…</p>';
      try {
        const result = await api(`${apiRecord(projectId, record.id)}/history${revisionQuery()}`);
        if (!alive || sequence !== inspectorSequence) return;
        body.innerHTML = `<p class="field-help">Selecting a revision opens the whole project at that point, including related labels and material.</p><ol class="history-list">${(result.history || []).map(entry => `<li class="history-entry"><button class="history-reason" data-project-revision="${esc(entry.commit)}">${esc(entry.reason || "Record saved")}</button><span class="history-meta">${esc(displayAuthor(entry.author))}<br>${esc(date(entry.created_at, true))}<br>${esc(entry.commit.slice(0, 10))}</span></li>`).join("")}</ol>`;
      } catch (error) { if (alive && sequence === inspectorSequence) body.innerHTML = `<p class="error-box">${esc(errorText(error))}</p>`; }
    }
    function formatSize(bytes) { return bytes < 1024 ? `${bytes} bytes` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`; }
    function mutationDialog({ title, description, body, prepare, saved = "Project revision preserved.", select = selected, category = "description", onReady, onReviewed }) {
      if (readOnly() && category !== "migration") return;
      let expectedHead = state.head, pending = null;
      openDialog(`${dialogHeader(title, description, "Preserve a revision")}<form id="module-form"><div class="dialog-body">${body}${category !== "migration" ? selectField("change_category", "What kind of change is this?", ["description", "represented_change", "evidence_or_interpretation", "classification", "maintenance"], category, "This records your account of the change. It does not independently establish that a situation changed.") : '<p class="field-help">Change category: format migration.</p>'}${inputField("reason", "Reason for this change", "", 2000, { required: true, multiline: true, rows: 2, placeholder: "What changed, and why should it be retained?" })}<div class="form-error" role="alert"></div><div class="transaction-conflict"></div></div><footer class="dialog-footer"><span class="small">Saved together in one project revision.</span><div class="row"><button class="button secondary" data-action="close-dialog" type="button">Cancel</button><button class="button" type="submit">Save revision${icon("arrow")}</button></div></footer></form>`);
      const form = dialog.querySelector("form");
      onReady?.(form);
      form.addEventListener("submit", async event => {
        event.preventDefault();
        const submit = form.querySelector('[type="submit"]');
        submit.disabled = true; form.querySelector(".form-error").innerHTML = "";
        try {
          const prepared = await prepare(form);
          const operations = prepared.operations || prepared;
          const reason = String(new FormData(form).get("reason") || "").trim();
          const chosenCategory = category === "migration" ? "migration" : String(new FormData(form).get("change_category") || category);
          const signature = JSON.stringify({ operations, reason, expectedHead, chosenCategory });
          if (!pending || pending.signature !== signature) pending = { signature, envelope: { protocol_version: PROTOCOL, transaction_id: uuid(), expected_head: expectedHead, reason, change_categories: [chosenCategory], operations }, files: prepared.files || {} };
          let requestBody = pending.envelope;
          if (Object.keys(pending.files).length) {
            requestBody = new FormData();
            requestBody.append("transaction", JSON.stringify(pending.envelope));
            for (const [part, file] of Object.entries(pending.files)) requestBody.append(part, file, file.name);
          }
          const result = await api(`${base}/transactions`, { method: "POST", body: requestBody });
          await loadSnapshot(result.head, { accepted: true, select });
          dialog.close(); toast(result.replayed ? "The earlier save was already preserved; recovered its receipt." : saved);
          root.querySelector(".inspector-header h2")?.focus({ preventScroll: true });
        } catch (error) {
          form.querySelector(".form-error").innerHTML = `<p class="error-box">${esc(errorText(error))}</p>`;
          if (error.status === 409) {
            const conflict = form.querySelector(".transaction-conflict");
            conflict.innerHTML = `<div class="conflict-panel"><strong>The project changed. Your draft remains here.</strong><p>Review the latest saved snapshot before basing this change on it.</p><button type="button" class="button secondary small-button" id="module-review-latest">Review latest snapshot</button><div id="module-latest-preview"></div></div>`;
            conflict.querySelector("#module-review-latest").addEventListener("click", async event => {
              event.currentTarget.disabled = true;
              const preview = conflict.querySelector("#module-latest-preview");
              try {
                const latest = await api(base);
                const affected = latest.records.filter(record => pending?.envelope.operations.some(operation => operation.record_id === record.id || operation.record?.id === record.id));
                preview.innerHTML = `<div class="conflict-preview"><p>${latest.records.length} records · ${esc(latest.head.slice(0, 10))}</p><pre>${esc(JSON.stringify(affected, null, 2))}</pre><p>Keeping your draft will apply the fields shown in this form to that reviewed version. It will not merge competing descriptions.</p><button type="button" class="button secondary small-button" id="module-use-latest">Use reviewed version and keep draft</button></div>`;
                preview.querySelector("#module-use-latest").addEventListener("click", () => { onReviewed?.(latest); expectedHead = latest.head; pending = null; conflict.innerHTML = '<p class="notice">The draft now uses the reviewed project revision. Review it and save again.</p>'; });
              } catch (failure) { preview.innerHTML = `<p class="error-box">${esc(errorText(failure))}</p>`; event.currentTarget.disabled = false; }
            });
          } else if (!error.status) {
            form.querySelector(".form-error").insertAdjacentHTML("beforeend", '<p class="field-help">Retry without changing the form to recover this same transaction if the connection failed after saving.</p>');
          }
          submit.disabled = false;
        }
      });
    }
    function enableModule(name) {
      const record = currentRecord(); if (!record) return;
      const moduleId = name === "files" ? "gsp.files" : "gsp.notes";
      mutationDialog({ title: `Add ${name} to this record.`, description: "An empty module is retained explicitly; you can add material afterward.", body: `<p class="notice">${esc(record.title)} · ${name === "files" ? "Files preserve their bytes and earlier versions in project history." : "Notes are supplementary retained text, with the same access as this record."}</p>`, prepare: () => [{ op: "module.set", record_id: record.id, module_id: moduleId, module: { version: "1", required: false, data: name === "files" ? { items: [] } : { text: "" } } }], saved: `${name === "files" ? "Files" : "Notes"} module added.` });
      tab = name;
    }
    function removeModule(name) {
      const label = name.replaceAll("_", " ");
      const record = currentRecord(); if (!record) return;
      mutationDialog({ title: `Remove ${name === "relation" ? "relation structure" : `${label} module`}.`, description: "Earlier versions remain in project history.", body: `<p class="notice">This removes the current ${esc(label)} module from “${esc(record.title)}”. It does not erase historical content or delete the record.</p>`, prepare: () => [{ op: "module.remove", record_id: record.id, module_id: `gsp.${name}` }], saved: "Module removed from the current record." });
    }
    function notesDialog() {
      const record = currentRecord(); if (!record) return;
      const prior = moduleValue(record, "gsp.notes");
      mutationDialog({ title: "Give the account more context.", description: "Notes are retained with this record and are visible to the same project account.", body: inputField("notes", "Supplementary notes", prior.data?.text || "", 20000, { multiline: true, rows: 9 }), prepare: form => [{ op: "module.set", record_id: record.id, module_id: "gsp.notes", module: { version: "1", required: prior.required, data: { text: String(new FormData(form).get("notes") || "") } } }], saved: "Notes revision preserved." });
    }
    function attachmentDialog(replacing = null) {
      const record = currentRecord(); if (!record) return;
      const fileId = replacing || uuid();
      mutationDialog({ title: replacing ? "Replace retained material." : "Attach material to this account.", description: "File bytes and the record's reference are saved together.", body: `<div class="field"><label class="label" for="retained-upload">Choose a file</label><input type="file" id="retained-upload" name="file" required><p class="field-help">Up to 10 MiB. Files download as attachments. Earlier bytes remain in Git history, including after replacement or detachment.</p></div>`, category: "evidence_or_interpretation", prepare: async form => {
        const file = form.elements.file.files[0];
        if (!file) throw new Error("Choose a file to retain.");
        if (file.size > 10 * 1024 * 1024) throw new Error("This file exceeds the 10 MiB limit.");
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer())), byte => byte.toString(16).padStart(2, "0")).join("");
        return { operations: [{ op: replacing ? "file.replace" : "file.attach", record_id: record.id, file_id: fileId, part: "file0", filename: file.name, media_type: file.type || "application/octet-stream", sha256: digest, byte_length: file.size }], files: { file0: file } };
      }, saved: replacing ? "File replacement preserved; earlier bytes remain available." : "File and record reference preserved together." });
    }
    function detachFile(id) {
      const record = currentRecord(); if (!record) return;
      const file = moduleData(record, "gsp.files")?.items.find(item => item.file_id === id);
      mutationDialog({ title: "Detach material from this record.", description: "Detachment changes the current account and does not erase retained history.", body: `<p class="notice">${esc(file?.filename || id)} will no longer be linked in the current record. Its earlier versions and bytes remain in the full project history.</p>`, category: "maintenance", prepare: () => [{ op: "file.detach", record_id: record.id, file_id: id }], saved: "File detached from the current account." });
    }
    function participantMarkup(participant, index, relationId) {
      const options = [...state.records, ...(!state.records.some(record => record.id === relationId) ? [{ id: relationId, title: "This relation (self-reference)", record_type: "Relation" }] : [])];
      return `<fieldset class="participant-editor" data-participant-id="${esc(participant.id || uuid())}"><legend>Participant ${index + 1}</legend><div class="field-grid"><div class="field"><label class="label" for="participant-${index}">Record</label><select id="participant-${index}" name="participant_record" required><option value="">Choose a record…</option>${options.map(record => `<option value="${esc(record.id)}" ${record.id === participant.record_id ? "selected" : ""}>${esc(record.title)} · ${esc(record.record_type)}</option>`).join("")}</select></div><div class="field"><label class="label" for="role-${index}">Participant role</label><input id="role-${index}" name="participant_role" value="${esc(participant.role || "")}" maxlength="120" required placeholder="For example: contributor or context"></div><div class="field"><label class="label" for="scope-${index}">What is related?</label><select id="scope-${index}" name="participant_scope"><option value="represented_target" ${participant.reference_scope !== "record" ? "selected" : ""}>The represented target</option><option value="record" ${participant.reference_scope === "record" ? "selected" : ""}>This record itself</option></select></div><div class="field"><label class="label" for="orientation-${index}">Orientation</label><select id="orientation-${index}" name="participant_orientation">${["undirected", "in", "out"].map(value => `<option value="${value}" ${participant.orientation === value ? "selected" : ""}>${value === "in" ? "Into relation" : value === "out" ? "Out of relation" : "Undirected"}</option>`).join("")}</select></div></div><button type="button" class="button text" data-remove-participant>Remove participant</button></fieldset>`;
    }
    function relationDialog(ids = [], record = null) {
      if (readOnly()) return;
      const relationId = record?.id || uuid();
      const priorModule = moduleValue(record, "gsp.relation");
      const prior = supported(priorModule) ? priorModule.data : {};
      let participants = prior.participants || ids.map(id => ({ id: uuid(), record_id: id, role: "", orientation: "undirected", reference_scope: "represented_target" }));
      if (!participants.length) participants = [{ id: uuid() }, { id: uuid() }];
      mutationDialog({ title: record ? "Describe this relationship precisely." : "A connection deserves its own account.", description: "Create a relation record with named participant roles, scope and grounds.", select: relationId, body: `${!record ? `${inputField("title", "Relation title", "", 160, { required: true, placeholder: "A short name for this relationship" })}${inputField("content", "Describe the relationship and its grounds", "", 20000, { required: true, multiline: true, rows: 3 })}${selectField("epistemic_mode", "Primary knowledge basis", modes, "", "Describe mixed or uncertain grounds in the account.", "How is this known?")}` : `<p class="notice">${esc(record.title)} · revising the structured relation module</p>`}${inputField("predicate", "Relationship predicate", prior.predicate, 160, { required: true, placeholder: "For example: contributes to, constrains, disputes" })}${inputField("predicate_definition", "Meaning of this predicate", prior.predicate_definition, 2000, { multiline: true, rows: 2 })}<p class="field-help">A participant can be another relation, or this relation itself. Repeated participants and separate relations between the same records retain their own identities.</p><div id="relation-participants">${participants.map((participant, index) => participantMarkup(participant, index, relationId)).join("")}</div><button class="button secondary small-button" type="button" id="add-participant">${icon("plus")}Add participant</button><div class="field participant-completeness"><label class="label" for="relation-completeness">Does the list cover this account's declared participant scope?</label><select id="relation-completeness" name="participants_complete" required><option value="">Choose the scope of this account?</option><option value="complete" ${prior.participants_complete === true ? "selected" : ""}>Complete within the stated scope</option><option value="incomplete" ${prior.participants_complete === false ? "selected" : ""}>Incomplete participant account</option></select></div>${inputField("participant_limitations", "Limits of the participant list", prior.participant_limitations, 2000, { multiline: true, rows: 2, help: "Required when the participant list is incomplete." })}<details class="form-section"><summary>Context, identity and time</summary><div class="form-section-content">${inputField("context", "Context", prior.context, 2000, { multiline: true })}${inputField("identity_criterion", "What identifies this relation?", prior.identity_criterion, 2000, { multiline: true, help: "Describe how this relation differs from another with the same participants." })}${inputField("temporal_scope", "Temporal scope", prior.temporal_scope, 1000, { multiline: true, rows: 2 })}</div></details>`, onReady: form => {
        form.querySelector("#add-participant").addEventListener("click", () => {
          const container = form.querySelector("#relation-participants");
          if (container.children.length >= 32) { toast("This profile allows up to 32 listed participants."); return; }
          const index = Number(container.dataset.next || participants.length); container.dataset.next = String(index + 1);
          container.insertAdjacentHTML("beforeend", participantMarkup({ id: uuid() }, index, relationId));
          container.lastElementChild.querySelector("select").focus();
        });
        form.addEventListener("click", event => { if (event.target.closest("[data-remove-participant]")) event.target.closest("fieldset").remove(); });
        const complete = form.elements.participants_complete;
        const update = () => { form.elements.participant_limitations.required = complete.value === "incomplete"; };
        complete.addEventListener("change", update); update();
      }, prepare: form => {
        const values = new FormData(form);
        const incidences = Array.from(form.querySelectorAll(".participant-editor")).map(fieldset => ({ id: fieldset.dataset.participantId, record_id: fieldset.querySelector('[name="participant_record"]').value, role: fieldset.querySelector('[name="participant_role"]').value.trim(), reference_scope: fieldset.querySelector('[name="participant_scope"]').value, orientation: fieldset.querySelector('[name="participant_orientation"]').value }));
        if (!incidences.length) throw new Error("List at least one participant, or cancel this draft.");
        const data = Object.fromEntries(["predicate", "predicate_definition", "participant_limitations", "context", "identity_criterion", "temporal_scope"].map(name => [name, String(values.get(name) || "").trim()]));
        data.participants = incidences; data.participants_complete = values.get("participants_complete") === "complete";
        const module = { version: "1", required: priorModule?.required || false, data };
        if (record) return [{ op: "module.set", record_id: relationId, module_id: "gsp.relation", module }];
        return [{ op: "record.create", record: { id: relationId, title: String(values.get("title")), content: String(values.get("content")), record_type: "Relation", record_roles: ["Relation"], epistemic_mode: String(values.get("epistemic_mode")), modality: "unknown", status: "unreviewed", related_records: [], modules: { "gsp.relation": module } } }];
      }, saved: record ? "Relation structure revised." : "Relation and all participant references preserved together." });
    }
    async function migrationPreview() {
      try {
        const preview = await api(`${base}/migration`);
        if (!preview.needed) { await loadSnapshot(); return; }
        mutationDialog({ title: "Bring this project into the graph workspace.", description: "The upgrade adds a new revision. Original commits and record identifiers remain intact.", category: "migration", body: `<dl class="migration-summary"><dt>Format</dt><dd>${esc(preview.from_version)} → ${esc(preview.to_version)}</dd><dt>Records retained</dt><dd>${esc(preview.record_count)}</dd><dt>Unstructured relation accounts</dt><dd>${esc(preview.unstructured_relations)}</dd><dt>Neutral references</dt><dd>${esc(preview.neutral_references)}</dd></dl><p class="notice">No predicates, participant roles or evidence are invented. Earlier untyped references stay neutral.</p>${(preview.limitations || []).map(note => `<p class="small muted">${esc(note)}</p>`).join("")}`, prepare: () => [{ op: "project.migrate" }], saved: "Project upgraded in a new revision. Earlier records remain preserved." });
      } catch (error) { toast(errorText(error)); }
    }
    function onClick(event) {
      const target = event.target.closest("button, a"); if (!target || target.disabled) return;
      if (target.dataset.graphView) { changeView(target.dataset.graphView); return; }
      if (target.dataset.selectRecord) { selectNode(target.dataset.selectRecord); return; }
      if (target.dataset.inspectorTab) { tab = target.dataset.inspectorTab; renderInspector(); root.querySelector(`[data-inspector-tab="${tab}"]`)?.focus({ preventScroll: true }); return; }
      if (target.dataset.projectRevision) { void loadSnapshot(target.dataset.projectRevision); return; }
      const action = target.dataset.graphAction;
      if (action === "connect") { connecting = true; picked = selected ? [selected] : []; renderConnectBar(); }
      else if (action === "cancel-connect") { connecting = false; picked = []; renderConnectBar(); }
      else if (action === "review-connection" || action === "relation-form") relationDialog(action === "review-connection" ? picked : selected ? [selected] : []);
      else if (action === "deselect") { selected = null; state.graphSelection = null; cy?.nodes().unselect(); renderInspector(); root.querySelector("#record-selector")?.focus({ preventScroll: true }); }
      else if (action === "edit-selected") editRecord(currentRecord());
      else if (action === "create-connected") editRecord(null, { connectTo: selected });
      else if (action === "full-record") { state.graphSelection = selected; context.openFullRecord?.(selected, state.revision || state.head); }
      else if (action === "edit-relation" || action === "structure-relation") relationDialog([], currentRecord());
      else if (action === "temporal-order") orderDialog();
      else if (action === "edit-order") orderDialog(currentRecord());
      else if (action === "edit-temporal") temporalDialog();
      else if (action === "enable-files") enableModule("files");
      else if (action === "enable-notes") enableModule("notes");
      else if (action === "edit-notes") notesDialog();
      else if (action === "attach-file") attachmentDialog();
      else if (action === "replace-file") attachmentDialog(target.dataset.fileId);
      else if (action === "detach-file") detachFile(target.dataset.fileId);
      else if (action?.startsWith("remove-")) removeModule(action.slice(7));
      else if (action === "migrate-preview") void migrationPreview();
      else if (action === "current" || action === "retry") void loadSnapshot();
      else if (action === "fit") cy?.fit(cy.elements(":visible"), 45);
      else if (action === "zoom-in" || action === "zoom-out") { if (cy) cy.zoom({ level: cy.zoom() * (action === "zoom-in" ? 1.25 : .8), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }
      else if (action === "arrange" && cy) { cy.elements(":visible").layout({ name: "cose", animate: false, randomize: true, fit: true, padding: 45, nodeRepulsion: () => 9000, idealEdgeLength: () => 130 }).run(); rememberPositions(); }
    }
    renderShell(); updateHeader(); renderInspector();
    resizeObserver.observe(root.querySelector(".graph-stage"));
    void loadSnapshot(state.revision || state.head, { accepted: !state.revision });
    return {
      destroy() { alive = false; ++requestSequence; ++inspectorSequence; resizeObserver.disconnect(); spacetime?.destroy(); root.removeEventListener("click", onClick); cy?.destroy(); cy = null; },
      refresh(head, selection = selected) { return loadSnapshot(head, { accepted: true, select: selection }); },
      selectedRecord: currentRecord,
      placeRecord(id, position) { const stored = positions(); stored[id] = position; try { localStorage.setItem(localKey, JSON.stringify(stored)); } catch (_) { /* The record does not depend on layout storage. */ } },
      isReadOnly: readOnly
    };
  }
  return { mount, PROTOCOL };
})();
