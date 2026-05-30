# Morsa Digital — Bíblia de Conteúdo e Checklist Obrigatório

> Este documento define as regras inegociáveis do @morsadigital no Instagram.
> O pipeline segue este checklist antes de cada post, sem exceção.

---

## 1. IDENTIDADE DA CONTA

**@morsadigital** é um perfil brasileiro de cultura pop/nerd/geek.

**Tom de voz:** fã apaixonado + jornalista. Direto, opinativo, humano — nunca corporativo, nunca bot.

**Temas permitidos:**
- Filmes e séries (Marvel, DC, Star Wars, Disney, A24, streaming)
- Animes e mangás (One Piece, Demon Slayer, Jujutsu Kaisen, Dragon Ball, Naruto, etc.)
- Games (Nintendo, PlayStation, Xbox, PC Gaming, Indies)
- Doramas e K-Drama
- Quadrinhos e cultura geek/nerd em geral

**Contas da operação:**
- Instagram: @morsadigital (`IG_USER_ID=17841405897887153`)
- Facebook Page ID: `108393784135641`
- ⚠️ NUNCA misturar com @tuliogama ou @ordemsithbrasil (projetos separados)
- ⚠️ Twitter/X: SKIP permanente — erro 402, nunca tentar

---

## 2. CHECKLIST OBRIGATÓRIO — PRÉ-PUBLICAÇÃO

Cada post passa por estes 8 pontos. Falhar em qualquer um = **pular para próxima notícia**.

### ✅ PONTO 1 — Fonte válida
- [ ] A notícia vem de um dos **13 feeds RSS autorizados** (ver Seção 4)
- [ ] Reddit: usado **APENAS como sinal de tendência** no CMO Brain — **NUNCA** como fonte de post
- [ ] Fonte removida da lista: Omelete (feed 404), Cinema com Rapadura (podcasts dominam o feed)

### ✅ PONTO 2 — Tipo de conteúdo permitido
- [ ] É notícia factual: trailer, lançamento, anúncio oficial, data confirmada, resultado
- [ ] **NÃO É** nenhum dos seguintes (rejeitar imediatamente):
  - Podcast ou episódio de podcast (RapaduraCast, NerdCast, etc.)
  - Lista genérica ("os melhores X de Y") sem novidade factual
  - Notícia de IA genérica / robótica / automação industrial
  - Finanças, crypto, NFT, investimentos
  - Política, eleições, governo
  - Clickbait sem fonte verificável ("vai acontecer?", "pode ser que...")
  - Celebridade sem ligação direta com cultura pop (ex: casamento de ator, saúde pessoal)
  - Conteúdo NSFW, violência explícita, suicídio, assédio

### ✅ PONTO 3 — Anti-duplicata (2 camadas obrigatórias)
- [ ] **Camada 1 — posts_log.json:** comparar título da notícia com últimos 20 posts publicados
  - Overlap de ≥ 2 palavras-chave com >3 letras = duplicata → rejeitar
  - Checar também nomes próprios (ex: "Marcia Lucas" = 2 palavras > 3 letras = bloqueia)
- [ ] **Camada 2 — Instagram API:** comparar com primeiras linhas das últimas 20 captions publicadas
  - Se o tema já foi coberto nos últimos 3 dias = rejeitar, mesmo título diferente
  - Exemplo: múltiplos artigos sobre a morte da Marcia Lucas → só o primeiro passa

### ✅ PONTO 4 — Imagem real obrigatória
- [ ] A notícia tem **imagem real do artigo** (og:image, twitter:image ou YouTube thumbnail)
- [ ] A imagem foi **processada**: redimensionada para **1080×1350px (4:5 vertical)**
- [ ] A imagem tem **logo Morsa Digital** no canto inferior direito
- [ ] A imagem foi **publicada em CDN público** (Imgur → catbox.moe como fallback)
- [ ] **PROIBIDO:** imagem horizontal, mockup com texto, fundo laranja com título, imagem sem logo
- [ ] Se não conseguir imagem com logo no formato certo → **pular para próxima notícia**

### ✅ PONTO 5 — Qualidade da legenda
- [ ] Começa com **hook direto** — sem emoji no início, sem "Olha só:", sem "Você sabia que?"
- [ ] Tem **corpo informativo** de 3–5 parágrafos curtos (max 150 palavras total)
- [ ] Tem **CTA variado** no final — nunca repetir o mesmo chamado em posts seguidos
- [ ] Tem **hashtags relevantes** (8–12) — mix de franquia + categoria + pt-BR
- [ ] Não começa parágrafo com emoji
- [ ] Não usa tom corporativo, formal ou "robô"

