"""Generators for the knowledge base entry points: README.md and index.html.

Both files are rebuilt from scratch after every incremental run, using
only the sidecar metadata (plus article bodies for the offline viewer),
so they always reflect the current state of the knowledge base.
"""

import json
from collections import defaultdict

from .storage import KnowledgeBaseStorage
from .utils import now_iso


def generate_readme(storage: KnowledgeBaseStorage, topic: str,
                    keywords: list[str], overview: str = "") -> str:
    """Build README.md: overview, keyword scope, timestamps and article list."""
    metas = storage.list_metadata()
    by_category: dict[str, list] = defaultdict(list)
    for m in metas:
        by_category[m.category].append(m)

    lines = [
        f"# Knowledge Base: {storage.kb_name}",
        "",
        f"**Topic:** {topic}",
        "",
        f"**Last updated:** {now_iso()}",
        "",
    ]
    if overview:
        lines += ["## Overview", "", overview, ""]
    if keywords:
        lines += ["## Search keyword scope", ""]
        lines += [f"- {k}" for k in keywords]
        lines.append("")

    lines += [
        "## Contents",
        "",
        f"Total articles: **{len(metas)}**",
        "",
        "| Category | Articles |",
        "| --- | --- |",
    ]
    for cat in sorted(by_category):
        lines.append(f"| {cat} | {len(by_category[cat])} |")
    lines.append("")

    for cat in sorted(by_category):
        lines += [f"### {cat}", ""]
        for m in sorted(by_category[cat], key=lambda x: x.title):
            lines.append(f"- [{m.title}]({m.article_relpath}) — {m.summary}")
        lines.append("")

    lines += [
        "## How to browse",
        "",
        "Open `index.html` in a browser for the offline graphical entry "
        "point (folder tree, tag filters, full-text search and markdown preview).",
        "",
    ]
    content = "\n".join(lines)
    storage.readme_path.write_text(content, encoding="utf-8")
    return content


def generate_index_html(storage: KnowledgeBaseStorage) -> str:
    """Build the fully offline index.html.

    All metadata AND article markdown bodies are embedded as JSON inside
    the page, because browsers block fetch() of local files under the
    file:// protocol. No CDN or external asset is referenced.
    """
    entries = []
    for m in storage.list_metadata():
        try:
            body = storage.read_article(m.article_relpath)
        except OSError:
            body = "(article file missing)"
        entries.append({
            "title": m.title, "url": m.url, "category": m.category,
            "tags": m.tags, "summary": m.summary, "crawl_time": m.crawl_time,
            "path": m.article_relpath, "content": body,
        })

    # Escape "</" so embedded JSON can never close the <script> tag early.
    data_json = json.dumps(entries, ensure_ascii=False).replace("</", "<\\/")
    html = _HTML_TEMPLATE.replace("__KB_NAME__", storage.kb_name) \
                         .replace("__DATA_JSON__", data_json)
    storage.index_html_path.write_text(html, encoding="utf-8")
    return html


