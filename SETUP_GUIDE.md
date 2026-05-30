# Guia Completo — Como Replicar o Autoposter em Qualquer Página

> Use este guia em um novo chat do Claude Code para configurar o autoposter
> em qualquer página Instagram + Facebook do zero. O Claude vai pedir
> as informações específicas da página e configurar tudo automaticamente.

---

## O QUE ESTE SISTEMA FAZ

Autoposter completo para Instagram (+ Facebook) com:
- **CMO Brain:** análise diária de métricas, concorrentes e tendências
- **Curadoria inteligente:** 13 feeds RSS filtrados + Reddit como sinal de tendência
- **Geração de conteúdo:** legendas com Claude Haiku, tom humano e jornalístico
- **Imagem obrigatória:** 1080×1350px (4:5) com logo da marca, sempre
- **Deduplicação:** 2 camadas — nunca reposta o mesmo assunto
- **12–18 posts/dia** automáticos via GitHub Actions, sem servidor, custo ~$2/mês
- **Stories:** compartilha automaticamente após cada post no feed

---

## PASSO 1 — FORK DO REPOSITÓRIO

```bash
# Clone o repositório base Morsa Digital
git clone https://github.com/tuliogama/morsa-digital-autoposter.git meu-novo-autoposter
cd meu-novo-autoposter

# Crie um novo repositório no GitHub para esta página
gh repo create NOME-DA-PAGINA-autoposter --public
git remote set-url origin https://github.com/SEU_USUARIO/NOME-DA-PAGINA-autoposter.git
git push -u origin main
```

---

## PASSO 2 — INFORMAÇÕES QUE O CLAUDE VAI PRECISAR

Ao iniciar um novo chat, forneça:

```
Página: @NOME_DA_PAGINA
Nicho: [ex: Star Wars / cultura geek brasileira / games indie / k-drama]
Tom de voz: [ex: fã apaixonado, jornalístico, sem emojis excessivos]
Logo: [caminho para o arquivo PNG da logo, fundo transparente, quadrada]
Feeds RSS: [listar feeds relevantes para o nicho, ou pedir para o Claude sugerir]
Facebook Page ID: [ID numérico da página vinculada]
Instagram User ID: [ID numérico da conta Business/Creator]
```

---

## PASSO 3 — META APP E TOKEN

### 3.1 Criar o App no Meta Developer

