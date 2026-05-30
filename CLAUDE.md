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

## O que funciona (atualizar com dados reais)

### Captions que engajam
- Hook sem emoji forçado no início — texto direto, opinião ou dado surpreendente
- Referências culturais que o público reconhece (comparações com outras franquias)
- CTA variado — nunca repetir o mesmo chamado à ação
- SEO: mencionar o nome da franquia/game/série no texto, não só nas hashtags

### Conteúdo que performa bem
- Notícias de animes populares (Demon Slayer, One Piece, Jujutsu Kaisen)
- Trailers e lançamentos de jogos esperados
- Conteúdo brasileiro (Irmão do Jorel, games indie nacionais) — público se identifica
- Polêmicas da indústria (sindicalização Rockstar, cancelamentos)

### Evitar
- Conteúdo de IA genérica / robótica / finanças / política
- Posts sobre celebridades sem relação com cultura pop
- Mesmo formato de hook em posts consecutivos
- Começar legenda com emoji (parece bot)
- Emojis no início de cada parágrafo

---

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

### GitHub Actions
- Agenda: 6x/dia (08h, 10h30, 13h, 16h, 19h, 21h30 BRT)
- Plataforma padrão: `instagram`
- Secret `FB_ACCESS_TOKEN` precisa ser atualizado via `gh secret set FB_ACCESS_TOKEN`

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
