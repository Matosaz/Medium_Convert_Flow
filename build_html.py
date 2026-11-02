#!/usr/bin/env python3
"""
LaTeX (macros Hype) -> HTML limpo, pronto para o 'Import a story' do Medium.

Uso:
  python build_html.py                       # converte tudo em articles/
  python build_html.py articles/teste-fluxo  # converte um artigo
  python build_html.py --base-url https://usuario.github.io/repo --out dist
"""
import argparse, html, json, re, shutil, subprocess, sys
from pathlib import Path
import yaml
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SHIM = (ROOT / "html" / "shim.tex").read_text(encoding="utf-8")

# Comandos de espaçamento que só fazem sentido no PDF.
LAYOUT_ONLY = re.compile(
    r"\\(?:hspace|vspace)\*?\{[^}]*\}|\\(?:noindent|newpage|clearpage|medskip|bigskip|smallskip)\b"
)

# ---------------------------------------------------------------- parsing LaTeX
def read_group(s: str, i: int):
    if s[i] != "{":
        raise ValueError(f"esperava '{{' na posição {i}, achei {s[i]!r}")
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "%":
            nl = s.find("\n", j)
            j = len(s) if nl == -1 else nl
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    raise ValueError("chaves não balanceadas")

def skip_ws_comments(s: str, i: int) -> int:
    while i < len(s):
        if s[i].isspace():
            i += 1
        elif s[i] == "%":
            nl = s.find("\n", i)
            i = len(s) if nl == -1 else nl
        else:
            break
    return i

def parse_hypearticle(tex: str):
    m = re.search(r"\\hypearticle\b", tex)
    if not m:
        raise ValueError("\\hypearticle não encontrado")
    i, groups = m.end(), []
    for _ in range(3):
        i = skip_ws_comments(tex, i)
        g, i = read_group(tex, i)
        groups.append(g)
    return groups

def find_article_tex(folder: Path) -> Path:
    for p in sorted(folder.glob("*.tex")):
        if r"\hypearticle" in p.read_text(encoding="utf-8"):
            return p
    raise FileNotFoundError(f"nenhum .tex com \\hypearticle em {folder}")

def tex_inline_to_text(s: str) -> str:
    s = s.replace(r"\&", "&").replace(r"\%", "%").replace(r"\_", "_")
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    return re.sub(r"[{}]", "", s).strip()

# ------------------------------------------------------------------ conversão
PANDOC_HELP = """pandoc não encontrado no PATH."""

