"""
dag.py — Data-flow DAG construction.

Takes the parsed output (segments + matrix) and builds a directed graph where:
  - Each node is a statement event (matrix row) or a synthetic entry node
  - Each edge A -> B means: A writes a slot that B reads (B depends on A)

Synthetic entry nodes
─────────────────────
Parameters and constants have no writer row in the matrix — their values
arrive from outside (caller or literal). A synthetic "func_entry" node is
injected at the start of each function/root/struct scope and writes all
params + constants for that scope. This gives every downstream read a
traceable source node.

Edge kinds
──────────
  data_flow     — standard def-use: A produces a value B consumes
  phi_loop      — back-edge into a loop_entry phi (loop iteration)
  phi_branch    — branch_reconvergence phi merging branch writes

Entry point:
    build_dag(segments: list, matrix: dict) -> dict
    Returns {"nodes": [...], "edges": [...]}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_edge(edges: list, seen: set, from_id: int, to_id: int,
              slot: str, kind: str = "data_flow") -> None:
    """Append a directed edge to the accumulator list if not already present.

    Args:
        edges: Accumulator list of edge dicts.
        seen: Set of ``(from_id, to_id, slot)`` tuples already recorded.
        from_id: Source node ID.
        to_id: Destination node ID.
        slot: Scoped slot name carried by this edge.
        kind: Edge kind — one of ``"data_flow"``, ``"phi_loop"``, or
            ``"phi_branch"``.
    """
    key = (from_id, to_id, slot)
    if key not in seen:
        seen.add(key)
        edges.append({"from": from_id, "to": to_id, "slot": slot, "kind": kind})


def _make_entry_node(seg: dict, scope_path: str) -> dict:
    """Build a synthetic entry node for a function, root, or struct segment.

    The entry node writes all parameter and constant slots for the scope so
    that every downstream read in the DAG has a traceable source.

    Args:
        seg: The segment dict for which to create an entry node.
        scope_path: The dot-separated scope path string for this segment.

    Returns:
        A node dict with ``kind``, ``seg_id``, ``scope_path``, ``raw``,
        ``reads``, ``writes``, ``decls``, and ``note`` fields.
    """
    writes = (
        [m["scoped_name"] for m in seg.get("memory", []) if m.get("param")]
        + [c["scoped_name"] for c in seg.get("constants", [])]
    )
    seg_type = seg.get("type", "function")
    kind_map = {"root": "file_entry", "struct": "struct_def"}
    entry_kind = kind_map.get(seg_type, "func_entry")
    return {
        "id":         None,  # assigned after insertion
        "kind":       entry_kind,
        "seg_id":     seg["id"],
        "scope_path": scope_path,
        "raw":        f"entry({scope_path})",
        "reads":      [],
        "writes":     writes,
        "decls":      list(writes),
        "note":       "synthetic",
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_dag(segments: list, matrix: dict) -> dict:
    """Build the data-flow DAG from the parsed segments and dependency matrix.

    Steps:
        1. Convert matrix rows to initial node list.
        2. Inject synthetic entry nodes for every function/root/struct scope.
        3. Build SSA-style def-use edges by scanning nodes in order.
        4. Add back-edges from the last loop-body write to each loop-entry phi.

    Args:
        segments: List of segment dicts from ``parse_c_file``.
        matrix: Dict with ``"slots"`` and ``"rows"`` keys from ``build_matrix``.

    Returns:
        A dict with ``"nodes"`` (list of node dicts) and ``"edges"`` (list
        of edge dicts).  Each node has ``id``, ``kind``, ``seg_id``,
        ``scope_path``, ``raw``, ``reads``, ``writes``, ``decls``, and
        ``note``.  Each edge has ``from``, ``to``, ``slot``, and ``kind``.
    """
    rows    = matrix["rows"]
    seg_map = {seg["id"]: seg for seg in segments}

    # ── Step 1: Build initial node list from matrix rows ──────────────────
    raw_nodes = []
    for row in rows:
        node = {
            "id":         None,
            "kind":       row["kind"],
            "seg_id":     row["seg_id"],
            "scope_path": row["scope_path"],
            "raw":        row["raw"],
            "reads":      list(row["reads"]),
            "writes":     list(row["writes"]),
            "decls":      list(row["decls"]),
            "note":       row["note"],
        }
        if "expr" in row:
            node["expr"] = row["expr"]
        raw_nodes.append(node)

    # ── Step 2: Inject synthetic entry nodes ──────────────────────────────
    # For each function/root/struct segment, insert a func_entry node
    # just before the first row that belongs to that segment.
    entry_seg_types = {"function", "root", "struct"}
    entry_segs = [seg for seg in segments if seg["type"] in entry_seg_types]

    # Find first row index for each seg_id
    first_row_for_seg = {}
    for i, node in enumerate(raw_nodes):
        sid = node["seg_id"]
        if sid is not None and sid not in first_row_for_seg:
            first_row_for_seg[sid] = i

    # Build and apply insertions in reverse order to preserve indices
    insertions = []
    for seg in entry_segs:
        insert_at = first_row_for_seg.get(seg["id"], len(raw_nodes))
        entry_node = _make_entry_node(seg, seg["scope_path"])
        insertions.append((insert_at, entry_node))
    insertions.sort(key=lambda x: x[0], reverse=True)
    for insert_at, entry_node in insertions:
        raw_nodes.insert(insert_at, entry_node)

    # Assign stable sequential ids
    nodes = []
    for i, node in enumerate(raw_nodes):
        node["id"] = i
        nodes.append(node)

    # ── Step 3: Build edges (SSA-style def-use scan) ──────────────────────
    edges = []
    seen  = set()

    # last_write[slot] = node_id of the most recent write to that slot
    last_write: dict = {}

    # scope_last_write[(scope_path, slot)] = node_id of last write to slot
    # inside a particular scope — used for branch_reconvergence phis
    scope_last_write: dict = {}

    for node in nodes:
        nid  = node["id"]
        note = node["note"]

        if note == "branch_reconvergence":
            # reads are scope_path strings, not slot names
            slot = node["writes"][0]
            for src_scope in node["reads"]:
                src_id = scope_last_write.get((src_scope, slot))
                if src_id is not None:
                    _add_edge(edges, seen, src_id, nid, slot, "phi_branch")
        else:
            for slot in node["reads"]:
                src_id = last_write.get(slot)
                if src_id is not None:
                    edge_kind = "phi_loop" if note == "loop_entry" else "data_flow"
                    _add_edge(edges, seen, src_id, nid, slot, edge_kind)

        # Update write tracking after resolving reads
        for slot in node["writes"]:
            last_write[slot] = nid
            if node["scope_path"] is not None:
                scope_last_write[(node["scope_path"], slot)] = nid

    # ── Step 4: Back-edges for loop_entry phis ────────────────────────────
    # Each loop_entry phi also needs an edge from the LAST write to that
    # slot inside the loop body (the back-edge from iteration N to phi
    # at the start of iteration N+1).
    for phi in nodes:
        if phi["note"] != "loop_entry":
            continue
        phi_scope = phi["scope_path"]
        for slot in phi["writes"]:
            last_in_loop = None
            for n in nodes:
                if n["id"] <= phi["id"]:
                    continue
                if n["scope_path"] is None:
                    continue
                if not n["scope_path"].startswith(phi_scope):
                    continue
                if slot in n["writes"]:
                    last_in_loop = n["id"]
            if last_in_loop is not None:
                _add_edge(edges, seen, last_in_loop, phi["id"],
                          slot, "phi_loop")

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def visualize_dag(dag: dict, output_path: str = "dag.png",
                  scope_filter: str = None,
                  figsize: tuple = (24, 16)) -> None:
    """Render the DAG as a PNG image using ``networkx`` and ``matplotlib``.

    Args:
        dag: Output of :func:`build_dag` — a dict with ``"nodes"`` and
            ``"edges"`` keys.
        output_path: File path for the output PNG. Defaults to ``"dag.png"``.
        scope_filter: If provided, only nodes whose ``scope_path`` starts with
            this prefix are shown (e.g. ``"root.dot_product"``). The synthetic
            entry node for the exact matching scope is always included.
        figsize: Matplotlib figure size in inches as ``(width, height)``.

    Raises:
        ImportError: If ``networkx`` or ``matplotlib`` are not installed.
    """
    try:
        import networkx as nx
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError as e:
        raise ImportError(f"visualize_dag requires networkx and matplotlib: {e}")

    nodes = dag["nodes"]
    edges = dag["edges"]

    # ── Filter nodes ─────────────────────────────────────────────────────────
    if scope_filter:
        visible_ids = set()
        for n in nodes:
            sp = n["scope_path"] or ""
            if sp.startswith(scope_filter):
                visible_ids.add(n["id"])
            # Always include the entry node for the exact scope
            if n["note"] == "synthetic" and sp == scope_filter:
                visible_ids.add(n["id"])
        nodes = [n for n in nodes if n["id"] in visible_ids]
        edges = [e for e in edges
                 if e["from"] in visible_ids and e["to"] in visible_ids]

    # ── Build networkx graph ──────────────────────────────────────────────────
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["id"], **n)
    for e in edges:
        G.add_edge(e["from"], e["to"], slot=e["slot"], kind=e["kind"])

    # ── Layout ───────────────────────────────────────────────────────────────
    # Use dot-style hierarchical layout if pygraphviz/pydot available,
    # otherwise fall back to Sugiyama-style via multipartite on depth.
    try:
        pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
    except Exception:
        try:
            pos = nx.nx_pydot.graphviz_layout(G, prog="dot")
        except Exception:
            # Manual topological-depth layout
            try:
                order = list(nx.topological_sort(G))
            except nx.NetworkXUnfeasible:
                # Graph has cycles (back-edges) — break them for layout
                G_acyclic = nx.DiGraph()
                G_acyclic.add_nodes_from(G.nodes())
                for u, v, d in G.edges(data=True):
                    if d.get("kind") not in ("phi_loop",):
                        G_acyclic.add_edge(u, v)
                try:
                    order = list(nx.topological_sort(G_acyclic))
                except Exception:
                    order = [n["id"] for n in nodes]

            depth = {}
            for nid in order:
                preds = list(G.predecessors(nid))
                depth[nid] = 1 + max((depth.get(p, 0) for p in preds), default=0)

            # Group by depth, spread horizontally
            from collections import defaultdict
            layers = defaultdict(list)
            for nid, d in depth.items():
                layers[d].append(nid)

            pos = {}
            for d, layer_nodes in layers.items():
                n_nodes = len(layer_nodes)
                for i, nid in enumerate(layer_nodes):
                    x = (i - (n_nodes - 1) / 2) * 2.5
                    y = -d * 2.0
                    pos[nid] = (x, y)

    # ── Visual style per node kind ────────────────────────────────────────────
    KIND_STYLE = {
        # kind          : (fill_color,  border_color, shape)
        "file_entry"    : ("#1a1a2e",   "#e94560",    "s"),   # dark navy / red
        "func_entry"    : ("#16213e",   "#0f3460",    "s"),   # dark blue
        "struct_def"    : ("#1a1a2e",   "#533483",    "s"),   # purple border
        "func_decl"     : ("#0d3b66",   "#1b6ca8",    "o"),
        "decl"          : ("#1b4332",   "#40916c",    "o"),   # green
        "assign"        : ("#7f4f24",   "#e9c46a",    "o"),   # amber
        "branch"        : ("#3d405b",   "#81b29a",    "D"),   # diamond
        "loop_head"     : ("#560bad",   "#b5179e",    "D"),   # purple/pink
        "phi"           : ("#212529",   "#adb5bd",    "^"),   # grey triangle
        "control"       : ("#370617",   "#e85d04",    "v"),   # orange/red
        "call"          : ("#03071e",   "#ffba08",    "p"),   # gold pentagon
        "expr"          : ("#2d3436",   "#636e72",    "o"),
    }
    DEFAULT_STYLE = ("#2d3436", "#636e72", "o")

    # ── Edge colors per kind ──────────────────────────────────────────────────
    EDGE_COLOR = {
        "data_flow"   : "#4cc9f0",
        "phi_loop"    : "#f72585",
        "phi_branch"  : "#7209b7",
    }

    # ── Draw ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.axis("off")

    # Draw edges grouped by kind (so colors are applied cleanly)
    for kind, color in EDGE_COLOR.items():
        kind_edges = [(e["from"], e["to"])
                      for e in (dag["edges"] if not scope_filter else edges)
                      if e["kind"] == kind
                      and e["from"] in pos and e["to"] in pos]
        if kind_edges:
            nx.draw_networkx_edges(
                G, pos,
                edgelist=kind_edges,
                edge_color=color,
                arrows=True,
                arrowsize=15,
                arrowstyle="-|>",
                width=1.5 if kind == "data_flow" else 1.0,
                style="solid" if kind == "data_flow" else "dashed",
                connectionstyle="arc3,rad=0.08",
                ax=ax,
                alpha=0.75,
            )

    # Draw nodes grouped by kind
    for kind, (fill, border, marker) in KIND_STYLE.items():
        kind_nodes = [n["id"] for n in nodes if n["kind"] == kind and n["id"] in pos]
        if kind_nodes:
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=kind_nodes,
                node_color=fill,
                edgecolors=border,
                node_size=900,
                node_shape=marker,
                linewidths=2.0,
                ax=ax,
            )

    # Draw any nodes not in KIND_STYLE
    known_kinds = set(KIND_STYLE)
    other_nodes = [n["id"] for n in nodes
                   if n["kind"] not in known_kinds and n["id"] in pos]
    if other_nodes:
        fill, border, marker = DEFAULT_STYLE
        nx.draw_networkx_nodes(G, pos, nodelist=other_nodes,
                               node_color=fill, edgecolors=border,
                               node_size=900, linewidths=2.0, ax=ax)

    # Labels: show node id + short raw snippet
    labels = {}
    for n in nodes:
        if n["id"] not in pos:
            continue
        raw = n["raw"]
        # Shorten for readability
        if len(raw) > 22:
            raw = raw[:20] + "…"
        labels[n["id"]] = f"{n['id']}\n{raw}"

    nx.draw_networkx_labels(
        G, pos, labels=labels,
        font_size=6,
        font_color="#e0e0e0",
        font_family="monospace",
        ax=ax,
    )

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_nodes = [
        mpatches.Patch(facecolor=fill, edgecolor=border, label=kind, linewidth=1.5)
        for kind, (fill, border, _) in KIND_STYLE.items()
    ]
    legend_edges = [
        mpatches.Patch(color=c, label=k)
        for k, c in EDGE_COLOR.items()
    ]
    ax.legend(
        handles=legend_nodes + legend_edges,
        loc="upper left",
        fontsize=7,
        framealpha=0.3,
        facecolor="#161b22",
        edgecolor="#30363d",
        labelcolor="#e0e0e0",
        ncol=2,
    )

    title = f"Data-flow DAG — {scope_filter or 'all scopes'}"
    ax.set_title(title, color="#e0e0e0", fontsize=11, pad=12, fontfamily="monospace")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"DAG written to {output_path}")