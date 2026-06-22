# Morsa Digital Autoposter — Guia para Claude

## O que é esse projeto

Autoposter de cultura pop/nerd/geek para @morsadigital no Instagram. Foco em filmes, séries, animes, doramas e games. Tom: fã apaixonado + jornalista, não robô corporativo.

**Contas:**
- Instagram: @morsadigital (IG_USER_ID=17841405897887153)
- Facebook Page ID: 108393784135641
- Meta App ID: 1309470283986322 (app "Morsa Digital", Consumer type)
- Tudo é @morsadigital — nunca confundir com @tuliogama ou @ordemsithbrasil

**Twitter: SKIP** — conta com erro 402, nunca tente postar lá.

---

## Workflow padrão (toda sessão)

### 1. Checar estado atual
```bash
# Ver posts recentes e métricas
python3 -c "
import sys; sys.path.insert(0, 'src')
from posts_log import get_recent_posts
import json
posts = get_recent_posts(limit=10)
for p in posts:
    m = p.get('metrics', {})
    print(f\"{p['published_at'][:10]} | L:{m.get('likes','?')} C:{m.get('comments','?')} S:{m.get('saved','?')} | {p['title'][:60]}\")
"

# Atualizar métricas dos últimos 7 dias (requer instagram_manage_insights)
cd src && python3 -m metrics_analyzer
```

### 2. Antes de publicar qualquer post
- Sempre checar `posts_log.py:is_duplicate()` antes de selecionar notícia
- O publisher já chama `is_duplicate` automaticamente via `main.py`
- Para scripts ad-hoc, lembrar de verificar manualmente

### 3. Publicar post
```bash
# Fluxo normal (GitHub Actions roda automaticamente 6x/dia)
cd /Users/tuliogama/morsa-digital-autoposter
source .env.secrets && export $(cat .env.secrets | grep -v '#' | xargs)
python3 src/main.py --platforms instagram

# Batch catch-up (quando houve gap de posts)
python3 batch_catchup.py
```

### 4. Após publicar — registrar aprendizados
Atualizar a seção "O que funciona" abaixo com observações reais.

---

## Análise de performance (fazer mensalmente)

```python
# Pegar relatório de performance
import sys; sys.path.insert(0, 'src')
from metrics_analyzer import performance_report
print(performance_report())
```

**Padrões a observar:**
- Qual tipo de hook gera mais engajamento (afirmação ousada vs pergunta vs dado)
- Quais franquias performam melhor (Marvel, anime, games nacionais)
- Melhor horário de publicação (comparar `published_at` com likes/reach)
- Posts com mais "salvos" = conteúdo de valor, replicar formato

---

## Análise de concorrentes e tendências

```bash
# Feeds RSS já cobrem as principais fontes. Para tendências adicionais:
# 1. IGN Brasil + Cinema com Rapadura = fontes BR prioritárias
# 2. Kotaku + IGN + ComicBook = cobertura internacional
# 3. Verificar trending hashtags manualmente no Instagram antes de grandes posts

# Para checar o que está em alta hoje:
python3 -c "
import sys; sys.path.insert(0, 'src')
from news_fetcher import fetch_all_news
news = fetch_all_news(limit=30)
for n in news[:15]:
    print(f\"[{n['source']}] {n['title']}\")
"
```

**Concorrentes para monitorar (manualmente):**
- @omelete — maior canal nerd BR
- @jovemnerd — podcast/portal geek
- @cinemascomrapadura — filmes
- @geekpublishing — quadrinhos/cultura geek

Observar: formatos que geram muito engajamento neles para adaptar (nunca copiar).

---

## O que funciona — dados reais (análise jun/2026, 50 posts, 27k seguidores)

### Performance por categoria (análise 200 posts, jun/2026)
| Categoria | Avg likes | Notas |
|---|---|---|
| DC (Batman, Superman) | 144 | **PRIORIDADE MÁXIMA** |
| Marvel/Avengers/Spider-Man | 46 | **PRIORIDADE MÁXIMA** |
| Filmes blockbuster (Pixar, Disney) | 32 | bom potencial |
| Star Wars | 26 | consistente |
| Séries (Stranger Things, The Boys) | 19 | só grandes nomes |
| Games grandes (GoW, Zelda, GTA, CoD, FF) | 14 | só franquias top |
| Anime mainstream (OP, JJK, DBS) | 13 | só os grandes |
| Games nichê internacional | 3–4 | **NUNCA postar** |
| Tech/gadgets/IA | 1–2 | **off-brand, NUNCA** |

