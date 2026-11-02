# Fluxo de teste: LaTeX → HTML → Medium

Valida se um artigo escrito com as macros do template **Tá no Hype** pode virar uma
página web que o **Import a story** do Medium consiga importar, mantendo o essencial.

```
artigo.tex ──pandoc + shim──▶ HTML limpo ──GitHub Pages──▶ URL pública ──(manual)──▶ Medium
     └────────xelatex──────▶ PDF da newsletter   (mesma fonte)
```

## O que há aqui

| Caminho | Função |
|---|---|
| `articles/<slug>/artigo.tex` | Artigo com `\hypearticle`, `\subtitle`, `\highlight`, `\articleimage`, `infobox`, `hypeitemize`, `\originalsource` |
| `articles/<slug>/meta.yml` | O que não está no `.tex`: descrição, capa, tags, edição, `pdf`, `medium_url` |
| `html/shim.tex` | Traduz cada macro Hype para LaTeX padrão (só para a conversão web) |
| `build_html.py` | Converte, copia imagens, reescreve URLs, gera `artigos.json` e **verifica** o resultado |
| `stub/main.tex` | Compila o mesmo `.tex` em PDF com macros mínimas (prova de fonte única) |
| `.github/workflows/pages.yml` | Publica `dist/` no GitHub Pages |

Título e autor vêm do próprio `\hypearticle` (fonte única); o `meta.yml` só guarda o restante.

## Rodar localmente

```bash
pip install -r requirements.txt   # + pandoc instalado
python build_html.py              # converte e verifica tudo em articles/
python build_html.py --base-url https://SEU-USUARIO.github.io/SEU-REPO
```

O script sai com código 1 se houver **ERRO** (útil no CI). **AVISO** não bloqueia, mas é algo a olhar.

PDF do harness: `cd stub && latexmk -xelatex -outdir=build main.tex`

## Executar o teste de viabilidade

1. Crie um repositório **público** de teste (Pages gratuito exige repo público; o Medium também precisa de URL pública) e envie esta pasta.
2. Em *Settings → Pages → Source*, escolha **GitHub Actions**. Faça um push e aguarde o workflow.
3. Abra `https://<usuario>.github.io/<repo>/artigos/teste-fluxo/` e confirme que a página carrega com as imagens.
4. No Medium, com a conta (idealmente a institucional): *Stories → Import a story* e cole a URL acima.
5. Preencha a tabela abaixo olhando o rascunho importado.

### Resultado do teste (preencher)

| Item | Esperado | Resultado |
|---|---|---|
| Título | Igual ao `\hypearticle` | |
| Subtítulos | `\subtitle` vira cabeçalho | |
| Capa/imagem da figura | Baixadas e exibidas | |
| Legenda da figura | Mantida | |
| Lista | 4 itens | |
| `\highlight` / `infobox` | Citação (a infobox perde a cor) | |
| Fórmula `E = mc²` | Imagem (ou perda) | |
| Canonical | Aponta para a URL do site (ver em *Advanced settings* e no código-fonte da página publicada) | |
| Data | Data original | |
| Link "Fonte original" | Clicável | |

**Critério de aprovação sugerido:** título, hierarquia, imagens, lista, citações e canonical corretos
sem retrabalho; fórmula e legenda podem exigir ajuste manual.

## Limitações conhecidas

- **A importação é manual.** O Medium não aceita novas chaves de API; este fluxo automatiza tudo *até* a URL.
- O Medium tem só dois níveis de título, sem tabelas nem matemática. O verificador avisa sobre `h3+`, tabelas e fórmulas.
- Fórmulas viram imagens via codecogs (serviço externo). Se o teste mostrar que o importador as perde, o caminho é pré-renderizar localmente.
- `\hypearticle` recebe o corpo como argumento, então `verbatim` não funciona dentro dele (limitação do LaTeX, também no PDF).
- **Macro sem entrada em `html/shim.tex` é descartada pelo pandoc junto com o argumento.** O verificador acusa como ERRO; mapeie-a no shim.
- Cores no CSS (`--hype-orange`, `--hype-purple`) são aproximações: ajuste para os hex reais.

## Levar para o repositório real

Copie `build_html.py`, `html/`, `requirements.txt` e o workflow. Aponte o script para as pastas
`editions/*/sections/artigoN/` (ele aceita caminhos: `python build_html.py editions/2025-09/sections/artigo1`)
e adicione um `meta.yml` por artigo. O `shim.tex` precisa refletir as assinaturas **reais** de
`shared/styles/macros.tex`, pois aqui foram assumidas a partir do README.
"# Medium_Convert_Flow" 
