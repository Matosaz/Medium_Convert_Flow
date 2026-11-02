#!/usr/bin/env python3
"""
LaTeX (macros Hype) -> HTML limpo, pronto para o 'Import a story' do Medium.

Uso:
  python build_html.py                       # converte tudo em articles/
  python build_html.py articles/teste-fluxo  # converte um artigo
  python build_html.py --base-url https://usuario.github.io/repo --out dist

Entrada de cada artigo (pasta):
  artigo.tex  (ou qualquer .tex que contenha \\hypearticle{titulo}{autor}{corpo})
  meta.yml    (opcional: slug, descricao, capa, tags, edicao, pdf, medium_url, ...)
  img/        (imagens referenciadas por \\articleimage)

Saída:
  <out>/artigos/<slug>/index.html + img/   (a URL que será importada no Medium)
  <out>/artigos.json                       (índice para o futuro site)
  <out>/index.html                         (lista simples dos artigos)
"""
import argparse, html, json, re, shutil, subprocess, sys
from pathlib import Path
import yaml
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):       # console do Windows: evitar UnicodeEncodeError
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
    """s[i] == '{'. Devolve (conteúdo, índice logo após o '}' correspondente)."""
    if s[i] != "{":
        raise ValueError(f"esperava '{{' na posição {i}, achei {s[i]!r}")
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "%":                       # comentário até o fim da linha
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
    return groups  # título, autor, corpo

def find_article_tex(folder: Path) -> Path:
    for p in sorted(folder.glob("*.tex")):
        if r"\hypearticle" in p.read_text(encoding="utf-8"):
            return p
    raise FileNotFoundError(f"nenhum .tex com \\hypearticle em {folder}")

def tex_inline_to_text(s: str) -> str:
    """Limpeza mínima de título/autor (vêm do .tex): \\& -> &, remove chaves."""
    s = s.replace(r"\&", "&").replace(r"\%", "%").replace(r"\_", "_")
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    return re.sub(r"[{}]", "", s).strip()

# ------------------------------------------------------------------ conversão
PANDOC_HELP = """pandoc não encontrado no PATH.
  Windows (PowerShell):  winget install --id JohnMacFarlane.Pandoc -e
                         (ou baixe o instalador em https://pandoc.org/installing.html)
  macOS:                 brew install pandoc
  Linux (Debian/Ubuntu): sudo apt-get install pandoc
Depois de instalar, FECHE e reabra o terminal e confira com:  pandoc --version"""

