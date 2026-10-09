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

## Prioridade por categoria e cota de GTA (out/2026)

Análise de 200 posts (ago-out/2026), mediana de likes: DC 11 · Marvel 8 · anime 8 ·
GTA 6 · Star Wars 5 · outros games 5. Média engana (um post de 302 likes distorce);
usar mediana. Os "picos" de horário 05h/07h eram outliers, não mexer na agenda por eles.
- `_CATEGORY_TIER` em `content_generator.py` ordena os candidatos; o Groq só ordena
  dentro do tier. Repetir categoria no dia custa prioridade; `game_niche` só entra
  se faltar pauta. Antes, o Groq via só os 20 primeiros itens (feeds BR de games) e
  games viraram 47% dos posts.
- **Cota de GTA**: `main.py` checa no Instagram o que já saiu hoje (BRT); sem GTA no
  dia, `fetch_gta_news()` (feeds gerais sem teto + `GTA_RSS_FEEDS`) vai na frente da
  fila. Máximo 1 GTA por run.

## Agenda real, portão de slots e revisão noturna (out/2026)

- **Cron do GitHub atrasa ~5h** e o watchdog antigo tinha bug (hora "08"/"09" virava
  octal e disparava post extra). Resultado: 5 posts/dia, vários às 03h-05h BRT.
- **`src/slot_gate.py`** é a regra única: publica se slots vencidos hoje (11h, 16h,
  21h BRT, env `FEED_SLOTS_BRT`) > posts de feed de hoje, com 90 min de intervalo.
  Crons e watchdog são só gatilhos. Disparo manual publica na hora (`gate=false`).
- **Revisão noturna** (`src/daily_review.py`, workflow `daily-review.yml`, 22h BRT):
  grava `data/learned_weights.json` (categoria sobe/desce um degrau, n≥5, mediana
  ≥1,4× ou ≤0,6× a geral), `logs/day_brief.json` (orientação de amanhã) e o
  relatório em `data/daily_review/`. Desde 06/10/2026 o token tem
  `instagram_manage_insights`: nota = curtidas+comentários+salvos+compartilhamentos,
  e o relatório traz alcance (mediana de 179 contas por post de feed, <1% dos 26k). O `cmo_brain.run_daily_analysis` antigo não roda mais.
- **Reels**: só canal oficial (`_is_official`: ID conferido ou selo + nome de
  estúdio), crédito do canal sempre na legenda (`_with_credit`), legenda sempre
  nossa, nunca a descrição do YouTube.

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
- **Feed (imagem)**: 10h, 18h, 21h — `POSTS_PER_RUN=1` → **3 posts/dia** (reduzido de 8 em 22/jun: 8 imagens/dia estavam estrangulando o alcance — análise mostrou 6 avg likes, algoritmo sufocado)
- **Carrossel**: 10h30 (eleva a manhã) + 18h30 (pico) → **2/dia**
- **Estreia Hoje**: 09h — só publica se algum filme/série estreia no dia
- Plataforma padrão: `instagram`
- Secret `FB_ACCESS_TOKEN` precisa ser atualizado via `gh secret set FB_ACCESS_TOKEN`

### Reel — fila: Mac abastece, GitHub publica (out/2026)
O YouTube bloqueia o IP do GitHub ("confirme que não é um robô"; testado em
06/10/2026 com yt-dlp atual, com e sem cookies — cookies expiram em semanas).
Então o download é local e a publicação é do CI. Tudo em `src/reel_queue.py`.
- **Fonte**: só uploads recentes (RSS do YouTube) dos canais em `OFFICIAL_CHANNELS`,
  conferidos por ID + inscritos. Só adicionar canal por ID: `@dcbrasil` (3 inscritos)
  e `@UniversalPicturesBr` são falsos. Nada de busca livre, nada de corte de cena.
- **Mac** (`run_reel_local.sh`, launchd `com.morsa.dailyreel`, 8h30, 13h30 e 18h;
  até 10 vídeos por fluxo por execução, 70s de pausa, para o YouTube não bloquear): `fill` baixa,
  converte para 9:16 (fundo desfocado + logo, máx. 90s), sobe na Release
  `reel-queue` e grava `data/reel_queue.json` até ter 7 pendentes. Com a fila
  cheia o Mac pode ficar dias desligado. yt-dlp SEM cookies (com cookies do Chrome
  o YouTube serve "only images"; foi o que zerou os reels de ago a out/2026) e
  sempre atualizado (`brew upgrade yt-dlp` no script: versão velha dá 403).