### Horários que mais engajam (BRT) — análise real 200 posts
- **18h**: 243 avg likes — **MELHOR JANELA**
- **21h**: 116 avg likes — **2ª MELHOR**
- 10h: 62 avg likes
- 09h: 46 avg likes
- 08h, 12h–15h: abaixo de 20 avg — evitar

### Tipos de post
- **VIDEO/Reel**: 5.589 avg likes — dominante absoluto
- CAROUSEL: 36 avg likes — 3x melhor que imagem
- IMAGE: 13 avg likes — formato mais fraco

### Captions que engajam
- Hook: **afirmação direta com o nome da franquia** — o fã precisa ver o personagem/franquia no 1º segundo
- Opinião ousada supera fato neutro: "isso é preguiça criativa" > "X lançou Y"
- Sem emoji no início — parece bot e prejudica alcance
- Hashtags específicas da franquia, nunca genéricas (#Marvel não #Filmes)
- CTA variado — nunca repetir o mesmo chamado à ação dois posts seguidos

### Conteúdo que performa bem
- Marvel/DC com qualquer novidade real (trailer, confirmação, polêmica)
- Notícias de animes populares **com grande base BR**: One Piece, JJK, Demon Slayer, Dragon Ball, Bleach
- Games com fandom consolidado: God of War, Zelda, GTA, Elden Ring, Call of Duty
- Polêmicas da indústria (Rockstar, cancelamentos, brigas de estúdio)
- Conteúdo brasileiro com novidade real (Irmão do Jorel, games indie nacionais)

### Evitar
- **Gizmodo-style tech**: celulares, laptops, gadgets, IA, robôs domésticos, promoções de produto
- Anime muito nichê sem base no Brasil (verificar se tem > 100k fãs BR antes)
- Séries antigas sem hype atual (Stargate, Battlestar, Babylon 5)
- Posts sobre celebridades sem relação com cultura pop nerd/geek
- Mesmo formato de hook em posts consecutivos
- Começar legenda com emoji (parece bot)
- Emojis no início de cada parágrafo
- Hashtags genéricas (#Filmes, #Games, #Animes, #MundoNerd)

---

## Curadoria editorial — garantia de especificidade (jun/2026)

Problema histórico: o título prometia (lista "7 heróis…", "anime ganha data de estreia") e o corpo entregava genérico, porque a `description` do RSS é só um teaser de 300 chars. Posts vendendo "serviço da Morsa" também vazavam.

Correções implementadas (`news_fetcher.py` + `content_generator.py`):
1. **Enriquecimento de fonte** — `fetch_article_text(url)` busca o corpo real do artigo quando a descrição é fina (<220 chars) ou o título promete lista/data. Dá dados reais ao modelo.
2. **Gate de verificação** — `_verify_specificity()` roda após gerar e PULA o post se:
   - título é lista numerada e o corpo não nomeia os itens (mín. 3 nomes), ou usa enchimento ("vários", "entre outros");
   - título promete estreia/data e o corpo não traz data concreta (dia/mês ou mês/ano);
   - há linguagem de venda/serviço em 1ª pessoa.
3. **Bloqueio na fonte** — `BLOCK_KEYWORDS` agora barra conteúdo promocional/publieditorial/assinatura.
4. **Prompt** — regra absoluta: Morsa só NOTICIA, nunca vende; lista sem nomes ou estreia sem data → modelo responde `PULAR` e o post é descartado.

Resultado: posts de lista/estreia só saem quando entregam os nomes/datas. Posts pulados não contam como falha — `main.py` tenta o próximo candidato (por isso `candidates_count = posts_per_run * 4`).

## Hashtags, curadoria e dedup (jun/2026)

- **Hashtags**: `_cap_hashtags()` corta para no máximo 8 (modelo despejava 15-20). Aplicado em `generate_post` antes de retornar.
- **Curadoria anti-nichê**: `_categorize()` + `_rerank_for_diversity()` em `content_generator.py` rebaixam games nichê (MMORPG indie, sim de fábrica — 3-4 likes) para o fim e impedem 3 posts da mesma categoria em sequência. Franquia grande (GTA, VALORANT, Zelda…) basta para classificar como `game_big`.
- **Dedup no mesmo run**: `is_duplicate()` só checa o log histórico; duas notícias do mesmo evento de fontes/idiomas diferentes entram juntas (o log ainda não tem nenhuma) → publicavam em dobro (caso Leviatán). `main.py` agora mantém `run_keywords`/`run_urls` e barra o 2º via overlap de palavras-chave (threshold 2). O `select_best_news` também é instruído a nunca escolher a mesma notícia de 2 fontes.

## Tokens — validade

- **PAT local do `gh`** (`ghp_…`, usado para upload de Reels manuais via GitHub Releases): é **classic PAT com expiração**. Checar com `gh api -i /user | grep -i token-expiration`. Quando expirar: gerar novo em github.com/settings/tokens (escopos `repo` + `workflow`) e `gh auth login`. **Expira 2026-06-28.**
- **Auto-post diário no GitHub Actions** usa `secrets.GITHUB_TOKEN` (automático, renovado a cada run) — não expira, independente do PAT local.

## Infraestrutura técnica

### Arquivos importantes
- `src/main.py` — entry point principal
- `src/news_fetcher.py` — RSS feeds nerd/geek/pop
- `src/content_generator.py` — geração de captions com Claude Haiku
- `src/image_generator.py` — imagem 4:5 1080x1350 com logo (Pillow + Imgur)
- `src/publishers/instagram.py` — publicação via Graph API
- `src/posts_log.py` — **memória persistente de posts publicados**
- `src/metrics_analyzer.py` — análise de engajamento via Insights API
- `batch_catchup.py` — recuperar gap de posts sem duplicar
- `logs/posts_log.json` — banco de dados de todos os posts
- `.github/workflows/auto-post.yml` — 6x/dia no GitHub Actions (sem MacBook)
- `.env.secrets` — chaves locais (NUNCA commitar)

### Credenciais
- `ANTHROPIC_API_KEY` — Claude Haiku para geração de conteúdo
- `FB_ACCESS_TOKEN` — Page Access Token permanente (não expira) — atualizar GitHub Secret ao renovar
- `IG_USER_ID=17841405897887153`
- `FB_PAGE_ID=108393784135641`

### Token permanente
Page Access Token (expires_at=0 = permanente) derivado de:
1. User token curto → long-lived (60d): `GET /oauth/access_token?grant_type=fb_exchange_token`
2. Long-lived → page token permanente: `GET /me/accounts`
O page token não expira enquanto a senha não mudar.

### Permissões que FALTAM (a adicionar no app Meta)
- `instagram_manage_insights` — para buscar métricas via API (hoje: manual)
- `instagram_manage_comments` — para desabilitar likes via API após publicar
  - **Workaround atual**: `like_and_view_counts_disabled=true` no container de criação (pode não funcionar sem a permissão)
  - **Ação manual**: desabilitar likes nos posts pelo app do Instagram enquanto não temos a permissão

### Facebook
- Atualmente PAUSADO — app é Consumer type, sem `pages_manage_posts`
- Para ativar: criar novo app Business type no Meta Developer
  - Usar caso de uso "Manage everything on your Page"
  - Gerar System User token (nunca expira, independe do usuário)

### GitHub Actions — agenda atual (jun/2026, BRT)
Baseada nos dados reais de performance. Horários em BRT (cron em UTC = +3):
- **Feed (imagem)**: 09h, 10h, 18h, 21h — `POSTS_PER_RUN=2` → **8 posts/dia**
- **Carrossel**: 10h30 (eleva a manhã) + 18h30 (pico) → **2/dia**
- **Reel**: 18h **diário** — usa o cron 0 21 * * * do feed (job casa via `if`); fonte = `data/trailer_backlog.json` + fallback RSS de trailers
- **Estreia Hoje**: 09h — só publica se algum filme/série estreia no dia
- Plataforma padrão: `instagram`
- Secret `FB_ACCESS_TOKEN` precisa ser atualizado via `gh secret set FB_ACCESS_TOKEN`
- **Manutenção**: reabastecer `data/trailer_backlog.json` regularmente — com reel diário, o backlog esvazia e passa a depender do RSS. Backlog vazio + sem trailer no RSS no dia = reel não publica (falha graciosa, nunca inventa).

---

## Checklist antes de qualquer publicação manual

- [ ] `source .env.secrets && export $(cat .env.secrets | grep -v '#' | xargs)`
- [ ] Verificar que não é duplicata (`posts_log.py`)
- [ ] Confirmar que a imagem foi gerada (não placeholder)
- [ ] Conferir que `like_and_view_counts_disabled=true` foi enviado
- [ ] Após publicar: checar o post no app do Instagram para desabilitar likes manualmente se necessário

---

## Self-improvement loop (mensal)

1. `python3 -m metrics_analyzer` → atualizar métricas
2. `performance_report()` → identificar top posts
3. Analisar padrões: qual fonte, qual tipo de hook, qual franquia
4. Atualizar seção "O que funciona" acima
5. Se necessário, ajustar prompts em `content_generator.py`
6. Checar feeds em `news_fetcher.py` — feeds mortos quebram silenciosamente
7. Monitorar concorrentes para novas tendências de formato
