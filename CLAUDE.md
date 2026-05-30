# Ordem Sith Brasil — Guia para Claude

## O que é esse projeto

Autoposter para @ordemsithbrasil no Instagram. Focado exclusivamente em Star Wars —
filmes, séries, games, quadrinhos, lore e universo expandido. Tom: fã apaixonado
que conhece o cânone a fundo, não divulgação corporativa da Disney.

**Contas:**
- Instagram: @ordemsithbrasil (atualizar IG_USER_ID após criar conta Business)
- Facebook Page ID: (atualizar após configurar)
- ⚠️ NUNCA misturar com @morsadigital ou @tuliogama
- ⚠️ Twitter/X: SKIP — não configurado

---

## Workflow padrão

```bash
cd /caminho/para/ordemsith-autoposter
source .env.secrets && export $(cat .env.secrets | grep -v '#' | xargs)
python3 src/main.py --platforms instagram
```

---

## Infraestrutura técnica

- `src/news_fetcher.py` — feeds RSS focados em Star Wars + sci-fi complementar
- `src/reddit_fetcher.py` — subreddits Star Wars para tendências do CMO Brain
- `src/content_generator.py` — legendas com voz de fã Star Wars
- `src/image_generator.py` — imagem 4:5 com logo Ordem Sith + GitHub CDN
- `src/publishers/instagram.py` — publicação via Graph API
- `src/posts_log.py` — dedup 2 camadas
- `assets/morsa_logo.png` — ⚠️ SUBSTITUIR pela logo da Ordem Sith Brasil

## Secrets necessários (GitHub)

```
ANTHROPIC_API_KEY   — Claude Haiku
FB_ACCESS_TOKEN     — Page Access Token permanente (gerar conforme SETUP_GUIDE.md)
IG_USER_ID          — ID Instagram Business da Ordem Sith
FB_PAGE_ID          — ID Facebook Page da Ordem Sith
GITHUB_TOKEN        — automático no Actions (não precisa configurar)
```

## Checklist antes de ativar

- [ ] Logo da Ordem Sith em `assets/morsa_logo.png` (PNG transparente, quadrada)
- [ ] IG_USER_ID e FB_PAGE_ID da conta da Ordem Sith configurados
- [ ] FB_ACCESS_TOKEN com `instagram_content_publish` e `pages_manage_posts`
- [ ] ANTHROPIC_API_KEY no GitHub Secrets
- [ ] `echo "[]" > logs/posts_log.json && echo "{}" > logs/day_brief.json`
- [ ] `git add -f logs/ && git commit -m "init logs" && git push`
