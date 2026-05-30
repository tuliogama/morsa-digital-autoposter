# Morsa Digital — Bíblia de Conteúdo e Checklist Obrigatório

> Última atualização: 2026-05-30 (baseada em análise real de 50 posts, 27.136 seguidores)
> O pipeline segue este checklist antes de cada post, sem exceção.

---

## 1. IDENTIDADE DA CONTA

**@morsadigital** é um perfil brasileiro de cultura pop/nerd/geek.

**Tom de voz:** fã apaixonado + jornalista. Direto, opinativo, humano — nunca corporativo, nunca bot.

**Temas por prioridade (baseado em dados reais):**

| Prioridade | Tema | Eng médio | Observação |
|-----------|------|-----------|------------|
| 🥇 | MCU / Marvel | 70 | Maior audiência ativa |
| 🥇 | DC / Batman / Super-heróis | 70 | Mesmo nível MCU |
| 🥈 | Cinema / Oscar / Estreias | 66 | Posts de evento explodem |
| 🥈 | Séries (Netflix, HBO, Disney+) | 60 | Consistente |
| 🥉 | Games (PS5, Xbox, Nintendo) | 40 | Público menor, mas ativo |
| — | Star Wars | 34 | Underperforma — cobrir só grandes notícias |
| — | Anime | 6 | Poucos dados; testar com cautela |

**Contas da operação:**
- Instagram: @morsadigital (`IG_USER_ID=17841405897887153`)
- Facebook Page ID: `108393784135641`
- ⚠️ NUNCA misturar com @tuliogama ou @ordemsithbrasil
- ⚠️ Twitter/X: SKIP permanente — erro 402

---

## 2. O QUE OS DADOS ENSINAM

### 2.1 Tipo de hook — impacto direto no engajamento

| Hook | Eng médio | Qtd | Diagnóstico |
|------|-----------|-----|-------------|
| ✅ Afirmação direta | **69** | 27 | Melhor desempenho — usar sempre que possível |
| ✅ Anúncio/confirmação | 60 | 5 | Segunda melhor opção |
| ✅ Pergunta direta | 55 | 3 | Gera comentários |
| ⚠️ Expectativa/nostalgia | 51 | 7 | Funciona mas não lidera |
| ❌ Emoji no início | **22** | 8 | **3× pior** — proibido |

**Conclusão: começar com emoji derruba o engajamento pela metade. Proibido.**

### 2.2 Volume × qualidade

| Período | Posts | Eng médio |
|---------|-------|-----------|
| Mar/2026 | 7 | **123** |
| Abr/2026 | 15 | 83 |
| Mai/2026 | 28 | **27** |

**Conclusão: volume alto derruba qualidade. Preferir 8–12 posts/dia com curadoria rigorosa.**

### 2.3 Melhor horário BRT (dados reais)

Picos de engajamento: **13h, 17h, 19h**
Horário com mais posts e consistência: **10h**
Pior janela: madrugada (00h–02h)

### 2.4 Melhor dia da semana

| Dia | Eng médio |
|-----|-----------|
| 🥇 Terça | **95** |
| 🥈 Domingo | 77 |
| 🥉 Segunda | 70 |
| Quarta | 68 |
| Quinta | 56 |
| Sexta | 38 |
| ❌ Sábado | **27** |

**Conclusão: posts mais caprichados devem sair na terça. Sábado é o pior dia.**

### 2.5 Conteúdo que gera comentários (discussão)
1. Reações em tempo real (Oscar, estreias, revelações ao vivo)
2. Perguntas diretas com CTA opinativo
3. Posts nostálgicos que pedem identificação ("qual cena te marca?")

---

## 3. CHECKLIST OBRIGATÓRIO — PRÉ-PUBLICAÇÃO

Cada post passa por estes 8 pontos. Falhar em qualquer um = **pular para próxima notícia**.

### ✅ PONTO 1 — Fonte válida
- [ ] Vem de um dos **13 feeds RSS autorizados** (ver Seção 6)
- [ ] Reddit: **APENAS sinal de tendência** no CMO Brain — nunca fonte de post
- [ ] Removidos: Omelete (feed 404), Cinema com Rapadura (podcasts dominam)

### ✅ PONTO 2 — Tipo de conteúdo
**Aceitar:**
- Notícias factuais: trailer, lançamento, data confirmada, anúncio oficial, resultado
- Eventos em tempo real: premiações, revelações, conferências
- Conteúdo que gera opinião: polêmicas da indústria, mudanças em franquias

