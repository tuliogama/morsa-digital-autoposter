# Morsa Digital — Autoposter

Sistema de postagem automática para o **@morsadigital** — perfil brasileiro de cultura pop/nerd/geek no Instagram. Busca as notícias mais relevantes, gera posts com IA e publica automaticamente. Roda **6×/dia** no GitHub Actions, custo quase zero de infraestrutura.

---

## Arquitetura do sistema

```
GitHub Actions (6×/dia — horários BRT)
         │
         ▼
  ┌─────────────────────────────────────────────┐
  │  1. CMO Brain — análise diária              │
  │     Métricas IG + concorrentes + trends     │
  │     → Day Brief (orientação estratégica)    │
  └─────────────────┬───────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────┐
  │  2. Busca de notícias                       │
  │     RSS feeds BR/internacional + Reddit     │
  │     Filtros: NSFW, política, crypto, etc.   │
  └─────────────────┬───────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────┐
  │  3. Deduplicação (2 camadas)               │
  │     Layer 1: posts_log.json (local)         │
  │     Layer 2: captions IG via API            │
  └─────────────────┬───────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────┐
  │  4. Curadoria com Claude Haiku              │
  │     Seleciona melhor notícia do dia         │
  │     Orientado pelo Day Brief do CMO         │
  └─────────────────┬───────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────┐
  │  5. Geração de conteúdo                     │
  │     Caption com hook, corpo, CTA, hashtags  │
  │     Imagem 1080×1350px (4:5) com logo       │
  └─────────────────┬───────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────┐
  │  6. Publicação no Instagram                 │
  │     like_and_view_counts_disabled=true      │
  │     Tenta desabilitar likes pós-publicação  │
  │     Registra em posts_log.json              │
  └─────────────────────────────────────────────┘
                    │
                    ▼
         git commit posts_log.json
         (persistência entre runs)
```

---

## Fontes de conteúdo

### Feeds RSS (por categoria)

| Fonte | Categoria | Idioma |
|-------|-----------|--------|
| IGN Brasil | Games + Filmes | PT-BR |
| Cinema com Rapadura | Filmes + Séries | PT-BR |
| GameBlast | Games | PT-BR |
| AnimeUnited | Anime + Manga | PT-BR |
| Jovem Nerd | Cultura geek geral | PT-BR |
| Omelete | Cultura pop | PT-BR |
| IGN | Games + Filmes | EN |
| Kotaku | Games | EN |
| ComicBook.com | Quadrinhos + MCU | EN |
| Anime News Network | Anime + Manga | EN |
| Eurogamer | Games | EN |

### Reddit (sinal de tendência)
Subreddits monitorados: `games`, `gaming`, `nintendo`, `PS5`, `movies`, `television`, `marvelstudios`, `anime`, `manga`, `OnePiece`, `DemonSlayer`, `Naruto`, `JujutsuKaisen`, e outros.

Filtros automáticos aplicados:
- Palavras NSFW/+18 no título
- Conteúdo político, financeiro (crypto/NFT), fake news
- Validação adicional por Claude: rejeita rumores sem fonte, memes e clickbait

---

## CMO Brain — ciclo de análise diária

A cada execução, o sistema primeiro roda uma análise estratégica completa:

1. **Métricas de performance** — analisa os últimos 20 posts (likes, comentários, salvos, alcance)
2. **Padrões de hook** — classifica qual estilo de abertura está performando melhor
3. **Cobertura dos concorrentes** — verifica o que IGN Brasil, Cinema com Rapadura, GameBlast e AnimeUnited publicaram hoje
4. **Trends do Reddit** — identifica o que está em alta nos subreddits relevantes
5. **Day Brief** — Claude sintetiza tudo em orientações concretas:
   - Categorias a priorizar no dia
   - Fontes com mais relevância agora
   - Tópicos já cobertos (evitar repetição)
   - Estilo de hook que está engajando
   - Ângulo editorial para se diferenciar