def pandoc_body(body: str, workdir: Path):
    exe = shutil.which("pandoc")
    if not exe:
        raise RuntimeError(PANDOC_HELP)
    src = SHIM + "\n" + LAYOUT_ONLY.sub("", body)
    cmd = [exe, "-f", "latex", "-t", "html5", "--wrap=none", "--verbose",
           "--shift-heading-level-by=1", "--webtex",
           f"--resource-path={workdir}"]
    r = subprocess.run(cmd, input=src, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("pandoc falhou:\n" + r.stderr)
    found = re.findall(r"Skipped '(.+?)' at line", r.stderr)
    skipped = [x for x in found if not re.match(r"\\(?:begin|end)\{|\\[be]group", x)]
    return r.stdout, skipped

PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="author" content="{author}">
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
{og_image}
<meta property="article:author" content="{author}">
{tags}
<style>
  :root {{ --hype-orange:#FF6B1A; --hype-purple:#8A5CF5; }}
  body {{ font:18px/1.7 Georgia,serif; max-width:42rem; margin:3rem auto; padding:0 1rem; color:#111; }}
  h1 {{ font:800 2.2rem/1.2 system-ui,sans-serif; }}
  h2 {{ font:700 1.4rem/1.3 system-ui,sans-serif; margin-top:2.2rem; }}
  article > h1 + p {{ color:#555; font-family:system-ui,sans-serif; }}
  img {{ max-width:100%; height:auto; }}
  figure {{ margin:2rem 0; text-align:center; }}
  figcaption {{ font:.85rem system-ui,sans-serif; color:#555; }}
  blockquote {{ border-left:6px solid var(--hype-purple); margin:1.5rem 0; padding:.2rem 1rem; background:#f3eefe; }}
  blockquote.infobox {{ border-color:var(--hype-orange); background:#fff1e8; }}
  ul li::marker {{ color:var(--hype-orange); }}
  .download {{ font-family:system-ui,sans-serif; margin-top:3rem; }}
</style>
</head>
<body>
<article>{article}</article>
</body>
</html>
"""

def build_article(folder: Path, out: Path, base_url: str) -> dict:
    tex_path = find_article_tex(folder)
    title_tex, author_tex, body = parse_hypearticle(tex_path.read_text(encoding="utf-8"))
    title, author = tex_inline_to_text(title_tex), tex_inline_to_text(author_tex)

    meta = {}
    if (folder / "meta.yml").exists():
        meta = yaml.safe_load((folder / "meta.yml").read_text(encoding="utf-8")) or {}
    slug = meta.get("slug") or folder.name
    base = base_url.rstrip("/")
    page_url = f"{base}/artigos/{slug}/"
    canonical = meta.get("url_canonica") or page_url
    desc = meta.get("descricao", "")

    art_out = out / "artigos" / slug
    (art_out / "img").mkdir(parents=True, exist_ok=True)

    def publish_image(rel: str) -> str | None:
        src = (folder / rel).resolve()
        if not src.exists():
            return None
        shutil.copy2(src, art_out / "img" / src.name)
        return f"{page_url}img/{src.name}"

    body_html, skipped = pandoc_body(body, folder)
    soup = BeautifulSoup(body_html, "lxml")

    # 1. FÓRMULAS: Converte <img> do codecogs para texto <code>
    for img in soup.find_all("img"):
        if "codecogs" in img.get("src", ""):
            formula = img.get("alt", img.get("title", ""))
            code_tag = soup.new_tag("code")
            code_tag.string = formula
            img.replace_with(code_tag)

    # 2. CAIXAS INFORMATIVAS: Converte para blockquote limpo
    for div in soup.select("div.hypeinfobox"):
        div.name = "blockquote"
        div.attrs = {}

    for bq in soup.find_all("blockquote"):
        next_sib = bq.find_next_sibling()
        if next_sib and next_sib.name == "blockquote":
            # Insere <hr> que o Medium reconhece como quebra de secção (três pontos)
            sep = soup.new_tag("hr")
            bq.insert_after(sep)

    # 3. IMAGENS E LEGENDAS: Reconstrução canónica estrita
    missing = []
    # Usamos list() para evitar loops infinitos ao modificar a árvore HTML
    for img in list(soup.find_all("img")):
        src = img.get("src", "")
        if src.startswith(("http://", "https://")):
            continue

        new = publish_image(src)
        if new is None:
            missing.append(src)
            continue

        parent = img.parent
        caption_text = img.get("alt", "").strip()

        clean_fig = soup.new_tag("figure")
        clean_img = soup.new_tag("img", src=new)
        clean_fig.append(clean_img)
        
        # Recupera legenda e reconstrói o bloco <figure>
        if parent.name == "figure":
            fc = parent.find("figcaption")
            if fc and fc.get_text(strip=True):
                caption_text = fc.get_text(strip=True)
            if caption_text:
                clean_fc = soup.new_tag("figcaption")
                clean_fc.string = caption_text
                clean_fig.append(clean_fc)
            parent.replace_with(clean_fig)
        elif parent.name == "p":
            if caption_text:
                clean_fc = soup.new_tag("figcaption")
                clean_fc.string = caption_text
                clean_fig.append(clean_fc)
            if len(parent.contents) == 1:
                parent.replace_with(clean_fig)
            else:
                img.replace_with(clean_fig)
        else:
            if caption_text:
                clean_fc = soup.new_tag("figcaption")
                clean_fc.string = caption_text
                clean_fig.append(clean_fc)
            img.replace_with(clean_fig)

    # Limpeza de IDs e classes desnecessárias nos títulos
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        h.attrs.pop("id", None)
        h.attrs.pop("class", None)

    # 4. LIMPEZA DEFINITIVA DE BLOCOS VAZIOS
    for empty in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div"]):
        if not empty.get_text(strip=True) and not empty.find(["img", "br", "code", "hr"]):
            empty.decompose()

    content = "".join(str(c) for c in soup.body.contents).strip()

    # 5. MONTAGEM: Capa, Créditos e Artigo
    cover_url = publish_image(meta["capa"]) if meta.get("capa") else None
    cover = f'<figure><img src="{cover_url}" alt="{html.escape(title)}"></figure>' if cover_url else ""
    og_image = f'<meta property="og:image" content="{cover_url}">' if cover_url else ""
    tags = "\n".join(f'<meta property="article:tag" content="{html.escape(t)}">' for t in meta.get("tags", []))
    edicao = f" · Edição {html.escape(str(meta['edicao']))}" if meta.get("edicao") else ""
    download = (f'<p class="download"><a href="{meta["pdf"]}">Baixar a edição em PDF</a></p>' if meta.get("pdf") else "")

    # Crédito de autoria SEM classes personalizadas.
    credit = f"<p><em>Por {html.escape(author)}{edicao}</em></p>"
    
    # IMPORTANTE: O Medium apaga parágrafos imediatamente após o <h1> se achar que são metadados.
    # Colocar a capa ANTES do crédito impede este comportamento.
    article = "".join([f"<h1>{html.escape(title)}</h1>", cover, credit, content, download])
    
    page = PAGE.format(title=html.escape(title), author=html.escape(author),
                       desc=html.escape(desc), canonical=canonical, og_image=og_image,
                       tags=tags, article=article)
    (art_out / "index.html").write_text(page, encoding="utf-8")

    return {"slug": slug, "title": title, "author": author, "descricao": desc,
            "edicao": meta.get("edicao", ""), "tags": meta.get("tags", []),
            "url": page_url, "canonical": canonical, "capa": cover_url,
            "pdf": meta.get("pdf", ""), "medium_url": meta.get("medium_url", ""),
            "_missing_images": missing, "_skipped": skipped,
            "_html": art_out / "index.html"}

# ----------------------------------------------------------------- verificação
def check(entry: dict, base_url: str) -> list[tuple[str, str]]:
    res = []
    soup = BeautifulSoup(entry["_html"].read_text(encoding="utf-8"), "lxml")
    art = soup.find("article")
    add = lambda lvl, msg: res.append((lvl, msg))

    n_h1 = len(art.find_all("h1"))
    add("OK" if n_h1 == 1 else "ERRO", f"{n_h1} <h1> (esperado: 1)")
    deep = art.find_all(["h3", "h4", "h5", "h6"])
    add("OK" if not deep else "AVISO", "só h1/h2 (o Medium tem 2 níveis de título)" if not deep
        else f"{len(deep)} título(s) h3+ — o Medium não tem esse nível")
    add("OK" if soup.find("link", rel="canonical") else "ERRO", "link canonical presente")
    if entry["_skipped"]:
        add("ERRO", "conteúdo DESCARTADO pelo pandoc: " + ", ".join(sorted(set(entry["_skipped"]))))
    if entry["_missing_images"]:
        add("ERRO", f"imagens não encontradas: {entry['_missing_images']}")
    imgs = art.find_all("img")
    no_alt = [i for i in imgs if not i.get("alt")]
    add("OK" if not no_alt else "AVISO", f"{len(imgs)} imagem(ns); sem alt: {len(no_alt)}")
    words = len(art.get_text(" ").split())
    add("OK", f"{words} palavras")
    return res

# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("articles", nargs="*", type=Path, help="pastas de artigos (padrão: articles/*)")
    ap.add_argument("--out", type=Path, default=ROOT / "dist")
    ap.add_argument("--base-url", default="https://USUARIO.github.io/REPO",
                    help="URL pública onde dist/ será hospedado")
    a = ap.parse_args()

    folders = a.articles or sorted(p for p in (ROOT / "articles").iterdir() if p.is_dir())
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / ".nojekyll").write_text("")

    entries, failed = [], False
    for f in folders:
        print(f"\n== {f.name}")
        try:
            e = build_article(f, a.out, a.base_url)
        except Exception as exc:
            print(f"  ERRO: {exc}"); failed = True; continue
        entries.append(e)
        for lvl, msg in check(e, a.base_url):
            print(f"  [{lvl:5}] {msg}")
            failed |= lvl == "ERRO"
        print(f"  -> {e['url']}")

    public = [{k: v for k, v in e.items() if not k.startswith("_")} for e in entries]
    (a.out / "artigos.json").write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    items = "\n".join(f'<li><a href="{e["url"]}">{html.escape(e["title"])}</a></li>' for e in public)
    (a.out / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><title>Tá no Hype — artigos</title>'
        f'<h1>Tá no Hype — artigos</h1><ul>{items}</ul>', encoding="utf-8")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()