### ✅ PONTO 6 — Configuração técnica
- [ ] `like_and_view_counts_disabled=true` enviado na criação do container
- [ ] Post registrado em `logs/posts_log.json` imediatamente após publicação

### ✅ PONTO 7 — Sequência de publicação
1. Publicar no **Feed** (container → publish)
2. Tentar compartilhar nos **Stories** via `source_type=FEED_MEDIA` (fallback silencioso se falhar)
3. Registrar no log (`record_post`)

### ✅ PONTO 8 — Pós-publicação
- [ ] `posts_log.json` commitado no GitHub após cada run (para dedup cross-run)
- [ ] `day_brief.json` commitado junto (para continuidade da análise CMO)

---

## 3. CICLO CMO — ANÁLISE OBRIGATÓRIA ANTES DE CADA BATCH

A cada execução (6×/dia), **antes** de selecionar qualquer notícia:

1. **Métricas dos últimos 20 posts** — identificar o que engajou, o que não engajou
2. **Classificar hooks** — qual estilo de abertura está performando (pergunta? dado? afirmação?)
3. **Cobertura dos concorrentes** — o que IGN Brasil, GameBlast, AnimeUnited publicaram hoje
4. **Tendências Reddit** — o que está em alta nos subreddits relevantes (só para orientação, nunca para post direto)
5. **Day Brief** gerado por Claude — orientações estratégicas para o dia

O brief é salvo e reutilizado durante o dia. Reanálise completa apenas 1×/dia.

---

## 4. FONTES AUTORIZADAS (13 feeds RSS)

| # | Fonte | Idioma | Categoria |
|---|-------|--------|-----------|
| 1 | IGN Brasil | PT-BR | Games + Filmes |
| 2 | GameBlast | PT-BR | Games |
| 3 | AnimeUnited | PT-BR | Anime + Manga |
| 4 | IGN | EN | Games + Filmes |
| 5 | Kotaku | EN | Games |
| 6 | ComicBook | EN | Quadrinhos + MCU |
| 7 | Den of Geek | EN | Séries + Filmes + Geek |
| 8 | The Verge | EN | Tech + Cultura (filtrar palavras-chave) |
| 9 | Deadline | EN | Cinema (filtrar palavras-chave) |
| 10 | Variety | EN | Cinema (filtrar palavras-chave) |
| 11 | Anime News Network | EN | Anime + Manga |
| 12 | Eurogamer | EN | Games |
| 13 | Gizmodo | EN | Tech + Cultura (filtrar palavras-chave) |

**Removidos:** Omelete (feed 404), Cinema com Rapadura (podcast domina)
**Reddit:** nunca como fonte de post — só tendência para o CMO Brain

---

## 5. REGRAS DE IMAGEM — DETALHAMENTO TÉCNICO

```
OBRIGATÓRIO:
✅ Dimensões: 1080 × 1350px (formato 4:5 vertical)
✅ Logo Morsa Digital: canto inferior direito, tamanho 140px, halo escuro
✅ Gradiente escuro na parte inferior (facilita leitura de texto sobre a imagem)
✅ Imagem real do artigo (og:image, twitter:image ou YouTube thumbnail)
✅ Upload em CDN público (Imgur ou catbox.moe como fallback)

PROIBIDO:
❌ Imagem horizontal (16:9, 4:3, qualquer ratio diferente de 4:5)
❌ Mockup com texto gerado (fundo laranja + título em branco)
❌ Imagem sem logo Morsa Digital
❌ og:image raw sem processamento (sem redimensionamento e sem logo)
❌ Placeholder genérico
❌ Se não tem imagem real → post é pulado, próxima notícia
```

---

## 6. REGRAS DE LEGENDA — DETALHAMENTO

### Estrutura obrigatória:
```
[Hook — 1 frase forte, sem emoji no início]

[Parágrafo 1: contexto da notícia — o que é, de onde vem]

[Parágrafo 2: por que importa para o fã — conexão emocional ou cultural]

[Parágrafo 3 (opcional): dado extra, comparação, curiosidade]

[CTA — pergunta ou chamada para ação variada]

#hashtag1 #hashtag2 ... (8-12 hashtags)
```