O brief é salvo em `logs/day_brief.json` e reutilizado nas execuções subsequentes do mesmo dia (sem re-análise).

---

## Deduplicação

Dois problemas que causavam reposts foram resolvidos com sistema de duas camadas:

**Layer 1 — posts_log.json**
- Arquivo local rastreado no git (`logs/posts_log.json`)
- Compara sobreposição de palavras significativas do título (≥3 palavras em comum = duplicata)
- Persiste entre runs via git commit automático no workflow

**Layer 2 — Instagram API**
- Busca as últimas 50 legendas publicadas no perfil via Graph API
- Extrai palavras significativas das captions
- Garante dedup mesmo se o arquivo local estiver desatualizado

---

## Geração de imagens

Estratégias aplicadas em ordem de prioridade:

1. **URL do YouTube** → extrai thumbnail diretamente (`img.youtube.com/vi/{id}/maxresdefault.jpg`)
2. **URL do Reddit** → resolve URL externa vinculada no post → aplica estratégias abaixo
3. **og:image** e **twitter:image** → extrai da página da notícia via meta tags
4. **Fallback** → imagem branded: fundo laranja, título em branco, badge da fonte

Todas as imagens são redimensionadas para **1080×1350px** (formato 4:5 do Instagram) com logo da Morsa Digital no canto inferior direito.

Upload via Imgur (URL pública exigida pela API do Instagram).

---

## Volume e horários

### Configuração atual: 12–24 posts/dia

| Execução | Horário (BRT) | Posts |
|----------|---------------|-------|
| Manhã cedo | 08:00 | 2 |
| Manhã | 10:30 | 2 |
| Almoço | 13:00 | 2 |
| Tarde | 16:00 | 2 |
| Noite | 19:00 | 2 |
| Noite tarde | 21:30 | 2 |

**Total padrão: 12 posts/dia**. Para aumentar até 24, ajuste `POSTS_PER_RUN: "4"` no workflow.

---

## Estrutura do projeto

```
morsa-digital-autoposter/
├── .github/
│   └── workflows/
│       └── auto-post.yml          # 6×/dia, permissions: write, concurrency guard
├── src/
│   ├── main.py                    # Pipeline principal (6 etapas)
│   ├── news_fetcher.py            # RSS feeds + Reddit
│   ├── content_generator.py       # Claude Haiku — curadoria + captions
│   ├── image_generator.py         # Imagem 1080×1350px + Imgur upload
│   ├── cmo_brain.py               # Análise diária + Day Brief
│   ├── posts_log.py               # Memória persistente + deduplicação
│   ├── metrics_analyzer.py        # Instagram Insights API
│   ├── reddit_fetcher.py          # Reddit RSS + filtros + validação Claude
│   └── publishers/
│       └── instagram.py           # Graph API — container → publish
├── logs/
│   ├── posts_log.json             # ← RASTREADO NO GIT (persistência)
│   └── day_brief.json             # ← RASTREADO NO GIT (brief do dia)
├── batch_catchup.py               # Recuperar gap de posts
├── CLAUDE.md                      # Guia de workflow para sessões Claude
└── .env.secrets                   # Chaves locais — NUNCA commitar
```

---

## Setup — passo a passo

### 1. Clone e configure

```bash
git clone https://github.com/SEU_USUARIO/morsa-digital-autoposter.git
cd morsa-digital-autoposter
pip install anthropic pillow requests
```

### 2. Configure os Secrets no GitHub

Vá em **Settings → Secrets and variables → Actions**:

| Secret | Descrição |
|--------|-----------|
| `ANTHROPIC_API_KEY` | Claude Haiku — geração de conteúdo |
| `FB_ACCESS_TOKEN` | Page Access Token permanente do Instagram |
| `IG_USER_ID` | ID numérico da conta Instagram Business |
| `IMGUR_CLIENT_ID` | Client ID do Imgur para upload de imagens |

### 3. Gerar o Page Access Token permanente