**Rejeitar imediatamente:**
- ❌ Podcast ou episódio (RapaduraCast, NerdCast, qualquer "ep.")
- ❌ Lista genérica sem novidade ("melhores de 2025", "top 10")
- ❌ IA genérica / robótica / automação industrial
- ❌ Finanças, crypto, NFT, investimentos
- ❌ Política, eleições, governo
- ❌ Clickbait sem fonte verificável
- ❌ Celebridade sem ligação com cultura pop
- ❌ NSFW, violência explícita, saúde mental negativa

### ✅ PONTO 3 — Anti-duplicata (2 camadas)
- [ ] **Camada 1 — posts_log.json:** overlap de ≥2 palavras-chave (>3 letras) com últimos 7 dias → rejeitar
- [ ] **Camada 2 — Instagram API:** comparar com primeiras linhas das últimas 20 captions → rejeitar se tema já coberto em 3 dias
- [ ] Nomes próprios contam: "Marcia Lucas" = 2 palavras = bloqueia duplicatas

### ✅ PONTO 4 — Imagem (inegociável)
- [ ] **Imagem real do artigo** (og:image, twitter:image ou YouTube thumbnail)
- [ ] **Processada:** 1080×1350px (4:5 vertical)
- [ ] **Logo Morsa Digital** no canto inferior direito
- [ ] **Upload em CDN** (Imgur → catbox.moe fallback)
- [ ] ❌ **PROIBIDO:** horizontal, mockup, fundo laranja com texto, sem logo, og:image raw sem logo
- [ ] Sem imagem com logo = **pular post**, tentar próximo candidato

### ✅ PONTO 5 — Legenda (baseada nos dados)

**Estrutura obrigatória:**
```
[Hook — afirmação direta OU anúncio, SEM emoji, SEM "Olha só:"]

[Parágrafo 1: o que é + contexto — máx. 3 frases]

[Parágrafo 2: por que importa para o fã — conexão emocional]

[Parágrafo 3 (opcional): dado extra ou curiosidade]

[CTA — pergunta ou chamada, variada a cada post]

#hashtag1 #hashtag2 (8–12 hashtags, mix franquia + categoria)
```

**Regras derivadas dos dados:**
- ✅ Começar com afirmação direta — eng médio 69
- ✅ Usar perguntas no CTA — gera comentários
- ✅ Mencionar nome da franquia no corpo (SEO)
- ❌ Nunca começar com emoji — queda de 3× no eng
- ❌ Nunca começar parágrafo com emoji
- ❌ Não repetir mesmo CTA em posts consecutivos
- ❌ Máx. 12 hashtags
- ❌ Tom corporativo ou de press release

### ✅ PONTO 6 — Configuração técnica
- [ ] `like_and_view_counts_disabled=true` no container
- [ ] `publish_to_facebook=true` + `facebook_page_id` (quando `pages_manage_posts` ativo)
- [ ] Post registrado em `logs/posts_log.json` após publicação

### ✅ PONTO 7 — Sequência de publicação
1. Publicar no **Feed**
2. Tentar **Stories** via `source_type=FEED_MEDIA` (fallback silencioso)
3. Registrar no log

### ✅ PONTO 8 — Pós-publicação
- [ ] `posts_log.json` commitado no GitHub após cada run
- [ ] `day_brief.json` commitado junto

---

## 4. CICLO CMO — ANÁLISE ANTES DE CADA BATCH

A cada execução, **antes** de selecionar notícias:

1. **Métricas dos últimos 20 posts** — eng score, hooks que performaram
2. **Classificar padrões** — afirmação vs pergunta vs emoji (ver Seção 2.1)
3. **Cobertura dos concorrentes** — o que IGN Brasil, GameBlast, AnimeUnited publicaram
4. **Tendências Reddit** — sinal de alta (nunca fonte direta de post)
5. **Day Brief com Claude** — orientações estratégicas para o dia

O brief é reutilizado durante o dia. Reanálise completa 1×/dia.

---

## 5. VOLUME E HORÁRIOS

**Target baseado em dados:** 8–12 posts/dia (qualidade > quantidade)
**Máximo configurado:** 18/dia (3 posts × 6 runs) — ativar só em datas especiais

