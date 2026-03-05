"""CLI command implementations for the CDUP ``parse``, ``detect``, and ``run`` subcommands.

Each ``cmd_*`` function is called directly from ``main.py`` after argument
parsing and is responsible for the full lifecycle of its subcommand:
file collection, parsing, detection or execution, and output writing.
"""

import json
import csv
from ..detect import detect_clones, detect_type3, detect_type4
from .utils import _collect_c_files, _parse_file, _merge_parsed_jsons

def _parse_files(filepaths: list, include_comments: bool,
               include_includes: bool, include_macros: bool) -> tuple:
    """Parse a list of source files into IR JSON strings.

    Args:
        filepaths: List of absolute or relative file paths to parse.
        include_comments: Whether to include comment statements.
        include_includes: Whether to include ``#include`` directives.
        include_macros: Whether to include macro statements.

    Returns:
        A ``(parsed_list, skipped_list)`` tuple where ``parsed_list`` is a
        list of IR JSON strings and ``skipped_list`` is a list of file paths
        that failed to parse.
    """
    results = [_parse_file(fp, include_comments, include_includes, include_macros) for fp in filepaths]
    parsed_list = [r for r, _ in results if r is not None]
    skipped_list = [s for _, s in results if s is not None]
    return parsed_list, skipped_list

def _build_parsed_str(parsed_list: list, skipped_list: list) -> str:
    """Merge one or more per-file IR JSON strings into a single combined document.

    If only one file was parsed, skipped-file metadata is patched in directly
    rather than going through the full merge path.

    Args:
        parsed_list: List of per-file IR JSON strings.
        skipped_list: List of file paths that could not be parsed.

    Returns:
        A single merged IR JSON string.
    """
    if len(parsed_list) == 1:
        data = json.loads(parsed_list[0])
        data["meta"]["skipped_files"] = skipped_list
        data["meta"]["total_skipped_files"] = len(skipped_list)
        return json.dumps(data, indent=2)
    return _merge_parsed_jsons(parsed_list, skipped_list)