```
1. Acesse developers.facebook.com → seu app "Morsa Digital"
2. Ferramentas → Graph API Explorer
3. Gere User Token com permissões:
   - instagram_basic
   - instagram_content_publish
   - instagram_manage_comments  ← necessário para desabilitar likes
   - instagram_manage_insights  ← necessário para métricas
   - pages_show_list
   - pages_read_engagement
4. Troque por Long-Lived Token (60 dias):
   GET /oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=TOKEN_CURTO
5. Converta para Page Token permanente (expires_at=0):
   GET /me/accounts?access_token=TOKEN_LONG_LIVED
   → copie o "access_token" da page "Morsa Digital"
6. Confirme: GET /debug_token → expires_at deve ser 0
7. Salve no GitHub: gh secret set FB_ACCESS_TOKEN
```

### 4. Configure variáveis de ambiente locais

```bash
# .env.secrets (nunca commitar!)
ANTHROPIC_API_KEY=sk-ant-...
FB_ACCESS_TOKEN=EAABm...
IG_USER_ID=17841405897887153
FB_PAGE_ID=108393784135641
IMGUR_CLIENT_ID=546c25a59c58ad7
```

### 5. Inicializar o log de posts

```bash
# Se logs/posts_log.json não existe ainda:
echo "[]" > logs/posts_log.json
git add logs/posts_log.json logs/day_brief.json
git commit -m "chore: inicializar logs rastreados"
git push
```

---

## Execução manual

```bash
# Carregar variáveis
source .env.secrets && export $(cat .env.secrets | grep -v '#' | xargs)

# Rodar pipeline completo (publica 2 posts)
python3 src/main.py --platforms instagram

# Pular re-análise do CMO (reutiliza brief do dia)
python3 src/main.py --platforms instagram --skip-brief

# Recuperar gap de posts sem duplicar
python3 batch_catchup.py

# Ver performance dos últimos posts
cd src && python3 -m metrics_analyzer
```

---

## Permissões do app Meta

| Permissão | Status | Para que serve |
|-----------|--------|----------------|
| `instagram_basic` | ✅ Ativo | Ler perfil e mídia |
| `instagram_content_publish` | ✅ Ativo | Publicar posts |
| `instagram_manage_comments` | ⚠️ Pendente | Desabilitar contagem de likes |
| `instagram_manage_insights` | ⚠️ Pendente | Métricas de alcance e salvos |

Para adicionar as permissões pendentes:
1. Meta Developer → App "Morsa Digital" → App Review
2. Solicitar `instagram_manage_comments` e `instagram_manage_insights`
3. Após aprovação: regenerar token e atualizar GitHub Secret

---

## Troubleshooting

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| Post sem imagem (só logo) | og:image não encontrado | Normal para alguns feeds — imagem branded é o fallback |
| Post repetido | posts_log.json desatualizado | Checar se git push do workflow está funcionando (`permissions: contents: write`) |
| CMO Brain sem dados | Token sem `instagram_manage_insights` | Adicionar permissão ou ignorar (brief usa fallback) |
| Likes visíveis | Sem `instagram_manage_comments` | Desabilitar manualmente no app até ter a permissão |
| Token expirado | Senha do FB mudou | Regenerar conforme passo 3 do setup |
| Reddit 403 | API JSON bloqueada | Sistema já usa RSS — se RSS falhar, Reddit é ignorado silenciosamente |
| Imgur falha | Client-ID inválido | Verificar `IMGUR_CLIENT_ID` no secret |

---

## Custos estimados

| Serviço | Custo |
|---------|-------|
| GitHub Actions | **Gratuito** (repositório público) |
| RSS Feeds | **Gratuito** |
| Reddit RSS | **Gratuito** |
| Meta Graph API | **Gratuito** |
| Imgur API | **Gratuito** (tier básico) |
| Claude Haiku | ~$0.012 por run (curadoria + geração + validação) |

**Custo total estimado: ~$2,16/mês** (6 runs/dia × 30 dias × $0.012)
