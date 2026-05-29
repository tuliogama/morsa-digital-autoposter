# Morsa Digital — Autoposter

Sistema de postagem automática para o **Morsa Digital** — busca as notícias tech mais relevantes, gera posts com IA e publica no Twitter/X, Instagram e Facebook. Roda 3x/dia no GitHub Actions, custo zero de infraestrutura.

---

## Como funciona

```
GitHub Actions (cron 3x/dia)
        ↓
   Busca notícias
   HackerNews + Reddit + RSS
        ↓
   Claude AI (Haiku)
   Seleciona as mais relevantes
   Gera post por plataforma
        ↓
   Publica via APIs
   Twitter · Instagram · Facebook
        ↓
   Salva log como artifact
```

---

## Setup — passo a passo

### 1. Fork / Clone este repositório no GitHub

```bash
gh repo create morsadigital/autoposter --public --source=. --push
```

### 2. Configure os Secrets no GitHub

Vá em **Settings → Secrets and variables → Actions** e adicione:

| Secret | Como obter |
|--------|-----------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `TWITTER_API_KEY` | [developer.x.com](https://developer.x.com) → App → Keys |
| `TWITTER_API_SECRET` | Idem acima |
| `TWITTER_ACCESS_TOKEN` | Idem — "Access Token and Secret" |
| `TWITTER_ACCESS_SECRET` | Idem |
| `FB_PAGE_ID` | ID numérico da sua Page no Facebook |
| `FB_ACCESS_TOKEN` | Token com `pages_manage_posts` (veja abaixo) |
| `IG_USER_ID` | ID numérico da conta Instagram Business |
| `IG_DEFAULT_IMAGE_URL` | URL pública de uma imagem padrão (1080x1080px) |

### 3. Facebook / Instagram — como obter o token

1. Acesse [developers.facebook.com](https://developers.facebook.com)
2. Crie um App → Business → adicione "Facebook Login" e "Instagram Graph API"
3. Gere um **Page Access Token** com permissões:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_basic`
   - `instagram_content_publish`
4. Use o [Access Token Debugger](https://developers.facebook.com/tools/accesstoken/) para converter para **Long-Lived Token** (60 dias).

> **Dica:** Renove o token a cada 50 dias ou configure o fluxo de refresh automático.

### 4. Twitter/X — como obter as chaves

1. Acesse [developer.x.com](https://developer.x.com) → Projects & Apps → New App
2. Ative **Read and Write** permissions
3. Em "Keys and Tokens" gere:
   - API Key + Secret
   - Access Token + Secret (com permissão de escrita)

### 5. Imagem padrão para Instagram

O Instagram exige uma imagem para cada post. Você tem duas opções:
- **URL fixa**: hospede uma imagem padrão do Morsa Digital no GitHub Pages ou Cloudinary e configure em `IG_DEFAULT_IMAGE_URL`
- **Geração dinâmica**: evolução futura — gerar imagens com a notícia via API de imagem

---

## Execução manual

Via GitHub Actions UI: **Actions → Morsa Digital Auto Post → Run workflow**

Localmente (dry run — não publica):
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python src/main.py --dry-run --platforms twitter,facebook
```

---

## Estrutura do projeto

```
morsa-digital-autoposter/
├── .github/workflows/auto-post.yml   # Cron + pipeline
├── src/
│   ├── main.py                       # Entry point
│   ├── news_fetcher.py               # HackerNews + Reddit + RSS
│   ├── content_generator.py          # Claude API — geração de posts
│   └── publishers/
│       ├── twitter.py
│       ├── instagram.py
│       └── facebook.py
├── config/settings.json              # Tom de voz, tópicos, frequência
└── logs/                             # Histórico de runs (gitignored)
```

---

## Custos

| Serviço | Custo |
|---------|-------|
| GitHub Actions | **Gratuito** (público) |
| HackerNews API | **Gratuito** |
| Reddit API | **Gratuito** (leitura pública) |
| RSS Feeds | **Gratuito** |
| Claude Haiku | ~$0.002 por run (3 posts) |
| Twitter API | **Gratuito** (Free tier — 1500 tweets/mês) |
| Meta Graph API | **Gratuito** |

**Custo total estimado: ~$0.18/mês** (só Claude API, 3 runs/dia × 30 dias)