# Single-file offline viewer: inline CSS/JS only, no external resources.
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Knowledge Base: __KB_NAME__</title>
<style>
  body { margin:0; font-family:-apple-system,"Segoe UI",sans-serif; display:flex; height:100vh; }
  #sidebar { width:320px; border-right:1px solid #ddd; overflow-y:auto; padding:12px; box-sizing:border-box; }
  #main { flex:1; overflow-y:auto; padding:24px 40px; box-sizing:border-box; }
  #search { width:100%; padding:8px; box-sizing:border-box; margin-bottom:12px;
            border:1px solid #ccc; border-radius:6px; font-size:14px; }
  .cat > summary { cursor:pointer; font-weight:600; padding:4px 0; }
  .item { padding:4px 0 4px 16px; cursor:pointer; font-size:14px; color:#0366d6; }
  .item:hover { text-decoration:underline; }
  .meta-box { background:#f6f8fa; border:1px solid #ddd; border-radius:6px;
              padding:12px; margin-bottom:16px; font-size:13px; }
  .tag { display:inline-block; background:#eef2ff; color:#3730a3; border-radius:10px;
         padding:1px 8px; margin:2px; font-size:12px; }
  pre { background:#f6f8fa; padding:12px; border-radius:6px; overflow-x:auto; }
  code { background:#f0f0f0; border-radius:3px; padding:1px 4px; }
  img { max-width:100%; }
  h1,h2,h3 { border-bottom:1px solid #eee; padding-bottom:4px; }
</style>
</head>
<body>
<div id="sidebar">
  <input id="search" type="search" placeholder="Search title / tag / summary ...">
  <div id="tree"></div>
</div>
<div id="main"><p>Select an article on the left, or search above.</p></div>

<script id="kb-data" type="application/json">__DATA_JSON__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("kb-data").textContent);

/* Minimal offline markdown renderer (headings, emphasis, links, images,
   inline/fenced code, lists). Good enough for previews; swap in a local
   copy of marked.min.js for full CommonMark if ever needed. */
function escapeHtml(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function renderMd(md){
  const codeBlocks=[];
  md=md.replace(/```([\\s\\S]*?)```/g,(_,c)=>{codeBlocks.push(c);return "\\u0000"+(codeBlocks.length-1)+"\\u0000";});
  md=escapeHtml(md);
  md=md.replace(/^###### (.*)$/gm,"<h6>$1</h6>")
       .replace(/^##### (.*)$/gm,"<h5>$1</h5>")
       .replace(/^#### (.*)$/gm,"<h4>$1</h4>")
       .replace(/^### (.*)$/gm,"<h3>$1</h3>")
       .replace(/^## (.*)$/gm,"<h2>$1</h2>")
       .replace(/^# (.*)$/gm,"<h1>$1</h1>");
  md=md.replace(/!\\[([^\\]]*)\\]\\(([^)]+)\\)/g,'<img alt="$1" src="$2">');
  md=md.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g,'<a href="$2">$1</a>');
  md=md.replace(/\\*\\*([^*]+)\\*\\*/g,"<strong>$1</strong>").replace(/\\*([^*]+)\\*/g,"<em>$1</em>");
  md=md.replace(/`([^`]+)`/g,"<code>$1</code>");
  md=md.replace(/^(?:[-*] .*(?:\\n|$))+/gm,
    b=>"<ul>"+b.trim().split("\\n").map(l=>"<li>"+l.replace(/^[-*] /,"")+"</li>").join("")+"</ul>");
  md=md.split(/\\n{2,}/).map(p=>/^<(h\\d|ul|pre|img)/.test(p.trim())?p:"<p>"+p+"</p>").join("\\n");
  md=md.replace(/\\u0000(\\d+)\\u0000/g,(_,i)=>"<pre><code>"+escapeHtml(codeBlocks[+i])+"</code></pre>");
  return md;
}

function show(entry){
  const tags=entry.tags.map(t=>'<span class="tag">'+escapeHtml(t)+"</span>").join("");
  document.getElementById("main").innerHTML=
    '<div class="meta-box"><b>Source:</b> <a href="'+entry.url+'">'+escapeHtml(entry.url)+"</a><br>"+
    "<b>Category:</b> "+escapeHtml(entry.category)+" &nbsp; <b>Crawled:</b> "+escapeHtml(entry.crawl_time)+"<br>"+
    "<b>Tags:</b> "+tags+"<br><b>Summary:</b> "+escapeHtml(entry.summary)+"</div>"+
    renderMd(entry.content);
}

function buildTree(items){
  const tree=document.getElementById("tree");tree.innerHTML="";
  const groups={};
  items.forEach(e=>{(groups[e.category]=groups[e.category]||[]).push(e);});
  Object.keys(groups).sort().forEach(cat=>{
    const det=document.createElement("details");det.className="cat";det.open=true;
    det.innerHTML="<summary>"+escapeHtml(cat)+" ("+groups[cat].length+")</summary>";
    groups[cat].forEach(e=>{
      const d=document.createElement("div");d.className="item";d.textContent=e.title;
      d.onclick=()=>show(e);det.appendChild(d);
    });
    tree.appendChild(det);
  });
}

document.getElementById("search").addEventListener("input",ev=>{
  const q=ev.target.value.toLowerCase();
  buildTree(!q?DATA:DATA.filter(e=>
    (e.title+" "+e.summary+" "+e.category+" "+e.tags.join(" ")).toLowerCase().includes(q)));
});

buildTree(DATA);
</script>
</body>
</html>
"""
