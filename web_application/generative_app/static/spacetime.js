"use strict";

/* Event order and a selected down-set are projections, never recording chronology. */
window.GSPSpaceTime = (() => {
  function mount(root, context) {
    const { api, base, esc, icon, errorText, selectRecord, isReadOnly } = context;
    let alive = true, visible = false, sequence = 0, head = null, records = [], data = null;
    let eventGraph = null, topologyGraph = null, busy = false, lastAfter;
    const title = id => records.find(record => record.id === id)?.title || id;
    const recordButton = (id, label = title(id)) => `<button class="button-link" type="button" data-st-record="${esc(id)}">${esc(label)}</button>`;
    const human = value => String(value || "unknown").replaceAll("_", " ");
    const boundText = boundary => boundary?.kind === "event" ? title(boundary.event_id) : boundary?.kind === "unbounded" ? "Unbounded within this account" : "Unknown boundary";
    function clearGraphs() { eventGraph?.destroy(); topologyGraph?.destroy(); eventGraph = null; topologyGraph = null; }
    const observer = new ResizeObserver(() => {
      if (!visible) return;
      requestAnimationFrame(() => {
        if (!alive || !visible) return;
        for (const graph of [eventGraph, topologyGraph]) { graph?.resize(); if (graph?.elements().length) graph.fit(graph.elements(), 35); }
      });
    });
    observer.observe(root);
    async function load(after, focusId = null) {
      if (!head || !alive) return;
      const request = ++sequence, requestedHead = head;
      lastAfter = after === undefined ? undefined : [...after];
      busy = true;
      root.querySelectorAll("[data-st-cut], [data-st-action]").forEach(control => { control.disabled = true; });
      if (!data) root.innerHTML = '<p class="spacetime-loading" role="status">Reading event order and temporal boundaries…</p>';
      try {
        const result = await api(`${base}/spacetime?revision=${encodeURIComponent(requestedHead)}`, after === undefined ? {} : { method: "POST", body: { after } });
        if (!alive || request !== sequence || head !== requestedHead) return;
        if (result.head !== requestedHead) throw new Error("The temporal projection does not match this project revision. Reload the project before continuing.");
        data = result; busy = false; render();
        if (focusId) root.querySelector(`[data-st-cut="${CSS.escape(focusId)}"]`)?.focus({ preventScroll: true });
      } catch (error) {
        if (!alive || request !== sequence) return;
        busy = false;
        if (data) render();
        else root.innerHTML = "";
        root.insertAdjacentHTML("afterbegin", `<div class="error-box" role="alert">${esc(errorText(error))}<br><button class="button secondary small-button" type="button" data-st-action="retry">Try temporal view again</button></div>`);
      }
    }
    function render() {
      clearGraphs();
      const included = new Set(data.cut?.included || []), events = data.events || [], orders = data.orders || [];
      const extents = data.extents || [], statuses = data.presence || [];
      const groups = new Map((data.trajectories || []).map(group => [group.subject_record_id, [...group.record_ids]]));
      for (const extent of extents.filter(item => !item.subject_record_id)) {
        const members = groups.get(extent.record_id) || [];
        if (!members.includes(extent.record_id)) members.unshift(extent.record_id);
        groups.set(extent.record_id, members);
      }
      const trajectories = Array.from(groups, ([subject_record_id, record_ids]) => ({ subject_record_id, record_ids }));
      const frontier = data.cut?.frontier || [], unplaced = statuses.filter(item => ["unknown", "unscoped", "indeterminate"].includes(item.presence));
      root.innerHTML = `<header class="spacetime-heading"><div><span class="eyebrow">Time in the represented world</span><h2>Follow events. Read what changes.</h2><p>Event order comes from recorded precedence claims. Git revisions preserve when those claims were recorded.</p></div><button class="button secondary small-button" type="button" data-graph-action="temporal-order" ${isReadOnly() ? "disabled" : ""}>${icon("plus")}Order events</button></header>
        <section class="spacetime-section" aria-labelledby="event-order-title"><div class="spacetime-section-heading"><h3 id="event-order-title">Event order</h3><button class="button secondary small-button" type="button" data-st-action="fit-events">Fit events</button></div><p class="field-help">Read arrows as asserted “before.” Unconnected or incomparable events are not necessarily simultaneous. Only arrows and their paths assert order. Columns are layout layers, not simultaneity or a time scale.</p><div id="spacetime-event-canvas" class="spacetime-canvas" role="img" aria-label="Event precedence graph. Use the event list below for keyboard access."></div>${!events.length ? '<p class="notice">Create records with an Event role, then add an ordering account when their order is known. Recording dates and descriptive date text do not invent an order.</p>' : ""}
        <details class="spacetime-orders"><summary>${orders.length} recorded ordering ${orders.length === 1 ? "account" : "accounts"}</summary><ul>${orders.map(order => `<li>${recordButton(order.id, `${title(order.before)} → ${title(order.after)}`)}<span class="spacetime-badge">${esc(human(order.status))}${order.active ? " · applied" : " · not applied"}</span></li>`).join("") || '<li>No precedence claims recorded.</li>'}</ul></details></section>
        <details id="spacetime-diagnostics" ${!data.consistent ? "open" : ""}><summary>${(data.diagnostics || []).length} temporal projection notes${!data.consistent ? " ? cut unavailable" : ""}</summary>${!data.consistent ? '<div class="error-box"><strong>These temporal records cannot define a consistent cut.</strong><p>The records are preserved. Review the notes below for conflicting claims or unsupported temporal data; revise an account only when warranted.</p></div>' : ""}${(data.diagnostics || []).map(item => `<div class="spacetime-diagnostic"><p>${esc(item.message)}</p>${[...new Set([...(item.record_id ? [item.record_id] : []), ...(item.event_ids || []), ...(item.relation_ids || [])])].map(id => recordButton(id)).join(" · ")}</div>`).join("")}</details>
        <section class="spacetime-section" aria-labelledby="temporal-cut-title"><div class="spacetime-section-heading"><h3 id="temporal-cut-title">Choose an event boundary</h3><div class="row"><button class="button secondary small-button" type="button" data-st-action="before-all" ${!data.cut ? "disabled" : ""}>Before all</button><button class="button secondary small-button" type="button" data-st-action="after-all" ${!data.cut ? "disabled" : ""}>After all</button></div></div><p class="field-help">Mark events as passed. Their recorded predecessors are included automatically; clearing an event also clears its passed successors. This consistent cut is a chosen boundary, not proof of a shared clock instant.</p><div id="spacetime-cut-status" class="spacetime-cut-status" role="status">${data.cut ? `${included.size} of ${events.length} events passed · ${frontier.length} frontier ${frontier.length === 1 ? "event" : "events"}` : "Cut unavailable; review the temporal projection notes."}</div><div class="spacetime-events">${events.map(event => `<div class="spacetime-event-row"><label><input type="checkbox" data-st-cut="${esc(event.id)}" ${included.has(event.id) ? "checked" : ""} ${!data.cut ? "disabled" : ""}><span>${esc(event.title)}</span></label><button class="button-link" type="button" data-st-record="${esc(event.id)}" aria-label="Read ${esc(event.title)}">Read</button>${["contested", "withdrawn"].includes(event.status) || event.modality !== "realized" ? `<span class="spacetime-badge">${esc(["contested", "withdrawn"].includes(event.status) ? event.status : human(event.modality))}</span>` : ""}${event.occurred_at ? `<span class="spacetime-event-date">Described time: ${esc(event.occurred_at)}</span>` : ""}</div>`).join("")}</div>${frontier.length ? `<p class="spacetime-frontier">Boundary frontier: ${frontier.map(id => recordButton(id)).join(" · ")}</p>` : ""}</section>
        <section class="spacetime-section" aria-labelledby="cut-topology-title"><div class="spacetime-section-heading"><h3 id="cut-topology-title">Ontology graph at this boundary</h3><button class="button secondary small-button" type="button" data-st-action="fit-topology">Fit graph</button></div><p class="field-help">“Space” is the topology of records whose temporal extents include this cut. A record can describe an Entity, State, Event, Process, Relation or Property. Coordinates and location descriptions remain ordinary records.</p><p id="spacetime-topology-summary" class="spacetime-cut-status">${data.topology ? `${data.topology.nodes.length} records in this projection · ${unplaced.length} with unknown or unscoped presence` : "Topology unavailable for this temporal selection."}</p><div id="spacetime-topology-canvas" class="spacetime-canvas spacetime-topology" role="img" aria-label="Ontology subgraph at the chosen event boundary. The temporal coverage list provides keyboard access."></div>${data.topology && !data.topology.nodes.length ? '<p class="notice">No record has a temporal extent placing it in this selected subgraph. Select a record and use Time &amp; trajectory to describe its boundaries.</p>' : ""}<details class="spacetime-coverage" open><summary>Temporal coverage of this snapshot</summary><ul>${statuses.map(item => `<li data-st-presence="${esc(item.record_id)}">${recordButton(item.record_id)}<span class="spacetime-badge">${esc(human(item.presence))}</span></li>`).join("") || '<li>No records in this snapshot.</li>'}</ul></details></section>
        <section class="spacetime-section spacetime-trajectories" aria-labelledby="trajectory-title"><h3 id="trajectory-title">Record trajectories</h3><p class="field-help">Start boundaries are inclusive; end boundaries are exclusive. Grouping by a subject connects descriptions without establishing identity or resolving competing States.</p>${trajectories.map(trajectory => `<div class="spacetime-trajectory"><h4>${recordButton(trajectory.subject_record_id)}</h4>${trajectory.record_ids.map(id => { const extent = extents.find(item => item.record_id === id); return `<div class="spacetime-trajectory-row">${recordButton(id)}<span>${esc(boundText(extent?.start))} <span aria-label="until">→</span> ${esc(boundText(extent?.end))}</span><span class="spacetime-badge">${esc(human(extent?.presence || statuses.find(item => item.record_id === id)?.presence))}</span></div>`; }).join("")}</div>`).join("") || '<p class="notice">Temporal extents and optional subject groupings will appear here as they are recorded.</p>'}</section><footer class="spacetime-footer">${(data.limitations || []).map(item => `<p>${esc(typeof item === "string" ? item : item.message || JSON.stringify(item))}</p>`).join("")}<p>Projection of preserved revision <span class="mono">${esc(head.slice(0, 10))}</span>. Changing this view does not save a project revision.</p></footer>`;
      drawEvents(events, orders, included); drawTopology(data.topology);
    }
    function makeGraph(container, elements, styles, layout = { name: "preset" }) {
      if (!window.cytoscape) { container.innerHTML = '<p class="notice">The canvas renderer is unavailable. All records remain accessible in the lists.</p>'; return null; }
      const graph = window.cytoscape({ container, elements, layout, minZoom: .12, maxZoom: 2.5, wheelSensitivity: .18, userPanningEnabled: true, autoungrabify: true, style: [
        { selector: "node", style: { "shape": "round-rectangle", "width": 125, "height": 48, "background-color": "#edf2e7", "border-width": 1.2, "border-color": "#9bb38e", "label": "data(label)", "color": "#304d3b", "font-size": 11, "font-family": "Inter, Segoe UI, sans-serif", "text-valign": "center", "text-wrap": "ellipsis", "text-max-width": 108 } },
        { selector: "edge", style: { "width": 1.5, "line-color": "#95aa86", "target-arrow-color": "#95aa86", "curve-style": "bezier", "target-arrow-shape": "triangle", "label": "data(label)", "font-size": 9, "color": "#65765c", "text-background-color": "#fafbf6", "text-background-opacity": 1, "text-background-padding": 3, "text-rotation": "autorotate" } },
        { selector: "node:selected", style: { "border-width": 3, "border-color": "#214e40" } }, ...styles
      ] });
      graph.on("tap", "node", event => selectRecord(event.target.id()));
      graph.on("tap", "edge", event => { const id = event.target.data("record_id"); if (id) selectRecord(id); });
      if (elements.length) graph.fit(graph.elements(), 35);
      return graph;
    }
    function drawEvents(events, orders, included) {
      const ranks = new Map();
      const nodes = events.map((event, index) => {
        const rank = event.rank === null ? index % 4 : event.rank;
        const row = ranks.get(rank) || 0; ranks.set(rank, row + 1);
        return { data: { id: event.id, label: event.title, passed: included.has(event.id) ? 1 : 0 }, position: { x: 95 + rank * 190, y: 60 + row * 100 } };
      });
      eventGraph = makeGraph(root.querySelector("#spacetime-event-canvas"), [...nodes, ...orders.filter(order => order.active).map(order => ({ data: { id: `order-${order.id}`, record_id: order.id, source: order.before, target: order.after, label: order.status === "contested" ? "before · contested" : "before", contested: order.status === "contested" ? 1 : 0 } }))], [
        { selector: "node[passed = 1]", style: { "background-color": "#d4e4c6", "border-color": "#648454", "border-width": 2 } },
        { selector: "edge[contested = 1]", style: { "line-style": "dashed", "line-color": "#a17b38", "target-arrow-color": "#a17b38" } }
      ]);
    }
    function drawTopology(topology) {
      const nodes = topology?.nodes || [], edges = topology?.edges || [];
      // CoSE component packing can overlap wide, isolated nodes. A grid keeps
      // an edgeless selection distinct without suggesting additional relations.
      const gridLayout = { name: "grid", avoidOverlap: true, spacingFactor: 1.35, fit: true, padding: 35 };
      const layout = edges.length
        ? { name: "cose", animate: false, randomize: false, fit: true, padding: 35, nodeRepulsion: () => 7000, idealEdgeLength: () => 120 }
        : gridLayout;
      const columns = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
      topologyGraph = makeGraph(root.querySelector("#spacetime-topology-canvas"), [
        ...nodes.map((node, index) => ({ data: { ...node, label: node.label || title(node.id), relation: (node.record_roles || [node.record_type]).includes("Relation") ? 1 : 0 }, position: { x: 95 + index % columns * 190, y: 60 + Math.floor(index / columns) * 130 } })),
        ...edges.map((edge, index) => ({ data: { ...edge, id: edge.id || `topology-edge-${index}`, record_id: edge.relation_id, label: edge.role || "", neutral: ["related", "neutral_reference", "reference"].includes(edge.kind) ? 1 : 0 } }))
      ], [
        { selector: "node[relation = 1]", style: { "shape": "diamond", "height": 75, "background-color": "#f1e9d6", "border-color": "#bda46e", "text-max-width": 80 } },
        { selector: 'edge[orientation = "undirected"], edge[neutral = 1]', style: { "target-arrow-shape": "none" } },
        { selector: "edge[neutral = 1]", style: { "line-style": "dashed", "label": "" } }
      ], layout);
      if (topologyGraph && edges.length) {
        const boxes = topologyGraph.nodes().map(node => node.boundingBox());
        const overlap = boxes.some((left, index) => boxes.slice(index + 1).some(right =>
          left.x1 < right.x2 && right.x1 < left.x2 && left.y1 < right.y2 && right.y1 < left.y2));
        // Preserve the graph's edges, but replace a colliding force layout.
        if (overlap) topologyGraph.layout(gridLayout).run();
      }
    }
    root.addEventListener("change", onChange);
    root.addEventListener("click", onClick);
    function onChange(event) {
      const input = event.target.closest("[data-st-cut]");
      if (!input || busy || !data?.cut) return;
      const id = input.dataset.stCut, passed = new Set(data.cut.included);
      if (input.checked) passed.add(id);
      else {
        const remove = [id];
        while (remove.length) {
          const current = remove.pop();
          if (!passed.delete(current)) continue;
          remove.push(...(data.events.find(item => item.id === current)?.successors || []));
        }
      }
      void load([...passed], id);
    }
    function onClick(event) {
      const target = event.target.closest("button"); if (!target || target.disabled) return;
      if (target.dataset.stRecord) { selectRecord(target.dataset.stRecord); return; }
      if (target.dataset.stAction === "before-all") void load([]);
      else if (target.dataset.stAction === "after-all") void load();
      else if (target.dataset.stAction === "retry") void load(lastAfter);
      else if (target.dataset.stAction === "fit-events") eventGraph?.fit(eventGraph.elements(), 35);
      else if (target.dataset.stAction === "fit-topology") topologyGraph?.fit(topologyGraph.elements(), 35);
    }
    return {
      setSnapshot(snapshotHead, snapshotRecords) {
        if (head === snapshotHead && records === snapshotRecords) return;
        head = snapshotHead; records = snapshotRecords; data = null; busy = false; lastAfter = undefined; ++sequence; clearGraphs();
        root.innerHTML = ""; if (visible) void load();
      },
      show(shown) { visible = shown; if (shown && !data && !busy) void load(); else if (shown) { eventGraph?.resize(); topologyGraph?.resize(); } },
      destroy() { alive = false; ++sequence; observer.disconnect(); clearGraphs(); root.removeEventListener("change", onChange); root.removeEventListener("click", onClick); }
    };
  }
  return { mount };
})();