def pandoc_body(body: str, workdir: Path):
    """Devolve (html, descartados). O pandoc DESCARTA em silêncio macros que não conhece
    (inclusive o argumento); só o modo --verbose avisa. Capturamos esses avisos."""
    exe = shutil.which("pandoc")
    if not exe:
        raise RuntimeError(PANDOC_HELP)
    src = SHIM + "\n" + LAYOUT_ONLY.sub("", body)
    cmd = [exe, "-f", "latex", "-t", "html5", "--wrap=none", "--verbose",
           "--shift-heading-level-by=1", "--webtex",
           f"--resource-path={workdir}"]
    # encoding explícito: no Windows o padrão seria cp1252 e os acentos seriam corrompidos
    r = subprocess.run(cmd, input=src, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("pandoc falhou:\n" + r.stderr)
    found = re.findall(r"Skipped '(.+?)' at line", r.stderr)
    # \begin/\end/\bgroup/\egroup de ambientes são ruído: o conteúdo é mantido num <div>.
    # Já macros comuns com argumento (\foo{x}) perdem o conteúdo de verdade.
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
  :root {{ --hype-orange:#FF6B1A; --hype-purple:#8A5CF5; }}  /* ajustar aos hex reais */
  body {{ font:18px/1.7 Georgia,serif; max-width:42rem; margin:3rem auto; padding:0 1rem; color:#111; }}
  h1 {{ font:800 2.2rem/1.2 system-ui,sans-serif; }}
  h2 {{ font:700 1.4rem/1.3 system-ui,sans-serif; margin-top:2.2rem; }}
  article > h1 + p {{ color:#555; font-family:system-ui,sans-serif; }}  /* crédito de autoria */
  img {{ max-width:100%; height:auto; }}
  figure {{ margin:2rem 0; text-align:center; }}
  figcaption {{ font:.85rem system-ui,sans-serif; color:#555; }}
  blockquote {{ border-left:6px solid var(--hype-purple); margin:1.5rem 0; padding:.2rem 1rem;
               background:#f3eefe; }}
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

    # caixa informativa -> citação com classe (o Medium só conhece citação)
    for div in soup.select("div.hypeinfobox"):
        div.name = "blockquote"
        div["class"] = ["infobox"]

    # Citações (\highlight e infobox): o Medium ignora CSS e lida melhor com texto direto
    # dentro do <blockquote>; parágrafos internos viram "<br><br>".
    for bq in soup.find_all("blockquote"):
        next_sib = bq.find_next_sibling()
        if(next_sib and next_sib.name == "blockquote"):
            sep = soup.new_tag("hr")
            bq.insert_after(sep)

    # imagens: copiar para dist/ e reescrever para URL absoluta
    missing = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "latex.codecogs" in src or src.startswith(("http://", "https://")):
            continue
        new = publish_image(src)
        if new is None:
            missing.append(src)
        else:
            img["src"] = new
            
        if not img.get("alt"):
            fig = img.find_parent("figure")
            cap = fig.find("figcaption").get_text(" ", strip=True) if fig and fig.find("figcaption") else ""
            img["alt"] = cap
    
    for fig in soup.find_all("figure"):
        fc = fig.find("figcaption")
        if fc and fc.get_text(strip=True):
            legenda_texto = fc.get_text(" ", strip=True)
            p_legenda = soup.new_tag("p")
            em_legenda = soup.new_tag("em")
            em_legenda.string = legenda_texto
            p_legenda.append(em_legenda)
            # Insere o <p><em> logo após a figure e remove o figcaption problemático
            fig.insert_after(p_legenda)
            fc.decompose()
        
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        h.attrs.pop("id", None)
        h.attrs.pop("class", None)
    # <li><p>x</p></li> -> <li>x</li> (listas "soltas" do pandoc; o Medium prefere simples)
    for li in soup.find_all("li"):
        kids = [c for c in li.children if getattr(c, "name", None) or str(c).strip()]
        if len(kids) == 1 and getattr(kids[0], "name", None) == "p":
            kids[0].unwrap()

    BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "figure",
             "figcaption", "blockquote", "div", "table", "pre", "hr"}

    def blockish(n):
        return n is None or (getattr(n, "name", None) in BLOCK) or (
            getattr(n, "name", None) == "img" and n.parent.name == "figure")

    for t in list(soup.find_all(string=True)):
        if not t.strip() and t.find_parent(["pre", "code"]) is None \
                and blockish(t.previous_sibling) and blockish(t.next_sibling):
            t.extract()
            
    # Remove qualquer título ou parágrafo que contenha apenas espaços em branco ou invisíveis.
    for empty in soup.find_all(["h1", "h2", "h3"]):
        if not empty.find(["img", "br"]) and not re.sub(r'\s+', '', empty.get_text()):
            empty.decompose()
            
            
    content = "".join(str(c) for c in soup.body.contents).strip()

    cover_url = publish_image(meta["capa"]) if meta.get("capa") else None
    cover = (f'<figure class="capa"><img src="{cover_url}" alt="{html.escape(title)}"></figure>'
             if cover_url else "")
    og_image = f'<meta property="og:image" content="{cover_url}">' if cover_url else ""
    tags = "\n".join(f'<meta property="article:tag" content="{html.escape(t)}">'
                     for t in meta.get("tags", []))
    edicao = f" · Edição {html.escape(str(meta['edicao']))}" if meta.get("edicao") else ""
    download = (f'<p class="download"><a href="{meta["pdf"]}">Baixar a edição em PDF</a></p>'
                if meta.get("pdf") else "")

    # Crédito de autoria: parágrafo simples em itálico, SEM classe/rel/itemprop de "autor".
    # Importadores tratam isso como metadado e o removem; e o Medium mostra o dono da conta
    # como autor, então o crédito da equipe precisa estar no corpo do texto.
    credit = f'<p><em class="markup--em markup--p--em">Por {html.escape(author)}{edicao}</em></p>'
    article = "".join([f"<h1>{html.escape(title)}</h1>", credit, cover, content, download])
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
    """Checagens de 'pronto para importar no Medium'. Devolve [(nível, mensagem)]."""
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
    has_og = bool(soup.find("meta", property="og:image"))
    add("OK" if has_og else "AVISO", "og:image (capa) presente" if has_og
        else "sem og:image (defina 'capa' no meta.yml)")
    if entry["_skipped"]:
        add("ERRO", "conteúdo DESCARTADO pelo pandoc (macro sem definição em html/shim.tex): "
                    + ", ".join(sorted(set(entry["_skipped"]))))
    else:
        add("OK", "nenhuma macro descartada")
    if entry["_missing_images"]:
        add("ERRO", f"imagens não encontradas: {entry['_missing_images']}")
    else:
        add("OK", "todas as imagens locais foram resolvidas")
    imgs = art.find_all("img")
    no_alt = [i for i in imgs if not i.get("alt")]
    add("OK" if not no_alt else "AVISO", f"{len(imgs)} imagem(ns); sem alt: {len(no_alt)}")
    math = [i for i in imgs if "latex.codecogs" in i.get("src", "")]
    add("OK" if not math else "AVISO",
        "sem fórmulas" if not math else
        f"{len(math)} fórmula(s) viram imagem via codecogs (o Medium não tem matemática); "
        "confira se o importador as baixa")
    leftover_divs = sorted({c for d in art.find_all("div") for c in d.get("class", [])})
    add("OK" if not leftover_divs else "AVISO",
        "todos os ambientes mapeados" if not leftover_divs else
        f"ambiente(s) sem mapeamento em html/shim.tex (texto mantido, estilo perdido): {leftover_divs}")
    sus = art.find_all(class_=re.compile(r"byline|author|dateline", re.I)) + \
          art.find_all(attrs={"rel": "author"}) + art.find_all(attrs={"itemprop": re.compile("author")})
    add("OK" if not sus else "AVISO", "crédito de autoria no corpo, sem marcação de 'autor'" if not sus
        else "elemento(s) marcados como autor/byline: importadores costumam removê-los")
    art_nopre = re.sub(r"<pre.*?</pre>", "", str(art), flags=re.S)
    n_ws = len(re.findall(r">\s+<", art_nopre))
    add("OK" if n_ws == 0 else "AVISO", "HTML compacto (sem espaços entre blocos)" if n_ws == 0
        else f"{n_ws} espaço(s)/quebra(s) entre blocos — podem virar parágrafos vazios")
    bq_p = [b for b in art.find_all("blockquote") if b.find("p")]
    add("OK" if not bq_p else "AVISO", "citações com texto direto" if not bq_p
        else f"{len(bq_p)} citação(ões) com <p> interno")
    tables = art.find_all("table")
    add("OK" if not tables else "AVISO",
        "sem tabelas" if not tables else f"{len(tables)} tabela(s) — Medium não suporta; use imagem")
    resid = re.findall(r"\\[a-zA-Z]+", art.get_text(" "))
    add("OK" if not resid else "ERRO",
        "sem LaTeX residual no texto" if not resid else f"LaTeX residual: {sorted(set(resid))}")
    if not base_url.startswith("https://") or "localhost" in base_url or "USUARIO" in base_url:
        add("AVISO", f"base-url '{base_url}' não é pública: o Medium não consegue importar")
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