| Run | Horário BRT | Target |
|-----|-------------|--------|
| 1 | 08:00 | 3 |
| 2 | 10:30 | 3 |
| 3 | 13:00 | 3 |
| 4 | 16:00 | 3 |
| 5 | 19:00 | 3 |
| 6 | 21:30 | 3 |

**Atenção:** GitHub Actions crons podem atrasar 30–60min em horários de pico.
Se um run não sair no horário, disparar manualmente via Actions → Run workflow.

---

## 6. FONTES AUTORIZADAS (13 feeds RSS)

| # | Fonte | Idioma | Categoria |
|---|-------|--------|-----------|
| 1 | IGN Brasil | PT-BR | Games + Filmes |
| 2 | GameBlast | PT-BR | Games |
| 3 | AnimeUnited | PT-BR | Anime + Manga |
| 4 | IGN | EN | Games + Filmes |
| 5 | Kotaku | EN | Games |
| 6 | ComicBook | EN | Quadrinhos + MCU |
| 7 | Den of Geek | EN | Séries + Filmes + Geek |
| 8 | The Verge | EN | Tech + Cultura (filtrado) |
| 9 | Deadline | EN | Cinema (filtrado) |
| 10 | Variety | EN | Cinema (filtrado) |
| 11 | Anime News Network | EN | Anime + Manga |
| 12 | Eurogamer | EN | Games |
| 13 | Gizmodo | EN | Tech + Cultura (filtrado) |

**Removidos:** Omelete (feed 404), Cinema com Rapadura (podcast domina)

---

## 7. REGRAS DE IMAGEM — DETALHAMENTO

```
OBRIGATÓRIO:
✅ 1080 × 1350px (4:5 vertical)
✅ Logo Morsa Digital — canto inferior direito, 140px, halo escuro
✅ Gradiente escuro na parte inferior
✅ Imagem real do artigo (og:image, twitter:image, YouTube thumbnail)
✅ Upload CDN: Imgur → catbox.moe (fallback automático)

PROIBIDO:
❌ Qualquer ratio diferente de 4:5
❌ Mockup gerado (fundo laranja + título em branco)
❌ Imagem sem logo
❌ og:image raw sem processamento
❌ Placeholder genérico
❌ Se não tem imagem real → pular post
```

---

## 8. ERROS CONHECIDOS E CORREÇÕES

| Erro | Causa | Status |
|------|-------|--------|
| Post duplicado (ex: Marcia Lucas) | Threshold 3 palavras >4 letras perdia nomes | ✅ Corrigido: threshold 2 palavras >3 letras |
| Imagem sem logo / horizontal | Imgur 429 + fallback og:image raw | ✅ Corrigido: catbox.moe fallback; sem logo = skip |
| Post de podcast entrou | Sem filtro por tipo | ✅ Corrigido: BLOCK_KEYWORDS no news_fetcher |
| Reddit como fonte de post | Sem separação clara | ✅ Corrigido: Reddit apenas no CMO Brain |
| Mockup com texto | Branded background como fallback | ✅ Corrigido: removido permanentemente |
| Repost cross-run | posts_log.json não persistia | ✅ Corrigido: git commit + permissions: write |
| Cron atrasado/pulado | GitHub Actions instável | ⚠️ Monitorar; disparar manualmente se necessário |
| Like count visível | Falta `instagram_manage_comments` | ⚠️ Pendente — workaround: desabilitar no app |

---

## 9. PERMISSÕES META — STATUS

| Permissão | Status | Impacto |
|-----------|--------|---------|
| `instagram_basic` | ✅ Ativo | Ler perfil |
| `instagram_content_publish` | ✅ Ativo | Publicar posts e Stories |
| `pages_manage_posts` | ⚠️ Pendente | Cross-post automático IG → Facebook |
| `instagram_manage_comments` | ⚠️ Pendente | Desabilitar likes via API |
| `instagram_manage_insights` | ⚠️ Pendente | Métricas reais (alcance, salvos) |
| `instagram_manage_broadcast_messages` | ⚠️ Pendente | Comunidade Clã do Morsa |

**Para adicionar:** Meta Developer → App "Morsa Digital" → App Review → solicitar permissão → regenerar token → `gh secret set FB_ACCESS_TOKEN`

---

*Bíblia baseada em análise real: 50 posts, 27.136 seguidores, dados de mar–mai 2026*
