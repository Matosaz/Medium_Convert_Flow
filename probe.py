#!/usr/bin/env python3
"""
Sonda do importador do Medium: gera UMA página com variantes de cada construção HTML
(crédito de autoria, legenda de imagem, caixas, títulos, fórmulas), cada uma marcada com
um código único (A1, B2, C3...). Importe a página no Medium e anote quais códigos sobrevivem.

Uso:
  python probe.py --out dist --base-url https://usuario.github.io/repo
Saída: <out>/probe/index.html  (+ <out>/probe/img/probe.png)
Sem dependências além da biblioteca padrão.
"""
import argparse, struct, zlib
from pathlib import Path

def make_png(path: Path, w=640, h=260):
    """PNG simples (faixas roxa/laranja com moldura branca), só com stdlib."""
    purple, orange, white = (138, 92, 245), (255, 107, 26), (255, 255, 255)
    rows = bytearray()
    for y in range(h):
        rows.append(0)                                   # filtro "None"
        for x in range(w):
            border = x < 8 or x >= w - 8 or y < 8 or y >= h - 8
            band = (x // 80 + y // 65) % 2 == 0
            rows += bytes(white if border else (purple if band else orange))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)

def build(img: str, url: str) -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Sondagem do importador do Medium</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{url}">
</head>
<body>
<article><h1>Sondagem do importador do Medium</h1><p><em>Por Equipe Hype (A1)</em></p><p>Texto: Equipe Hype (A2)</p><p>Parágrafo de controle (CTRL1): este texto comum deve sempre aparecer.</p><h2>Bloco A: crédito de autoria</h2><p>Mesmo formato de A1, mas no meio do texto:</p><p><em>Por Equipe Hype (A3)</em></p><p>Sem a palavra "Por":</p><p><em>Equipe Hype, autoria (A4)</em></p><p>Com rótulo em negrito:</p><p><strong>Autoria:</strong> Equipe Hype (A5)</p><p>No fim do texto:</p><p>— Equipe Hype (A6)</p><h2>Bloco B: imagem e legenda</h2><p>B1: figure + figcaption</p><figure><img src="{img}" alt="texto alternativo B1"><figcaption>Legenda B1 (figcaption)</figcaption></figure><p>B2: figure sem figcaption, legenda em itálico no parágrafo seguinte</p><figure><img src="{img}" alt="texto alternativo B2"></figure><p><em>Legenda B2 (parágrafo em itálico)</em></p><p>B3: imagem solta em parágrafo, legenda em itálico no seguinte</p><p><img src="{img}" alt="texto alternativo B3"></p><p><em>Legenda B3 (parágrafo em itálico)</em></p><p>B4: só o atributo alt (sem legenda visível)</p><p><img src="{img}" alt="Legenda B4 (somente alt)"></p><p>B5: legenda na mesma linha, após quebra</p><p><img src="{img}" alt="texto alternativo B5"><br><em>Legenda B5 (após br)</em></p><h2>Bloco C: caixas</h2><p>C1: blockquote com texto direto</p><blockquote>Caixa C1: texto direto dentro do blockquote.</blockquote><p>C2: blockquote com parágrafo interno</p><blockquote><p>Caixa C2: texto dentro de p dentro do blockquote.</p></blockquote><p>C3: blockquote com dois parágrafos</p><blockquote><p>Caixa C3a: primeiro parágrafo.</p><p>Caixa C3b: segundo parágrafo.</p></blockquote><p>C4: blockquote com rótulo em negrito</p><blockquote><strong>Título C4.</strong> Corpo da caixa C4 logo após o rótulo.</blockquote><p>C5: dois blockquotes consecutivos, sem separador</p><blockquote>Caixa C5a.</blockquote><blockquote>Caixa C5b.</blockquote><p>C6: dois blockquotes separados por hr</p><blockquote>Caixa C6a.</blockquote><hr><blockquote>Caixa C6b.</blockquote><p>C7: bloco de código como caixa</p><pre>Caixa C7: texto em bloco pre.</pre><p>C8: parágrafo com emoji como marcador de cor</p><p>🟣 Caixa C8: parágrafo com marcador roxo.</p><p>🟠 Caixa C8b: parágrafo com marcador laranja.</p><h2>Bloco D: espaço após títulos</h2><h2>Título D1 (HTML compacto)</h2><p>Parágrafo logo após D1.</p><h2>Título D2 (com quebra de linha)</h2>
<p>Parágrafo logo após D2.</p><h3>Título D3 (nível h3)</h3><p>Parágrafo logo após D3.</p><h2>Bloco E: fórmulas</h2><p>E1: em código: <code>E = mc^2 (E1)</code></p><p>E2: imagem do codecogs: <img src="https://latex.codecogs.com/png.latex?E%20%3D%20mc%5E2" alt="E = mc^2 (E2)"></p><p>E3: Unicode: E = mc² (E3)</p><p>Fim da sondagem (CTRL2): este texto comum deve sempre aparecer.</p></article>
</body>
</html>
"""

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("dist"))
    ap.add_argument("--base-url", default="https://USUARIO.github.io/REPO")
    a = ap.parse_args()
    d = a.out / "probe"
    (d / "img").mkdir(parents=True, exist_ok=True)
    make_png(d / "img" / "probe.png")
    url = f"{a.base_url.rstrip('/')}/probe/"
    (d / "index.html").write_text(build(f"{url}img/probe.png", url), encoding="utf-8")
    print(f"sonda gerada -> {url}")

if __name__ == "__main__":
    main()