1. Acesse [developers.facebook.com](https://developers.facebook.com)
2. **Meus Apps → Criar App**
3. Tipo: **"Business"** (não Consumer — precisa ser Business para `pages_manage_posts`)
4. Caso de uso: **"Manage everything on your Page"**
5. Associar à Página do Facebook da conta

### 3.2 Adicionar produtos ao App

Em **Painel → Adicionar Produto**, adicionar:
- **Instagram Graph API**
- **Facebook Login**

### 3.3 Permissões necessárias

Em **App Review → Permissões**, solicitar:

| Permissão | Para que serve | Prioridade |
|-----------|---------------|-----------|
| `instagram_basic` | Ler perfil e posts | ✅ Obrigatório |
| `instagram_content_publish` | Publicar posts e Stories | ✅ Obrigatório |
| `pages_show_list` | Listar páginas do usuário | ✅ Obrigatório |
| `pages_read_engagement` | Ler métricas básicas | ✅ Obrigatório |
| `pages_manage_posts` | Cross-post IG → Facebook | ✅ Obrigatório para FB |
| `instagram_manage_comments` | Desabilitar contagem de likes | ⭐ Recomendado |
| `instagram_manage_insights` | Métricas de alcance e salvos | ⭐ Recomendado |

### 3.4 Gerar o Page Access Token PERMANENTE

```bash
# Passo 1: No Graph API Explorer, gere um User Token com todas as permissões acima

# Passo 2: Converter para Long-Lived Token (60 dias)
GET https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=APP_ID
  &client_secret=APP_SECRET
  &fb_exchange_token=TOKEN_CURTO

# Passo 3: Converter para Page Token PERMANENTE (expires_at=0)
GET https://graph.facebook.com/v19.0/me/accounts
  ?access_token=TOKEN_LONG_LIVED

# Copie o "access_token" da sua página — esse nunca expira
# (enquanto a senha do Facebook não mudar)

# Passo 4: Confirmar que é permanente
GET https://graph.facebook.com/debug_token
  ?input_token=PAGE_TOKEN
  &access_token=PAGE_TOKEN
# expires_at deve ser 0
```

### 3.5 Descobrir IDs

```bash
# Instagram User ID
GET https://graph.facebook.com/v19.0/me?fields=instagram_business_account&access_token=PAGE_TOKEN

# Facebook Page ID
GET https://graph.facebook.com/v19.0/me?fields=id,name&access_token=PAGE_TOKEN
```

---

## PASSO 4 — CONFIGURAR SECRETS NO GITHUB

```bash
# No repositório da nova página:
gh secret set ANTHROPIC_API_KEY    # Claude API key (mesma para todas as páginas)
gh secret set FB_ACCESS_TOKEN      # Page Access Token permanente
gh secret set IG_USER_ID           # ID numérico Instagram
gh secret set FB_PAGE_ID           # ID numérico Facebook Page
gh secret set IMGUR_CLIENT_ID      # Client ID do Imgur (gratuito em imgur.com/oauth2/addclient)
```

---

## PASSO 5 — ADAPTAR O SISTEMA PARA A NOVA PÁGINA

### 5.1 Logo da marca

```bash
# Colocar logo PNG (fundo transparente, quadrada, mín. 200×200px)
cp /caminho/para/logo.png assets/morsa_logo.png
```

O sistema automaticamente coloca a logo no canto inferior direito de cada imagem.

### 5.2 Feeds RSS (news_fetcher.py)

Substituir `NERD_RSS_FEEDS` pelos feeds relevantes ao nicho. Exemplos por nicho:

**Star Wars / Sci-Fi:**
```python
("StarWars.com",     "https://www.starwars.com/news/rss"),
("IGN",              "https://feeds.feedburner.com/ign/all"),
("Den of Geek",      "https://www.denofgeek.com/feed/"),
("ComicBook",        "https://comicbook.com/feed/"),
```

**K-Drama / Doramas:**
```python
("Soompi",           "https://www.soompi.com/feed"),
("Asian Wiki",       "https://asianwiki.com/feed/"),
("Dramabeans",       "https://www.dramabeans.com/feed/"),
```

**Games BR:**
```python
("GameBlast",        "https://www.gameblast.com.br/feeds/posts/default"),
("IGN Brasil",       "https://br.ign.com/feed.xml"),
("Voxel",            "https://www.voxel.com.br/rss.xml"),
("TudoCelular",      "https://www.tudocelular.com/rss.xml"),
```

### 5.3 Tom de voz e nicho (content_generator.py)

Atualizar o system prompt da geração de posts:

```python
# Em PLATFORM_PROMPTS["instagram"]["system"]
# Trocar referências a "cultura pop/nerd/geek" pelo nicho da página
# Ex. para Star Wars: "editor de conteúdo do Clã Sith Brasil, especialista em Star Wars"
```

### 5.4 Subreddits para CMO Brain (reddit_fetcher.py)

```python
# Substituir SUBREDDITS pelos relevantes ao nicho
# Ex. Star Wars:
SUBREDDITS = ["StarWars", "PrequelMemes", "sequelmemes", "TheMandalorianTV", ...]
```

### 5.5 Identidade no CLAUDE.md

Atualizar com os dados da nova conta:
```markdown
## O que é esse projeto
Autoposter para @NOME_PAGINA — [descrição do nicho]

**Contas:**
- Instagram: @NOME_PAGINA (IG_USER_ID=XXXX)
- Facebook Page ID: YYYY
```

---

## PASSO 6 — CONFIGURAR GITHUB ACTIONS

O arquivo `.github/workflows/auto-post.yml` já está configurado. Apenas verifique:

```yaml
# Volume de posts (ajustar conforme o nicho)
POSTS_PER_RUN: "3"   # 6 runs × 3 = 18 posts/dia (máximo)
                     # Use "2" para 12 posts/dia (mais conservador)
```

Os horários padrão são BRT: 08h, 10h30, 13h, 16h, 19h, 21h30.

---

## PASSO 7 — INICIALIZAR LOGS E TESTAR

```bash
# Garantir que logs existem e estão no git
echo "[]" > logs/posts_log.json
echo "{}" > logs/day_brief.json
git add -f logs/posts_log.json logs/day_brief.json
git commit -m "chore: inicializar logs"
git push

# Teste local (não publica)
source .env.secrets && export $(cat .env.secrets | grep -v '#' | xargs)
python3 src/main.py --dry-run --platforms instagram

# Teste real (publica)
python3 src/main.py --platforms instagram
```

---

## PASSO 8 — CROSS-POSTING INSTAGRAM → FACEBOOK

Quando o token tiver `pages_manage_posts`, o cross-post é automático.
O parâmetro `publish_to_facebook=true` já está implementado no publisher.

Para ativar: regenerar o token incluindo `pages_manage_posts` e atualizar o Secret.

```bash
gh secret set FB_ACCESS_TOKEN  # Token novo com pages_manage_posts
```

---

## ESTRUTURA DO REPOSITÓRIO (referência)

```
autoposter/
├── .github/workflows/auto-post.yml   # Cron 6×/dia, permissions: write
├── src/
│   ├── main.py                       # Pipeline: CMO → News → Dedup → Gera → Publica
│   ├── news_fetcher.py               # 13 feeds RSS (adaptar ao nicho)
│   ├── content_generator.py          # Claude Haiku — curadoria + captions
│   ├── image_generator.py            # Imagem 4:5 + logo + Imgur/catbox upload
│   ├── cmo_brain.py                  # Análise diária + Day Brief
│   ├── posts_log.py                  # Dedup 2 camadas (log local + IG API)
│   ├── metrics_analyzer.py           # Instagram Insights (requer permissão)
│   ├── reddit_fetcher.py             # Reddit RSS — só tendência, nunca post direto
│   └── publishers/
│       └── instagram.py              # Feed + Stories + cross-post FB
├── assets/
│   └── morsa_logo.png                # ← SUBSTITUIR pela logo da nova página
├── logs/
│   ├── posts_log.json                # Rastreado no git — memória de posts
│   └── day_brief.json                # Rastreado no git — brief diário do CMO
├── CONTENT_BIBLE.md                  # Regras editoriais (adaptar ao nicho)
├── CLAUDE.md                         # Guia de workflow para sessões Claude
└── .env.secrets                      # Chaves locais — NUNCA commitar
```

---

## CHECKLIST RÁPIDO PARA NOVO CHAT

Copie e cole no início do chat novo:

```
Contexto: quero configurar um autoposter para @NOME_PAGINA no Instagram.
Repositório base: https://github.com/tuliogama/morsa-digital-autoposter
Guia: SETUP_GUIDE.md no repositório

Dados da página:
- Nome: @NOME_PAGINA
- Nicho: [descrever]
- Tom de voz: [descrever]
- Logo: [caminho ou "vou enviar"]
- IG_USER_ID: [ID ou "ainda vou gerar"]
- FB_PAGE_ID: [ID ou "ainda vou gerar"]
- FB_ACCESS_TOKEN: [token ou "ainda vou gerar"]

Siga o SETUP_GUIDE.md do repositório passo a passo.
Peça o que precisar e adapte o sistema para este nicho específico.
```

---

## VARIÁVEIS DE AMBIENTE (resumo)

| Variável | Onde definir | Obrigatória |
|----------|-------------|-------------|
| `ANTHROPIC_API_KEY` | GitHub Secret | ✅ |
| `FB_ACCESS_TOKEN` | GitHub Secret | ✅ |
| `IG_USER_ID` | GitHub Secret | ✅ |
| `FB_PAGE_ID` | GitHub Secret | ✅ |
| `IMGUR_CLIENT_ID` | GitHub Secret | ✅ |
| `MORSA_BROADCAST_CHANNEL_ID` | GitHub Secret | Opcional |
| `POSTS_PER_RUN` | workflow env | Padrão: 3 |
| `DELAY_BETWEEN_POSTS` | workflow env | Padrão: 90s |
| `DRY_RUN` | workflow input | Padrão: false |

---

*Guia criado a partir da implementação do @morsadigital — maio 2026*