def cmd_parse(args) -> None:
    """Execute the ``parse`` subcommand.

    Collects source files from ``args.src``, parses them into IR JSON, and
    writes the result to a file or stdout.  Optionally exports the dependency
    matrix as CSV, the DAG as a DOT file, or the DAG as a 3-D HTML viewer.

    Args:
        args: Parsed ``argparse.Namespace`` from the ``parse`` subparser.
    """
    # Recursively get all the files from the passed in directory
    c_files = _collect_c_files(args.src)
    parsed_list, skipped_list = _parse_files(
        c_files, args.include_comments, args.include_includes, args.include_macros
    )
    if not parsed_list:
        print("Error: No files could be parsed successfully.")
        exit(1)

    # Get the parsed JSON
    result = _build_parsed_str(parsed_list, skipped_list)

    if getattr(args, "export_matrix_csv", None):
        data = json.loads(result)
        matrix = data.get("matrix", {})
        columns = matrix.get("slots", [])
        rows = matrix.get("rows", [])
        
        with open(args.export_matrix_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            header = ["seg_id", "scope_path", "kind", "raw"] + columns
            writer.writerow(header)
            
            for r in rows:
                row_data = [r.get("seg_id", ""), r.get("scope_path", ""), r.get("kind", ""), r.get("raw", "")]
                reads = set(r.get("reads", []))
                writes = set(r.get("writes", []))
                decls = set(r.get("decls", []))
                
                for col in columns:
                    cell = []
                    if col in decls: cell.append("D")
                    if col in writes: cell.append("W")
                    if col in reads: cell.append("R")
                    row_data.append("+".join(cell) if cell else "")
                writer.writerow(row_data)
        print(f"Matrix CSV exported to {args.export_matrix_csv}")

    if getattr(args, "export_dag_dot", None):
        data = json.loads(result)
        dag = data.get("dag", {})
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])
        
        # Group nodes by scope_path
        nodes_by_scope = {}
        for n in nodes:
            scope = n.get("scope_path", "root")
            if scope is None:
                scope = "root"
            nodes_by_scope.setdefault(scope, []).append(n)
        
        with open(args.export_dag_dot, 'w') as f:
            f.write("digraph G {\n")
            f.write('  rankdir=TB;\n')  # Switch back to Top-to-Bottom
            f.write('  nodesep=0.5;\n')
            f.write('  ranksep=0.8;\n')
            f.write('  splines=polyline;\n') # Use polyline to reduce overlapping curves
            f.write('  node [shape=box, style=filled, fillcolor="#f0f0f0", fontname="Courier", fontsize=10];\n')
            
            # Write subgraphs for each scope
            cluster_id = 0
            for scope, scope_nodes in nodes_by_scope.items():
                f.write(f'  subgraph cluster_{cluster_id} {{\n')
                f.write(f'    label="{scope}";\n')
                f.write('    style=filled;\n')
                f.write('    fillcolor="#e8e8e8";\n')
                f.write('    color=black;\n')
                
                # Sort nodes in this scope by ID (which is execution order)
                scope_nodes_sorted = sorted(scope_nodes, key=lambda x: x.get("id", 0))
                
                for i, n in enumerate(scope_nodes_sorted):
                    nid = n.get("id")
                    raw = n.get("raw", "").replace('"', '\\"').replace("\n", "\\n")
                    kind = n.get("kind", "")
                    label = f"{nid}: [{kind}]\\n{raw}"
                    f.write(f'    n{nid} [label="{label}"];\n')
                    
                    # Force sequential execution layout by adding invisible edges 
                    # from one statement to the next within the same block
                    if i > 0:
                        prev_nid = scope_nodes_sorted[i-1].get("id")
                        f.write(f'    n{prev_nid} -> n{nid} [style=invis, weight=10];\n')
                
                f.write('  }\n')
                cluster_id += 1
                
            # Write data dependency edges
            for e in edges:
                src = e.get("from")
                dst = e.get("to")
                slot = e.get("slot", "")
                ekind = e.get("kind", "")
                
                color = "#4cc9f0" if ekind == "data_flow" else ("#f72585" if ekind == "phi_loop" else "#7209b7")
                style = "solid" if ekind == "data_flow" else "dashed"
                
                label = slot
                if ekind != "data_flow":
                    label += f" ({ekind})"
                f.write(f'  n{src} -> n{dst} [label="{label}", color="{color}", fontcolor="{color}", style="{style}"];\n')
                
            f.write("}\n")
        print(f"DAG DOT exported to {args.export_dag_dot}")

    if getattr(args, "export_3d_html", None):
        data = json.loads(result)
        dag = data.get("dag", {})
        
        graph_data = {
            "nodes": [],
            "links": []
        }
        
        scope_colors = {}
        color_palette = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080', '#ffffff', '#000000']
        
        for n in dag.get("nodes", []):
            scope = n.get("scope_path", "root")
            if scope is None: scope = "root"
            if scope not in scope_colors:
                scope_colors[scope] = color_palette[len(scope_colors) % len(color_palette)]
                
            graph_data["nodes"].append({
                "id": n.get("id"),
                "name": f"[{n.get('kind')}] {n.get('raw')}",
                "raw": n.get("raw"),
                "kind": n.get("kind"),
                "group": scope,
                "color": scope_colors[scope],
                "reads": n.get("reads", []),
                "writes": n.get("writes", []),
                "decls": n.get("decls", [])
            })
            
        for e in dag.get("edges", []):
            ekind = e.get("kind", "")
            color = "#4cc9f0" if ekind == "data_flow" else ("#f72585" if ekind == "phi_loop" else "#7209b7")
            
            graph_data["links"].append({
                "source": e.get("from"),
                "target": e.get("to"),
                "name": e.get("slot"),
                "color": color
            })

        html_content = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CDUP 3D DAG Visualization</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/java.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/c.min.js"></script>
  <style> 
    body { margin: 0; background-color: #000011; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: white; overflow: hidden; } 
    #ui-panel { position: absolute; top: 10px; left: 10px; background: rgba(10, 10, 25, 0.9); padding: 15px; border-radius: 8px; max-height: 95vh; overflow-y: auto; width: 320px; z-index: 10; border: 1px solid #334; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    #code-panel { position: absolute; top: 10px; right: 10px; background: rgba(10, 10, 25, 0.9); padding: 15px; border-radius: 8px; max-height: 95vh; overflow-y: auto; width: 400px; z-index: 10; border: 1px solid #334; box-shadow: 0 4px 15px rgba(0,0,0,0.5); font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }
    
    h3 { margin-top: 0; margin-bottom: 10px; font-size: 14px; border-bottom: 1px solid #445; padding-bottom: 8px; color: #4cc9f0; text-transform: uppercase; letter-spacing: 1px; }
    .section-label { font-size: 11px; color: #889; margin-bottom: 5px; display: block; }
    
    /* Inspector Styles */
    #inspector { background: rgba(0,0,0,0.5); border: 1px solid #333; border-radius: 4px; padding: 10px; margin-bottom: 15px; font-size: 11px; }
    .ins-key { color: #911eb4; font-weight: bold; }
    .ins-val { color: #e8e8e8; }
    .ins-list { color: #4cc9f0; font-size: 10px; margin: 2px 0 0 10px; }

    /* Code Line Styles */
    .code-line { padding: 2px 5px; cursor: pointer; white-space: pre; border-radius: 2px; border-left: 3px solid transparent; }
    .code-line:hover { background: rgba(255,255,255,0.1); }
    .code-line.active { background: rgba(76, 201, 240, 0.3); border-left-color: #4cc9f0; }
    .code-line.synthetic { color: #666; font-style: italic; }

    /* Tree Styles */
    .tree-node { margin-left: 15px; border-left: 1px solid #333; padding-left: 5px; }
    .tree-row { display: flex; align-items: center; padding: 2px 0; font-size: 12px; }
    .tree-arrow { cursor: pointer; user-select: none; width: 15px; text-align: center; color: #666; transition: transform 0.2s; }
    .tree-arrow:hover { color: white; }
    .tree-arrow.collapsed { transform: rotate(-90deg); }
    .tree-label { cursor: pointer; flex-grow: 1; padding-left: 5px; }
    .tree-label:hover { background: rgba(255,255,255,0.05); text-decoration: underline; }
    .tree-content.collapsed { display: none; }
    .scope-leaf { color: #ccc; font-size: 11px; cursor: pointer; display: flex; align-items: center; padding: 2px 0; }
    .scope-leaf:hover { color: white; background: rgba(255,255,255,0.05); text-decoration: underline; }
    .color-dot { width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; display: inline-block; }

    select, button { width: 100%; padding: 6px; margin-bottom: 8px; background: #1a1a2e; color: white; border: 1px solid #334; border-radius: 4px; font-size: 11px; }
    button { cursor: pointer; transition: background 0.2s; font-weight: bold; }
    button:hover { background: #2a2a4e; }
    #btn-play { background: #1b4332; border-color: #2d6a4f; }
    #controls { margin-top: 15px; }
    .stepper { display: flex; justify-content: space-between; gap: 5px; }
    .stepper button { width: 33%; padding: 4px; }
  </style>
  <script src="https://unpkg.com/3d-force-graph"></script>
</head>
<body>
  <div id="ui-panel">
    <h3>Node Inspector</h3>
    <div id="inspector">Select a node to inspect...</div>

    <h3>Explorer</h3>
    <span class="section-label">Highlight Memory Slot:</span>
    <select id="slot-select"><option value="all">-- All Slots --</option></select>
    
    <div id="controls">
      <span class="section-label">Execution Stepper:</span>
      <div class="stepper">
        <button id="btn-prev">◀ Prev</button>
        <button id="btn-play">▶ Play</button>
        <button id="btn-next">Next ▶</button>
      </div>
      <button id="btn-reset-step" style="margin-top:5px; background:#432;">Reset View</button>
    </div>

    <h3 style="margin-top:20px;">Scopes</h3>
    <div id="scope-tree"></div>
  </div>

  <div id="code-panel">
    <h3>Code View</h3>
    <div id="code-content">Select a scope to view source...</div>
  </div>

  <div id="3d-graph"></div>

  <script>
    const gData = __GDATA__;
    const scopeColors = __COLORS__;
    
    const executionOrder = [...gData.nodes].sort((a, b) => a.id - b.id);
    let currentStepIdx = -1;
    let isPlaying = false;
    let playInterval;
    
    let visibleNodes = new Set(gData.nodes.map(n => n.id));
    let visibleLinks = new Set(gData.links);
    let isFiltering = false;
    let highlightNodes = new Set();
    let highlightLinks = new Set();

    // Inspector Logic
    function updateInspector(node) {
      const ins = document.getElementById('inspector');
      if (!node) { ins.innerHTML = "Select a node to inspect..."; return; }
      let html = `<div><span class="ins-key">ID:</span> <span class="ins-val">${node.id}</span></div>`;
      html += `<div><span class="ins-key">Kind:</span> <span class="ins-val">${node.kind}</span></div>`;
      html += `<div style="margin-top:5px; color:#e9c46a; font-weight:bold;">${node.raw}</div>`;
      
      if (node.reads && node.reads.length > 0) {
        html += `<div style="margin-top:8px;"><span class="ins-key">Reads:</span>`;
        node.reads.forEach(r => html += `<div class="ins-list">→ ${r}</div>`);
        html += `</div>`;
      }
      if (node.writes && node.writes.length > 0) {
        html += `<div style="margin-top:5px;"><span class="ins-key">Writes:</span>`;
        node.writes.forEach(w => html += `<div class="ins-list">← ${w}</div>`);
        html += `</div>`;
      }
      ins.innerHTML = html;
      
      // Also highlight the line in the code view
      const activeLine = document.querySelector(`.code-line[data-node-id="${node.id}"]`);
      if (activeLine) {
        document.querySelectorAll('.code-line').forEach(l => l.classList.remove('active'));
        activeLine.classList.add('active');
        activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    // Code Panel Logic
    function updateCodeView(scopePrefix) {
        const container = document.getElementById('code-content');
        container.innerHTML = "";
        
        const scopeNodes = gData.nodes
            .filter(n => n.group === scopePrefix || n.group.startsWith(scopePrefix + '.'))
            .sort((a, b) => a.id - b.id);
            
        scopeNodes.forEach(node => {
            const line = document.createElement('div');
            line.className = 'code-line';
            line.setAttribute('data-node-id', node.id);
            if (node.kind.includes('entry') || node.kind === 'phi') {
                line.classList.add('synthetic');
                line.innerText = node.raw;
            } else {
                try {
                    line.innerHTML = hljs.highlight(node.raw, {language: 'java'}).value;
                } catch(e) {
                    line.innerText = node.raw;
                }
            }
            line.onclick = () => {
                focusNode(node);
            };
            container.appendChild(line);
        });
    }

    function focusNode(node) {
        updateInspector(node);
        const distRatio = 1 + 150/Math.hypot(node.x, node.y, node.z);
        Graph.cameraPosition({ x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, node, 1500);
    }

    // Hierarchical Tree Logic
    function buildScopeTree() {
      const root = { children: {}, fullName: "" };
      Object.keys(scopeColors).forEach(scopePath => {
        const parts = scopePath.split('.');
        let current = root;
        parts.forEach((part, i) => {
          if (!current.children[part]) {
            current.children[part] = { 
              children: {}, 
              fullName: parts.slice(0, i+1).join('.') 
            };
          }
          current = current.children[part];
        });
      });
      return root;
    }

    function renderTree(node, container, name) {
      const hasChildren = Object.keys(node.children).length > 0;
      const nodeDiv = document.createElement('div');
      nodeDiv.className = 'tree-node';
      
      if (hasChildren) {
        const row = document.createElement('div');
        row.className = 'tree-row';
        const arrow = document.createElement('div');
        arrow.className = 'tree-arrow';
        arrow.innerText = '▾';
        const label = document.createElement('div');
        label.className = 'tree-label';
        label.innerText = name;
        const content = document.createElement('div');
        content.className = 'tree-content';
        
        arrow.onclick = (e) => {
          e.stopPropagation();
          arrow.classList.toggle('collapsed');
          content.classList.toggle('collapsed');
        };
        
        label.onclick = (e) => {
           e.stopPropagation();
           focusScopePrefix(node.fullName);
           updateCodeView(node.fullName);
        };
        
        Object.entries(node.children).forEach(([childName, childNode]) => {
          renderTree(childNode, content, childName);
        });
        
        row.appendChild(arrow);
        row.appendChild(label);
        nodeDiv.appendChild(row);
        nodeDiv.appendChild(content);
      } else {
        const leaf = document.createElement('div');
        leaf.className = 'scope-leaf';
        const color = scopeColors[node.fullName] || '#fff';
        leaf.innerHTML = `<span class="color-dot" style="background:${color}"></span>${name}`;
        leaf.onclick = (e) => {
            e.stopPropagation();
            focusScopePrefix(node.fullName);
            updateCodeView(node.fullName);
        };
        nodeDiv.appendChild(leaf);
      }
      container.appendChild(nodeDiv);
    }

    const scopeTreeData = buildScopeTree();
    const treeContainer = document.getElementById('scope-tree');
    Object.entries(scopeTreeData.children).forEach(([name, node]) => renderTree(node, treeContainer, name));

    // Initialize Graph
    const Graph = ForceGraph3D()
      (document.getElementById('3d-graph'))
        .graphData(gData)
        .nodeLabel('name')
        .nodeColor(node => node.color)
        .nodeVisibility(node => isFiltering ? visibleNodes.has(node.id) : true)
        .linkDirectionalArrowLength(3.5)
        .linkDirectionalArrowRelPos(1)
        .linkLabel(link => link.name)
        .linkColor(link => link.color)
        .linkVisibility(link => isFiltering ? visibleLinks.has(link) : true)
        .onNodeClick(node => {
          updateInspector(node);
          const distance = 100;
          const distRatio = 1 + distance/Math.hypot(node.x, node.y, node.z);
          Graph.cameraPosition({ x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, node, 2000);
        });

    // Memory Slot Filter
    const uniqueSlots = [...new Set(gData.links.map(l => l.name))].sort();
    const select = document.getElementById('slot-select');
    uniqueSlots.forEach(slot => {
      const opt = document.createElement('option');
      opt.value = slot;
      opt.innerText = slot;
      select.appendChild(opt);
    });

    select.addEventListener('change', (e) => {
      const slot = e.target.value;
      visibleNodes.clear(); visibleLinks.clear();
      if (slot === 'all') {
        isFiltering = false;
        Graph.nodeVisibility(true).linkVisibility(true);
        return;
      }
      gData.links.forEach(link => {
        if (link.name === slot) {
          const tgtId = link.target.id !== undefined ? link.target.id : link.target;
          const srcId = link.source.id !== undefined ? link.source.id : link.source;
          visibleLinks.add(link);
          visibleNodes.add(srcId);
          visibleNodes.add(tgtId);
        }
      });
      isFiltering = true;
      Graph.nodeVisibility(node => visibleNodes.has(node.id)).linkVisibility(link => visibleLinks.has(link));
    });

    function focusScopePrefix(scopePrefix) {
      visibleNodes.clear(); visibleLinks.clear();
      select.value = 'all';
      currentStepIdx = -1;
      let hasNodes = false;
      gData.nodes.forEach(node => {
        if (node.group === scopePrefix || node.group.startsWith(scopePrefix + '.')) {
          visibleNodes.add(node.id);
          hasNodes = true;
        }
      });
      gData.links.forEach(link => {
        const tgtId = link.target.id !== undefined ? link.target.id : link.target;
        const srcId = link.source.id !== undefined ? link.source.id : link.source;
        if (visibleNodes.has(srcId) && visibleNodes.has(tgtId)) visibleLinks.add(link);
      });
      isFiltering = true;
      Graph.nodeVisibility(node => visibleNodes.has(node.id)).linkVisibility(link => visibleLinks.has(link));
      if (hasNodes) setTimeout(() => { Graph.zoomToFit(1500, 50, node => visibleNodes.has(node.id)); }, 100);
    }

    // Stepper
    let currentScope = null;
    function stepTo(idx) {
      if (idx < 0 || idx >= executionOrder.length) return;
      currentStepIdx = idx;
      const node = executionOrder[currentStepIdx];
      
      if (currentScope !== node.group) {
        currentScope = node.group;
        updateCodeView(node.group);
      }
      
      updateInspector(node);
      isFiltering = false;
      highlightNodes.clear(); highlightLinks.clear();
      highlightNodes.add(node.id);
      gData.links.forEach(link => {
        const tgtId = link.target.id !== undefined ? link.target.id : link.target;
        const srcId = link.source.id !== undefined ? link.source.id : link.source;
        if (tgtId === node.id || srcId === node.id) {
          highlightLinks.add(link); highlightNodes.add(srcId); highlightNodes.add(tgtId);
        }
      });
      Graph.nodeVisibility(true).linkVisibility(true);
      Graph.nodeColor(n => highlightNodes.has(n.id) ? n.color : 'rgba(50,50,50,0.1)')
           .linkOpacity(l => highlightLinks.has(l) ? 0.8 : 0.05);
      if (node.x !== undefined && !isNaN(node.x)) {
         const distRatio = 1 + 150/Math.hypot(node.x, node.y, node.z);
         Graph.cameraPosition({ x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, node, 1000);
      }
    }

    document.getElementById('btn-next').onclick = () => stepTo(currentStepIdx + 1);
    document.getElementById('btn-prev').onclick = () => stepTo(Math.max(0, currentStepIdx - 1));
    document.getElementById('btn-play').onclick = () => {
      isPlaying = !isPlaying;
      document.getElementById('btn-play').innerText = isPlaying ? "⏸ Pause" : "▶ Play";
      if (isPlaying) { playInterval = setInterval(() => { if (currentStepIdx >= executionOrder.length - 1) { clearInterval(playInterval); isPlaying = false; } else stepTo(currentStepIdx + 1); }, 1000); }
      else clearInterval(playInterval);
    };

    document.getElementById('btn-reset-step').onclick = () => {
      clearInterval(playInterval); isPlaying = false; currentStepIdx = -1; isFiltering = false;
      highlightNodes.clear(); highlightLinks.clear();
      Graph.nodeVisibility(true).linkVisibility(true).nodeColor(n => n.color).linkOpacity(0.8);
      Graph.cameraPosition({x: 0, y: 0, z: 800}, {x:0, y:0, z:0}, 2000);
      document.getElementById('code-content').innerHTML = "Select a scope to view source...";
    };
  </script>
</body>
</html>'''

        html_content = html_content.replace("__GDATA__", json.dumps(graph_data)).replace("__COLORS__", json.dumps(scope_colors))

        with open(args.export_3d_html, 'w') as f:
            f.write(html_content)
        print(f"3D HTML exported to {args.export_3d_html}")

    # Either print to stdout or save to file
    if args.output:
        with open(args.output, 'w') as f:
            f.write(result)
        print(f"Parsed output written to {args.output}")
    else:
        # Only print full JSON to stdout if we aren't exporting specific files and haven't specified an output
        if not getattr(args, "export_matrix_csv", None) and not getattr(args, "export_dag_dot", None) and not getattr(args, "export_3d_html", None):
            print(result)

def _build_seg_stmt_to_dag_map(dag_nodes: list) -> dict:
    """Build a lookup from ``(seg_id, stmt_raw)`` to DAG node ID.

    Args:
        dag_nodes: List of node dicts from ``build_dag``.

    Returns:
        Dict mapping ``(seg_id, raw)`` tuples to node IDs.
    """
    """
    Build a mapping from (seg_id, stmt_index_within_seg) to DAG node IDs.
    DAG nodes derived from matrix rows appear in segment/statement order.
    Synthetic nodes (func_entry, phi, etc.) are excluded from stmt counting.
    """
    seg_stmt_counter = {}  # seg_id -> next stmt index
    mapping = {}           # (seg_id, stmt_idx) -> dag_node_id
    for node in dag_nodes:
        sid = node.get("seg_id")
        note = node.get("note", "")
        kind = node.get("kind", "")
        if sid is None:
            continue
        # Skip synthetic nodes — they don't correspond to source statements
        if note in ("synthetic", "loop_entry", "branch_reconvergence"):
            continue
        if kind in ("func_entry", "file_entry", "struct_def", "phi"):
            continue
        idx = seg_stmt_counter.get(sid, 0)
        mapping[(sid, idx)] = node["id"]
        seg_stmt_counter[sid] = idx + 1
    return mapping


def _export_clone_3d_html(filepath: str, parsed_data: dict,
                          clone_classes: list) -> None:
    """Write an interactive 3-D DAG + clone visualisation as a standalone HTML file.

    Args:
        filepath: Output path for the HTML file.
        parsed_data: The full parsed IR dict (with ``segments``, ``dag``, etc.).
        clone_classes: List of clone-class dicts as returned by detection.
    """
    """Generate the 3D DAG + clone visualization HTML."""
    from ..matrix import build_matrix
    from ..dag import build_dag

    segments = parsed_data["segments"]
    matrix = parsed_data.get("matrix") or build_matrix(segments)
    dag = parsed_data.get("dag") or build_dag(segments, matrix)

    # -- Build graph data (same as cmd_parse) --
    graph_data = {"nodes": [], "links": []}
    scope_colors = {}
    color_palette = [
        '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
        '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', '#008080', '#e6beff',
        '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1',
        '#000075', '#808080', '#ffffff', '#000000'
    ]

    for n in dag.get("nodes", []):
        scope = n.get("scope_path", "root")
        if scope is None:
            scope = "root"
        if scope not in scope_colors:
            scope_colors[scope] = color_palette[len(scope_colors) % len(color_palette)]
        graph_data["nodes"].append({
            "id": n.get("id"),
            "name": f"[{n.get('kind')}] {n.get('raw')}",
            "raw": n.get("raw"),
            "kind": n.get("kind"),
            "seg_id": n.get("seg_id"),
            "group": scope,
            "color": scope_colors[scope],
            "reads": n.get("reads", []),
            "writes": n.get("writes", []),
            "decls": n.get("decls", [])
        })

    for e in dag.get("edges", []):
        ekind = e.get("kind", "")
        color = "#4cc9f0" if ekind == "data_flow" else (
            "#f72585" if ekind == "phi_loop" else "#7209b7"
        )
        graph_data["links"].append({
            "source": e.get("from"),
            "target": e.get("to"),
            "name": e.get("slot"),
            "color": color
        })

    # -- Map clone occurrences to DAG node IDs --
    dag_nodes = dag.get("nodes", [])
    stmt_map = _build_seg_stmt_to_dag_map(dag_nodes)

    clone_data = []   # JSON-serialisable clone info for the frontend
    for cc in clone_classes:
        ct = cc.get("clone_type", "?")
        clone_entry = {
            "id": cc.get("id"),
            "type": ct,
            "similarity": cc.get("similarity"),
            "cross_language": cc.get("cross_language", False),
            "occurrences": []
        }
        for occ in cc.get("occurrences", []):
            sid = occ.get("seg_id")
            start = occ.get("start_stmt_idx", 0)
            end = occ.get("end_stmt_idx", start)
            dag_ids = []
            for i in range(start, end + 1):
                nid = stmt_map.get((sid, i))
                if nid is not None:
                    dag_ids.append(nid)
            clone_entry["occurrences"].append({
                "seg_id": sid,
                "start": start,
                "end": end,
                "dag_node_ids": dag_ids,
                "scope": occ.get("scope_path", ""),
                "file": occ.get("file", ""),
                "language": occ.get("language", ""),
            })
        clone_data.append(clone_entry)

    # -- Generate HTML --
    html = _CLONE_VIZ_HTML
    html = html.replace("__GDATA__", json.dumps(graph_data))
    html = html.replace("__COLORS__", json.dumps(scope_colors))
    html = html.replace("__CLONE_DATA__", json.dumps(clone_data))

    with open(filepath, 'w') as f:
        f.write(html)


_CLONE_VIZ_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CDUP Clone Visualization</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/java.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/c.min.js"></script>
  <style>
    body { margin: 0; background-color: #000011; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: white; overflow: hidden; }
    #ui-panel { position: absolute; top: 10px; left: 10px; background: rgba(10, 10, 25, 0.9); padding: 15px; border-radius: 8px; max-height: 95vh; overflow-y: auto; width: 340px; z-index: 10; border: 1px solid #334; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    #code-panel { position: absolute; top: 10px; right: 10px; background: rgba(10, 10, 25, 0.9); padding: 15px; border-radius: 8px; max-height: 95vh; overflow-y: auto; width: 400px; z-index: 10; border: 1px solid #334; box-shadow: 0 4px 15px rgba(0,0,0,0.5); font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; }
    h3 { margin-top: 0; margin-bottom: 10px; font-size: 14px; border-bottom: 1px solid #445; padding-bottom: 8px; color: #4cc9f0; text-transform: uppercase; letter-spacing: 1px; }
    .section-label { font-size: 11px; color: #889; margin-bottom: 5px; display: block; }
    #inspector { background: rgba(0,0,0,0.5); border: 1px solid #333; border-radius: 4px; padding: 10px; margin-bottom: 15px; font-size: 11px; }
    .ins-key { color: #911eb4; font-weight: bold; }
    .ins-val { color: #e8e8e8; }
    .ins-list { color: #4cc9f0; font-size: 10px; margin: 2px 0 0 10px; }
    .code-line { padding: 2px 5px; cursor: pointer; white-space: pre; border-radius: 2px; border-left: 3px solid transparent; }
    .code-line:hover { background: rgba(255,255,255,0.1); }
    .code-line.active { background: rgba(76, 201, 240, 0.3); border-left-color: #4cc9f0; }
    .code-line.synthetic { color: #666; font-style: italic; }
    .code-line.clone-hl { border-left-width: 3px; border-left-style: solid; }
    .tree-node { margin-left: 15px; border-left: 1px solid #333; padding-left: 5px; }
    .tree-row { display: flex; align-items: center; padding: 2px 0; font-size: 12px; }
    .tree-arrow { cursor: pointer; user-select: none; width: 15px; text-align: center; color: #666; transition: transform 0.2s; }
    .tree-arrow:hover { color: white; }
    .tree-arrow.collapsed { transform: rotate(-90deg); }
    .tree-label { cursor: pointer; flex-grow: 1; padding-left: 5px; }
    .tree-label:hover { background: rgba(255,255,255,0.05); text-decoration: underline; }
    .tree-content.collapsed { display: none; }
    .scope-leaf { color: #ccc; font-size: 11px; cursor: pointer; display: flex; align-items: center; padding: 2px 0; }
    .scope-leaf:hover { color: white; background: rgba(255,255,255,0.05); text-decoration: underline; }
    .color-dot { width: 7px; height: 7px; border-radius: 50%; margin-right: 8px; display: inline-block; }
    select, button { width: 100%; padding: 6px; margin-bottom: 8px; background: #1a1a2e; color: white; border: 1px solid #334; border-radius: 4px; font-size: 11px; }
    button { cursor: pointer; transition: background 0.2s; font-weight: bold; }
    button:hover { background: #2a2a4e; }
    #btn-clone-toggle { background: #1b2a44; border-color: #2d4a6f; font-size: 13px; padding: 8px; }
    #btn-clone-toggle.active { background: #2d6a4f; border-color: #40b87a; }
    .clone-legend { display: flex; gap: 10px; flex-wrap: wrap; margin: 8px 0; font-size: 11px; }
    .legend-item { display: flex; align-items: center; gap: 4px; }
    .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
    .clone-class-item { padding: 4px 8px; margin: 2px 0; border-radius: 4px; cursor: pointer; font-size: 11px; border-left: 3px solid transparent; }
    .clone-class-item:hover { background: rgba(255,255,255,0.1); }
    .clone-class-item.selected { background: rgba(255,255,255,0.15); }
    .clone-list { max-height: 250px; overflow-y: auto; }
    .cross-lang-badge { background: #f72585; color: white; font-size: 9px; padding: 1px 5px; border-radius: 3px; margin-left: 5px; }
    #controls { margin-top: 15px; }
    .stepper { display: flex; justify-content: space-between; gap: 5px; }
    .stepper button { width: 33%; padding: 4px; }
    .type-filter { display: flex; gap: 4px; margin: 6px 0; flex-wrap: wrap; }
    .type-btn { padding: 3px 10px; border-radius: 12px; cursor: pointer; font-size: 11px; font-weight: bold; border: 2px solid; opacity: 0.5; }
    .type-btn.on { opacity: 1; }
  </style>
  <script src="https://unpkg.com/3d-force-graph"></script>
</head>
<body>
  <div id="ui-panel">
    <h3>Node Inspector</h3>
    <div id="inspector">Select a node to inspect...</div>

    <h3>Clone View</h3>
    <button id="btn-clone-toggle">Show Clones</button>
    <div class="clone-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#4cc9f0"></div>Type I</div>
      <div class="legend-item"><div class="legend-dot" style="background:#3cb44b"></div>Type II</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f58231"></div>Type III</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f032e6"></div>Type IV</div>
    </div>
    <div class="type-filter" id="type-filter"></div>
    <div class="clone-list" id="clone-list"></div>

    <h3 style="margin-top: 15px;">Explorer</h3>
    <span class="section-label">Highlight Memory Slot:</span>
    <select id="slot-select"><option value="all">-- All Slots --</option></select>

    <div id="controls">
      <span class="section-label">Execution Stepper:</span>
      <div class="stepper">
        <button id="btn-prev">◀ Prev</button>
        <button id="btn-play">▶ Play</button>
        <button id="btn-next">Next ▶</button>
      </div>
      <button id="btn-reset-step" style="margin-top:5px; background:#432;">Reset View</button>
    </div>

    <h3 style="margin-top:20px;">Scopes</h3>
    <div id="scope-tree"></div>
  </div>

  <div id="code-panel">
    <h3>Code View</h3>
    <div id="code-content">Select a scope to view source...</div>
  </div>

  <div id="3d-graph"></div>

  <script>
    const gData = __GDATA__;
    const scopeColors = __COLORS__;
    const cloneData = __CLONE_DATA__;

    // Clone type color map
    const CLONE_COLORS = { "I": "#4cc9f0", "II": "#3cb44b", "III": "#f58231", "IV": "#f032e6" };
    const DIM_COLOR = "rgba(30,30,40,0.15)";
    const DIM_LINK = 0.03;

    // State
    const executionOrder = [...gData.nodes].sort((a, b) => a.id - b.id);
    let currentStepIdx = -1;
    let isPlaying = false;
    let playInterval;
    let visibleNodes = new Set(gData.nodes.map(n => n.id));
    let visibleLinks = new Set(gData.links);
    let isFiltering = false;
    let highlightNodes = new Set();
    let highlightLinks = new Set();

    // Clone state
    let cloneMode = false;
    let activeTypeFilters = new Set(["I", "II", "III", "IV"]);
    let selectedCloneId = null;

    // Pre-index: node_id -> list of clone entries touching it
    const nodeCloneMap = {};
    cloneData.forEach(cc => {
      cc.occurrences.forEach(occ => {
        occ.dag_node_ids.forEach(nid => {
          if (!nodeCloneMap[nid]) nodeCloneMap[nid] = [];
          nodeCloneMap[nid].push(cc);
        });
      });
    });

    // All node IDs involved in any clone
    const allCloneNodeIds = new Set(Object.keys(nodeCloneMap).map(Number));

    // Inspector
    function updateInspector(node) {
      const ins = document.getElementById('inspector');
      if (!node) { ins.innerHTML = "Select a node to inspect..."; return; }
      let html = '<div><span class="ins-key">ID:</span> <span class="ins-val">' + node.id + '</span></div>';
      html += '<div><span class="ins-key">Kind:</span> <span class="ins-val">' + node.kind + '</span></div>';
      html += '<div style="margin-top:5px; color:#e9c46a; font-weight:bold;">' + node.raw + '</div>';
      if (node.reads && node.reads.length > 0) {
        html += '<div style="margin-top:8px;"><span class="ins-key">Reads:</span>';
        node.reads.forEach(r => html += '<div class="ins-list">\u2192 ' + r + '</div>');
        html += '</div>';
      }
      if (node.writes && node.writes.length > 0) {
        html += '<div style="margin-top:5px;"><span class="ins-key">Writes:</span>';
        node.writes.forEach(w => html += '<div class="ins-list">\u2190 ' + w + '</div>');
        html += '</div>';
      }
      // Show clone info
      const clones = nodeCloneMap[node.id];
      if (clones && clones.length > 0) {
        html += '<div style="margin-top:8px;"><span class="ins-key">Clones:</span>';
        const seen = new Set();
        clones.forEach(cc => {
          if (seen.has(cc.id)) return; seen.add(cc.id);
          const color = CLONE_COLORS[cc.type] || '#fff';
          html += '<div class="ins-list" style="color:' + color + '">Type ' + cc.type + ' #' + cc.id;
          if (cc.similarity) html += ' (sim=' + cc.similarity + ')';
          if (cc.cross_language) html += ' <span class="cross-lang-badge">cross-lang</span>';
          html += '</div>';
        });
        html += '</div>';
      }
      ins.innerHTML = html;
      const activeLine = document.querySelector('.code-line[data-node-id="' + node.id + '"]');
      if (activeLine) {
        document.querySelectorAll('.code-line').forEach(l => l.classList.remove('active'));
        activeLine.classList.add('active');
        activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    // Code Panel
    function updateCodeView(scopePrefix) {
      const container = document.getElementById('code-content');
      container.innerHTML = "";
      const scopeNodes = gData.nodes
        .filter(n => n.group === scopePrefix || n.group.startsWith(scopePrefix + '.'))
        .sort((a, b) => a.id - b.id);
      scopeNodes.forEach(node => {
        const line = document.createElement('div');
        line.className = 'code-line';
        line.setAttribute('data-node-id', node.id);
        if (node.kind.includes('entry') || node.kind === 'phi') {
          line.classList.add('synthetic');
          line.innerText = node.raw;
        } else {
          try { line.innerHTML = hljs.highlight(node.raw, {language: 'java'}).value; }
          catch(e) { line.innerText = node.raw; }
        }
        // Clone highlighting in code view
        const clones = nodeCloneMap[node.id];
        if (clones && clones.length > 0) {
          const bestClone = clones[0];
          line.classList.add('clone-hl');
          line.style.borderLeftColor = CLONE_COLORS[bestClone.type] || '#fff';
        }
        line.onclick = () => focusNode(node);
        container.appendChild(line);
      });
    }

    function focusNode(node) {
      updateInspector(node);
      const distRatio = 1 + 150/Math.hypot(node.x, node.y, node.z);
      Graph.cameraPosition({ x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, node, 1500);
    }

    // Scope Tree
    function buildScopeTree() {
      const root = { children: {}, fullName: "" };
      Object.keys(scopeColors).forEach(scopePath => {
        const parts = scopePath.split('.');
        let current = root;
        parts.forEach((part, i) => {
          if (!current.children[part]) {
            current.children[part] = { children: {}, fullName: parts.slice(0, i+1).join('.') };
          }
          current = current.children[part];
        });
      });
      return root;
    }

    function renderTree(node, container, name) {
      const hasChildren = Object.keys(node.children).length > 0;
      const nodeDiv = document.createElement('div');
      nodeDiv.className = 'tree-node';
      if (hasChildren) {
        const row = document.createElement('div'); row.className = 'tree-row';
        const arrow = document.createElement('div'); arrow.className = 'tree-arrow'; arrow.innerText = '\u25be';
        const label = document.createElement('div'); label.className = 'tree-label'; label.innerText = name;
        const content = document.createElement('div'); content.className = 'tree-content';
        arrow.onclick = (e) => { e.stopPropagation(); arrow.classList.toggle('collapsed'); content.classList.toggle('collapsed'); };
        label.onclick = (e) => { e.stopPropagation(); exitCloneMode(); focusScopePrefix(node.fullName); updateCodeView(node.fullName); };
        Object.entries(node.children).forEach(([childName, childNode]) => renderTree(childNode, content, childName));
        row.appendChild(arrow); row.appendChild(label); nodeDiv.appendChild(row); nodeDiv.appendChild(content);
      } else {
        const leaf = document.createElement('div'); leaf.className = 'scope-leaf';
        const color = scopeColors[node.fullName] || '#fff';
        leaf.innerHTML = '<span class="color-dot" style="background:' + color + '"></span>' + name;
        leaf.onclick = (e) => { e.stopPropagation(); exitCloneMode(); focusScopePrefix(node.fullName); updateCodeView(node.fullName); };
        nodeDiv.appendChild(leaf);
      }
      container.appendChild(nodeDiv);
    }

    const scopeTreeData = buildScopeTree();
    const treeContainer = document.getElementById('scope-tree');
    Object.entries(scopeTreeData.children).forEach(([name, node]) => renderTree(node, treeContainer, name));

    // Graph
    const Graph = ForceGraph3D()
      (document.getElementById('3d-graph'))
        .graphData(gData)
        .nodeLabel('name')
        .nodeColor(node => node.color)
        .nodeVisibility(node => isFiltering ? visibleNodes.has(node.id) : true)
        .linkDirectionalArrowLength(3.5)
        .linkDirectionalArrowRelPos(1)
        .linkLabel(link => link.name)
        .linkColor(link => link.color)
        .linkVisibility(link => isFiltering ? visibleLinks.has(link) : true)
        .onNodeClick(node => {
          updateInspector(node);
          const distance = 100;
          const distRatio = 1 + distance/Math.hypot(node.x, node.y, node.z);
          Graph.cameraPosition({ x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, node, 2000);
        });

    // Memory Slot Filter
    const uniqueSlots = [...new Set(gData.links.map(l => l.name))].sort();
    const select = document.getElementById('slot-select');
    uniqueSlots.forEach(slot => {
      const opt = document.createElement('option');
      opt.value = slot; opt.innerText = slot; select.appendChild(opt);
    });
    select.addEventListener('change', (e) => {
      exitCloneMode();
      const slot = e.target.value;
      visibleNodes.clear(); visibleLinks.clear();
      if (slot === 'all') { isFiltering = false; Graph.nodeVisibility(() => true).linkVisibility(() => true).nodeVal(1); return; }
      gData.links.forEach(link => {
        if (link.name === slot) {
          const tgtId = link.target.id !== undefined ? link.target.id : link.target;
          const srcId = link.source.id !== undefined ? link.source.id : link.source;
          visibleLinks.add(link); visibleNodes.add(srcId); visibleNodes.add(tgtId);
        }
      });
      isFiltering = true;
      Graph.nodeVisibility(node => visibleNodes.has(node.id)).linkVisibility(link => visibleLinks.has(link));
    });

    function focusScopePrefix(scopePrefix) {
      visibleNodes.clear(); visibleLinks.clear(); select.value = 'all'; currentStepIdx = -1;
      let hasNodes = false;
      gData.nodes.forEach(node => {
        if (node.group === scopePrefix || node.group.startsWith(scopePrefix + '.')) { visibleNodes.add(node.id); hasNodes = true; }
      });
      gData.links.forEach(link => {
        const tgtId = link.target.id !== undefined ? link.target.id : link.target;
        const srcId = link.source.id !== undefined ? link.source.id : link.source;
        if (visibleNodes.has(srcId) && visibleNodes.has(tgtId)) visibleLinks.add(link);
      });
      isFiltering = true;
      Graph.nodeVisibility(node => visibleNodes.has(node.id)).linkVisibility(link => visibleLinks.has(link));
      if (hasNodes) setTimeout(() => Graph.zoomToFit(1500, 50, node => visibleNodes.has(node.id)), 100);
    }

    // ============================================================
    // CLONE VIEW
    // ============================================================

    function getFilteredClones() {
      return cloneData.filter(cc => activeTypeFilters.has(cc.type));
    }

    // Collect the set of active clone node IDs given current filters + selection
    function getActiveCloneNodeIds() {
      const ids = new Set();
      const filtered = getFilteredClones();
      filtered.forEach(cc => {
        if (selectedCloneId !== null && cc.id !== selectedCloneId) return;
        cc.occurrences.forEach(occ => occ.dag_node_ids.forEach(nid => ids.add(nid)));
      });
      return ids;
    }

    // For a given node, determine its clone color (or null if not a clone node)
    function getCloneColorForNode(nodeId) {
      const clones = nodeCloneMap[nodeId];
      if (!clones) return null;
      // When a specific clone is selected, only color nodes in that clone
      if (selectedCloneId !== null) {
        const match = clones.find(cc => cc.id === selectedCloneId && activeTypeFilters.has(cc.type));
        return match ? CLONE_COLORS[match.type] : null;
      }
      // No selection: color by highest-priority active type
      const priority = ["IV", "III", "II", "I"];
      for (const t of priority) {
        if (!activeTypeFilters.has(t)) continue;
        if (clones.find(cc => cc.type === t)) return CLONE_COLORS[t];
      }
      return null;
    }

    function enterCloneMode() {
      cloneMode = true;
      isFiltering = false;
      document.getElementById('btn-clone-toggle').classList.add('active');
      document.getElementById('btn-clone-toggle').innerText = 'Hide Clones';
      applyCloneView();
    }

    function exitCloneMode() {
      cloneMode = false;
      selectedCloneId = null;
      document.getElementById('btn-clone-toggle').classList.remove('active');
      document.getElementById('btn-clone-toggle').innerText = 'Show Clones';
      // Reset everything with explicit function callbacks to clear cached state
      Graph
        .nodeColor(n => n.color)
        .nodeVisibility(() => true)
        .nodeVal(1)
        .linkColor(l => l.color)
        .linkVisibility(() => true)
        .linkOpacity(0.8);
      document.querySelectorAll('.clone-class-item').forEach(el => el.classList.remove('selected'));
    }

    function applyCloneView() {
      if (!cloneMode) return;
      const activeNodeIds = getActiveCloneNodeIds();

      // Color: clone nodes get their type color, others are dimmed
      Graph.nodeColor(node => {
        const cloneColor = getCloneColorForNode(node.id);
        if (cloneColor) return cloneColor;
        return DIM_COLOR;
      });

      // Size: clone nodes are larger
      Graph.nodeVal(node => {
        return activeNodeIds.has(node.id) ? 3 : 0.5;
      });

      // Visibility: all nodes visible (dimmed ones are nearly invisible but present)
      Graph.nodeVisibility(() => true);

      // Links: only show edges where BOTH endpoints are active clone nodes
      Graph.linkVisibility(link => {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source;
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
        return activeNodeIds.has(srcId) && activeNodeIds.has(tgtId);
      });

      Graph.linkOpacity(link => {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source;
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
        return (activeNodeIds.has(srcId) && activeNodeIds.has(tgtId)) ? 0.9 : DIM_LINK;
      });

      // Zoom to the active nodes when a specific clone is selected
      if (selectedCloneId !== null && activeNodeIds.size > 0) {
        setTimeout(() => Graph.zoomToFit(1500, 80, node => activeNodeIds.has(node.id)), 200);
      }
    }

    // Toggle button
    document.getElementById('btn-clone-toggle').onclick = () => {
      if (cloneMode) exitCloneMode(); else enterCloneMode();
    };

    // Type filter buttons
    const typeFilterDiv = document.getElementById('type-filter');
    ["I", "II", "III", "IV"].forEach(t => {
      const btn = document.createElement('div');
      btn.className = 'type-btn on';
      btn.style.borderColor = CLONE_COLORS[t];
      btn.style.color = CLONE_COLORS[t];
      btn.innerText = t;
      btn.onclick = () => {
        if (activeTypeFilters.has(t)) { activeTypeFilters.delete(t); btn.classList.remove('on'); }
        else { activeTypeFilters.add(t); btn.classList.add('on'); }
        selectedCloneId = null;
        document.querySelectorAll('.clone-class-item').forEach(el => el.classList.remove('selected'));
        renderCloneList();
        if (cloneMode) applyCloneView();
      };
      typeFilterDiv.appendChild(btn);
    });

    // Clone class list
    function renderCloneList() {
      const container = document.getElementById('clone-list');
      container.innerHTML = '';
      const filtered = getFilteredClones();
      filtered.forEach(cc => {
        const div = document.createElement('div');
        div.className = 'clone-class-item';
        div.style.borderLeftColor = CLONE_COLORS[cc.type] || '#fff';
        let label = 'Type ' + cc.type + ' #' + cc.id;
        if (cc.similarity) label += ' sim=' + cc.similarity;
        label += ' (' + cc.occurrences.length + ' occ)';
        div.innerText = label;
        if (cc.cross_language) {
          const badge = document.createElement('span');
          badge.className = 'cross-lang-badge'; badge.innerText = 'cross-lang';
          div.appendChild(badge);
        }
        div.onclick = () => {
          // Toggle selection
          document.querySelectorAll('.clone-class-item').forEach(el => el.classList.remove('selected'));
          if (selectedCloneId === cc.id) {
            selectedCloneId = null;
          } else {
            selectedCloneId = cc.id;
            div.classList.add('selected');
          }
          if (!cloneMode) enterCloneMode(); else applyCloneView();
          // Show occurrences side by side in code panel
          if (selectedCloneId !== null) showCloneInCodePanel(cc);
        };
        container.appendChild(div);
      });
    }

    function showCloneInCodePanel(cc) {
      const container = document.getElementById('code-content');
      container.innerHTML = '';
      cc.occurrences.forEach((occ, oi) => {
        const header = document.createElement('div');
        header.style.cssText = 'color: #889; font-size: 11px; margin: 10px 0 4px; border-bottom: 1px solid #333; padding-bottom: 3px;';
        header.innerText = 'Occurrence ' + (oi+1) + ': ' + (occ.scope || 'seg_' + occ.seg_id) + (occ.file ? ' (' + occ.file + ')' : '') + (occ.language ? ' [' + occ.language + ']' : '');
        container.appendChild(header);
        occ.dag_node_ids.forEach(nid => {
          const node = gData.nodes.find(n => n.id === nid);
          if (!node) return;
          const line = document.createElement('div');
          line.className = 'code-line clone-hl';
          line.style.borderLeftColor = CLONE_COLORS[cc.type] || '#fff';
          line.setAttribute('data-node-id', nid);
          try { line.innerHTML = hljs.highlight(node.raw, {language: 'java'}).value; }
          catch(e) { line.innerText = node.raw; }
          line.onclick = () => focusNode(node);
          container.appendChild(line);
        });
      });
    }

    renderCloneList();

    // Stepper
    let currentScope = null;
    function stepTo(idx) {
      if (idx < 0 || idx >= executionOrder.length) return;
      exitCloneMode();
      currentStepIdx = idx;
      const node = executionOrder[currentStepIdx];
      if (currentScope !== node.group) { currentScope = node.group; updateCodeView(node.group); }
      updateInspector(node);
      isFiltering = false; highlightNodes.clear(); highlightLinks.clear();
      highlightNodes.add(node.id);
      gData.links.forEach(link => {
        const tgtId = link.target.id !== undefined ? link.target.id : link.target;
        const srcId = link.source.id !== undefined ? link.source.id : link.source;
        if (tgtId === node.id || srcId === node.id) { highlightLinks.add(link); highlightNodes.add(srcId); highlightNodes.add(tgtId); }
      });
      Graph.nodeVisibility(() => true).linkVisibility(() => true).nodeVal(1);
      Graph.nodeColor(n => highlightNodes.has(n.id) ? n.color : 'rgba(50,50,50,0.1)')
           .linkOpacity(l => highlightLinks.has(l) ? 0.8 : 0.05);
      if (node.x !== undefined && !isNaN(node.x)) {
        const distRatio = 1 + 150/Math.hypot(node.x, node.y, node.z);
        Graph.cameraPosition({ x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, node, 1000);
      }
    }

    document.getElementById('btn-next').onclick = () => stepTo(currentStepIdx + 1);
    document.getElementById('btn-prev').onclick = () => stepTo(Math.max(0, currentStepIdx - 1));
    document.getElementById('btn-play').onclick = () => {
      isPlaying = !isPlaying;
      document.getElementById('btn-play').innerText = isPlaying ? "\u23f8 Pause" : "\u25b6 Play";
      if (isPlaying) { playInterval = setInterval(() => { if (currentStepIdx >= executionOrder.length - 1) { clearInterval(playInterval); isPlaying = false; } else stepTo(currentStepIdx + 1); }, 1000); }
      else clearInterval(playInterval);
    };

    document.getElementById('btn-reset-step').onclick = () => {
      clearInterval(playInterval); isPlaying = false; currentStepIdx = -1; exitCloneMode();
      isFiltering = false; highlightNodes.clear(); highlightLinks.clear();
      Graph.nodeVisibility(() => true).linkVisibility(() => true).nodeColor(n => n.color).nodeVal(1).linkOpacity(0.8);
      Graph.cameraPosition({x: 0, y: 0, z: 800}, {x:0, y:0, z:0}, 2000);
      document.getElementById('code-content').innerHTML = "Select a scope to view source...";
    };
  </script>
</body>
</html>'''


def cmd_detect(args) -> None:
    """Execute the ``detect`` subcommand.

    Collects or loads source, runs the requested clone detection types (I–IV),
    and writes the results to a file or stdout.  Optionally exports an
    interactive 3-D clone visualisation.

    Args:
        args: Parsed ``argparse.Namespace`` from the ``detect`` subparser.
    """
    src = args.src
    types = args.type
    skipped_list = []

    if src.endswith('.json'):
        # Pre-parsed input — filtering already applied at parse time
        with open(src, 'r') as f:
            parsed_str_for_detect = f.read()
    else:
        # Raw C input — parse in memory, applying filters now
        c_files = _collect_c_files(src)
        parsed_list, skipped_list = _parse_files(
            c_files, args.include_comments, args.include_includes, args.include_macros
        )
        if not parsed_list:
            print("Error: No files could be parsed successfully.")
            exit(1)
        parsed_str_for_detect = _build_parsed_str(parsed_list, skipped_list)

    results_by_type = {}

    # Run Types 1, 2, 4 first so we can build an exclusion set for Type 3
    for t in sorted(types):
        if t in (1, 2):
            result_str = detect_clones(
                parsed_str_for_detect,
                type_2_norm=(t == 2),
                maximal=args.maximal,
                min_length=args.min_length,
                max_freq=args.max_freq,
                filter_overlaps=args.filter_overlaps
            )
            results_by_type[t] = json.loads(result_str)["clone_classes"]
        elif t == 4:
            result_str = detect_type4(
                parsed_str_for_detect,
                min_length=args.min_length,
            )
            results_by_type[t] = json.loads(result_str)["clone_classes"]

    # Build exclusion set: segment pairs already covered by Types I, II, IV.
    # Type III should only report clones that the other detectors miss.
    exclude_seg_pairs = set()
    for t in (1, 2, 4):
        for clone in results_by_type.get(t, []):
            sids = [o["seg_id"] for o in clone["occurrences"]]
            for i in range(len(sids)):
                for j in range(i + 1, len(sids)):
                    exclude_seg_pairs.add((min(sids[i], sids[j]), max(sids[i], sids[j])))

    # Now run Type 3 with exclusions
    if 3 in types:
        result_str = detect_type3(
            parsed_str_for_detect,
            similarity_threshold=args.similarity_threshold,
            min_length=args.min_length_type3,
            exclude_seg_pairs=exclude_seg_pairs,
        )
        results_by_type[3] = json.loads(result_str)["clone_classes"]

    # Deduplicate: remove Type II clones already caught by Type I
    type1_fingerprints = set()
    if 1 in results_by_type:
        for clone in results_by_type[1]:
            fp = frozenset(
                (o["seg_id"], o["start_stmt_idx"], o["end_stmt_idx"])
                for o in clone["occurrences"]
            )
            type1_fingerprints.add(fp)

    all_clone_classes = []
    for t in sorted(types):
        for clone in results_by_type[t]:
            if t == 2 and 1 in results_by_type:
                fp = frozenset(
                    (o["seg_id"], o["start_stmt_idx"], o["end_stmt_idx"])
                    for o in clone["occurrences"]
                )
                if fp in type1_fingerprints:
                    continue
            all_clone_classes.append(clone)
    for i, clone in enumerate(all_clone_classes, 1):
        clone["id"] = i

    # --- Detection metadata ---
    parse_meta = json.loads(parsed_str_for_detect).get("meta", {})
    seg_by_id_meta = {seg["id"]: seg for seg in json.loads(parsed_str_for_detect)["segments"]}

    total_occurrences = sum(len(c["occurrences"]) for c in all_clone_classes)
    total_cloned_stmts = sum(
        c.get("length", len(c["occurrences"][0].get("statements", [])) if c["occurrences"] else 0)
        * len(c["occurrences"])
        for c in all_clone_classes
    )
    clones_by_type = {}
    for c in all_clone_classes:
        ct = c["clone_type"]
        clones_by_type[ct] = clones_by_type.get(ct, 0) + 1

    cross_language_count = sum(1 for c in all_clone_classes if c.get("cross_language", False))

    cloned_seg_ids = set(o["seg_id"] for c in all_clone_classes for o in c["occurrences"])
    cloned_files = set()
    cloned_modules = set()
    for sid in cloned_seg_ids:
        seg = seg_by_id_meta.get(sid, {})
        if "file" in seg:
            cloned_files.add(seg["file"])
        if "module" in seg:
            cloned_modules.add(seg["module"])

    largest_clone = max(
        (c.get("length", len(c["occurrences"][0].get("statements", [])) if c["occurrences"] else 0)
         for c in all_clone_classes),
        default=0
    )
    most_occurrences = max((len(c["occurrences"]) for c in all_clone_classes), default=0)

    seg_clone_count = {}
    for c in all_clone_classes:
        for o in c["occurrences"]:
            sid = o["seg_id"]
            seg_clone_count[sid] = seg_clone_count.get(sid, 0) + 1
    most_cloned_seg_id = max(seg_clone_count, key=seg_clone_count.get) if seg_clone_count else None
    most_cloned_seg_file = (
        seg_by_id_meta.get(most_cloned_seg_id, {}).get("file")
        if most_cloned_seg_id is not None else None
    )

    detect_meta = {
        "clone_types_detected": sorted(types),
        "min_length": args.min_length,
        "max_freq": args.max_freq,
        "maximal_filter": args.maximal,
        "overlap_filter": args.filter_overlaps,
        "similarity_threshold": args.similarity_threshold if 3 in types else None,
        "min_length_type3": args.min_length_type3 if 3 in types else None,
        "total_files_scanned": parse_meta.get("total_files", 0),
        "total_files_skipped": len(skipped_list),
        "skipped_files": skipped_list,
        "total_modules": parse_meta.get("total_modules", 0),
        "total_segments": parse_meta.get("total_segments", 0),
        "total_statements": parse_meta.get("total_statements", 0),
        "total_clone_classes": len(all_clone_classes),
        "clone_classes_by_type": clones_by_type,
        "cross_language_clone_classes": cross_language_count,
        "total_occurrences": total_occurrences,
        "total_cloned_statements": total_cloned_stmts,
        "largest_clone_length": largest_clone,
        "most_occurrences_in_class": most_occurrences,
        "files_with_clones": sorted(cloned_files),
        "total_files_with_clones": len(cloned_files),
        "modules_with_clones": sorted(cloned_modules),
        "total_modules_with_clones": len(cloned_modules),
        "most_cloned_seg_id": most_cloned_seg_id,
        "most_cloned_seg_file": most_cloned_seg_file,
        "total_segments_with_clones": len(seg_clone_count),
    }

    final = json.dumps({"meta": detect_meta, "clone_classes": all_clone_classes}, indent=2)
    if args.output:
        with open(args.output, 'w') as f:
            f.write(final)
        print(f"Detection output written to {args.output}")
    else:
        if not getattr(args, "export_3d_html", None):
            print(final)

    if getattr(args, "export_3d_html", None):
        _export_clone_3d_html(
            args.export_3d_html,
            json.loads(parsed_str_for_detect),
            all_clone_classes
        )
        print(f"3D clone visualization exported to {args.export_3d_html}")

def cmd_run(args) -> None:
    """Execute the ``run`` subcommand.

    Loads a parsed IR JSON file and runs the specified function using the
    interpreter VM.  Either prints program output to stdout or appends the
    execution trace back to the JSON file.

    Args:
        args: Parsed ``argparse.Namespace`` from the ``run`` subparser.
    """
    from ..vm import VM

    src        = args.src
    fn_name    = args.fn
    max_unroll = args.max_unroll

    # --- Only accepts parsed JSON --- 
    if not src.endswith('.json'):
        print("Error: 'run' requires a parsed .json file as --src. "
              "Run 'parse' first to produce one.")
        exit(1)

    with open(src, 'r') as f:
        parsed_str = f.read()
    parsed_doc = json.loads(parsed_str)

    # --- Build VM ---
    vm = VM(parsed_str, max_unroll=max_unroll)

    # --- Build arg frame from --args ---
    arg_frame = {}
    if args.args:
        seg_map    = {s["name"]: s for s in parsed_doc["segments"]
                      if s["type"] == "function"}
        target_seg = seg_map.get(fn_name)
        if target_seg is None:
            print(f"Error: Function '{fn_name}' not found.")
            exit(1)
        params = [m for m in target_seg.get("memory", []) if m.get("param")]
        seen, logical = {}, []
        for p in params:
            parent = p.get("udt_parent")
            if parent:
                if parent not in seen:
                    seen[parent] = True
                    logical.append(("udt", parent,
                        [m["name"] for m in params if m.get("udt_parent") == parent]))
            else:
                logical.append(("plain", p["name"], None))
        parsed_args = [json.loads(a) for a in args.args]
        for i, lp in enumerate(logical):
            if i >= len(parsed_args): break
            if lp[0] == "plain":
                arg_frame[lp[1]] = parsed_args[i]
            else:
                vals = parsed_args[i] if isinstance(parsed_args[i], list) else [parsed_args[i]]
                for j, fs in enumerate(lp[2]):
                    arg_frame[fs] = vals[j] if j < len(vals) else 0

    # --- Execute ---
    try:
        ret = vm.call_fn(fn_name, arg_frame)
    except NameError as e:
        print(f"Error: {e}")
        exit(1)
    except NotImplementedError as e:
        print(f"Error: {e}")
        exit(1)

    if vm.unroll_capped:
        print(f"Warning: One or more loops were capped at {max_unroll} iterations.")

    # --- Emit ---
    if args.output is not None:
        # --output given (with or without a path value):
        # append trace into the parsed doc and write it out.
        # If no path was provided, write back to --src.
        out_path = args.output if args.output else src

        parsed_doc["trace_meta"] = {
            "fn":            fn_name,
            "args":          args.args or [],
            "max_unroll":    max_unroll,
            "unroll_capped": vm.unroll_capped,
            "output":        vm.output,
            "return_value":  ret,
        }
        parsed_doc["trace"] = vm.trace

        with open(out_path, 'w') as f:
            json.dump(parsed_doc, f, indent=2)
        print(f"Trace written to {out_path}")
    else:
        # No --output flag at all — just print program output to stdout
        for line in vm.output:
            print(line)
        if fn_name != "main" and ret is not None:
            print(f"Return value: {ret}")