### Tipos de hook que funcionam:
- **Anúncio direto:** "X foi confirmado para Y — e muda tudo."
- **Dado surpreendente:** "Depois de 13 anos, Call of Duty volta para Nintendo."
- **Afirmação provocativa:** "Fable foi adiado de novo e Xbox continua sem resposta."
- **Expectativa cumprida:** "A gente esperou 2 anos. One Piece finalmente confirmou."

### Proibido na legenda:
- ❌ Começar com emoji
- ❌ Começar parágrafo com emoji
- ❌ "Olha só:", "Sabia que?", "Incrível:", "Uau!"
- ❌ Tom de press release corporativo
- ❌ Repetir o mesmo CTA em posts consecutivos
- ❌ Mais de 12 hashtags

---

## 7. VOLUME E HORÁRIOS

**Target:** 12–18 posts/dia  
**Configuração:** 6 runs/dia × 3 posts/run = 18 máximo

| Run | Horário BRT | Posts |
|-----|-------------|-------|
| 1 | 08:00 | 3 |
| 2 | 10:30 | 3 |
| 3 | 13:00 | 3 |
| 4 | 16:00 | 3 |
| 5 | 19:00 | 3 |
| 6 | 21:30 | 3 |

---

## 8. FLUXO COMPLETO DE UMA RUN (passo a passo do sistema)

```
START
  │
  ▼
[1] CMO Brain
    ├── Busca últimos 20 posts IG (métricas)
    ├── Analisa hooks que engajaram
    ├── Verifica concorrentes (RSS)
    ├── Coleta trends Reddit (só leitura)
    └── Gera Day Brief com Claude → salva day_brief.json

  │
  ▼
[2] Busca de notícias
    └── 13 feeds RSS → filtra NSFW, podcast, política, clickbait → max 50 notícias

  │
  ▼
[3] Deduplicação (2 camadas)
    ├── Layer 1: posts_log.json — overlap título ≥ 2 palavras-chave
    └── Layer 2: Instagram API — primeiras linhas das últimas 20 captions

  │
  ▼
[4] Curadoria com Claude
    └── Seleciona top 12 candidatos (posts_per_run × 4) orientado pelo Day Brief

  │
  ▼
[5] Para cada candidato (até posts_per_run publicados):
    ├── Gera legenda com Claude Haiku
    ├── Busca og:image do artigo
    ├── Processa imagem: resize 1080×1350 + gradiente + logo Morsa
    ├── Upload Imgur → catbox.moe (fallback)
    ├── SE sem imagem processada com logo → PULAR, próximo candidato
    ├── Cria container IG (like_count_disabled=true)
    ├── Publica no Feed
    ├── Tenta Stories (feed post reshare)
    └── Registra em posts_log.json

  │
  ▼
[6] Commit posts_log.json + day_brief.json → GitHub
    └── Garante persistência para próxima run

END
```

---

## 9. ERROS CONHECIDOS E SUAS CORREÇÕES

| Erro | Causa | Correção implementada |
|------|-------|-----------------------|
| Post duplicado (Marcia Lucas) | Threshold de 3 palavras perdia nomes de 2 partes | Threshold reduzido para 2 palavras >3 letras |
| Imagem sem logo / horizontal | Imgur 429 + fallback og:image raw | catbox.moe como fallback; sem imagem com logo = skip |
| Post de podcast entrou | Sem filtro de tipo de conteúdo | Filtro explícito: podcast, lista genérica, clickbait |
| Reddit como fonte de post | Sem separação clara Reddit/RSS | Reddit removido do pool de candidatos |
| Mockup com texto | Fundo branded como fallback | Branded background removido completamente |
| Repost cross-run | posts_log.json não persistia | Git commit após cada run + `permissions: write` |

---

## 10. PERMISSÕES META — STATUS

| Permissão | Status | Impacto |
|-----------|--------|---------|
| `instagram_basic` | ✅ Ativo | Ler perfil |
| `instagram_content_publish` | ✅ Ativo | Publicar posts e Stories |
| `instagram_manage_comments` | ⚠️ Pendente | Desabilitar likes via update pós-publicação |
| `instagram_manage_insights` | ⚠️ Pendente | Métricas reais (alcance, salvos) |
| `instagram_manage_broadcast_messages` | ⚠️ Pendente | Postar na comunidade Clã do Morsa |

**Para adicionar:** Meta Developer → App "Morsa Digital" → App Review → solicitar cada permissão

---

*Última atualização: 2026-05-30*