- **Dois fluxos, 1 reel/dia cada** (`STREAMS` em `reel_queue.py`):
  - `cenas`, 11h: cenas, clipes e bastidores de canais oficiais com legenda de
    pergunta ao fã (`HOOK_SYSTEM`). É o formato dos maiores reels da conta: os 8
    maiores (436 mil a 1,2 mi de alcance, 2025) eram cena/nostalgia/opinião, nenhum
    trailer. Plano em `data/reel_plan_cenas.json`, fila em `reel_queue_cenas.json`.
  - `main`, 13h: trailers. Ordem: fixo do dia (`scheduled_for`: Halloween, Natal,
    contagem GTA VI) → lançamento novo (`fill`) → acervo (`data/reel_plan.json`).
  - Horário: em 184 reels de nov/24 a out/25, 11h-13h deu 1,2x a mediana do mês;
    17h-19h, 0,6x. Feed estático foi para 9h/16h/21h para não colidir.
- **Português e vertical primeiro** (pedido do Tulio, 06/10/2026: reel em inglês
  com faixas desfocadas não serve). Fonte preferida: Shorts dos canais oficiais
  BRASILEIROS (aba /shorts; vertical nativo, dublado ou legendado na origem).
  Canal estrangeiro só entra com legenda OFICIAL em PT, queimada no vídeo com
  Pillow (o ffmpeg do Homebrew não tem drawtext/libass). Exceção: Rockstar, que
  não tem versão PT. Horizontal vira 9:16 com fundo desfocado só como último caso.
- **TikTok** (@morsadigital, 103 seguidores em 09/10/2026): `publishers/tiktok.py`
  publica via Zernio (ex-Late; app já auditado pelo TikTok, grátis até 2 contas,
  chave em `ZERNIO_API_KEY`). A API oficial não serve: app não auditado só posta
  privado e a auditoria recusa ferramenta de uso interno. Cada reel que sai no
  Instagram vai junto para o TikTok; sem a chave, é no-op.
- **Auditoria** (`reel_queue.py audit`, roda no fim de `run_reel_local.sh`): confere
  os arquivos, gera a legenda dos próximos 6 dias e passa por `lint_caption` (regras
  fixas) e `judge_caption` (gpt-oss-120b aponta detalhe inventado). Legenda aprovada
  fica no item (`caption`) e é a que o CI publica. Calendário e legendas em
  `data/reel_report.md`.
- **Molde do prompt na legenda** (07/10/2026, post das 9h10 foi ao ar com
  "[HOOK, 1 a 2 linhas...]" e "[linha em branco]"): o modelo reserva copiou as
  instruções entre colchetes. Três barreiras em `content_generator.py` e
  `publishers/instagram.py`: `_strip_template_echo` limpa, `has_template_echo`
  descarta a resposta e tenta o próximo modelo, e `_clean_caption` cancela a
  publicação em qualquer caminho (feed, reel, estreia). Ao trocar de modelo,
  SEMPRE gerar e ler legendas reais antes de pôr em produção.
- **Cota da Groq**: 200 mil tokens/dia POR MODELO. Em 07/10/2026 a auditoria da
  madrugada gastou tudo do qwen (1.186 chamadas falhas) e quase derrubou o feed do
  dia. Hoje: auditoria limitada a 4 legendas por fluxo por execução, e
  `_call_groq_fallback` cai para gpt-oss-120b/20b no 429. Nunca rodar geração em
  massa de legenda.
- **CI** (`reel-queue.yml` + watchdog): `publish` olha os dois fluxos, 90 min de
  intervalo entre reels, legenda nossa (fatos = descrição oficial; vídeo com +60
  dias é relembrança) e crédito do canal. `premap` baixa o que faltar dos planos.
  Para acrescentar reels: pôr o ID no plano e rodar `premap` no Mac.
- `editorial.run_reel` e `data/trailer_backlog.json` são o fluxo antigo, sem uso.

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
