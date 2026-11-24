"""
Nomes oficiais no Brasil. Em nov/2026 saíram "Doutor Demônio" (é Doutor Destino),
"Avengers: Doomsday" (no Brasil, Vingadores: Doutor Destino) e "Captain America" no
meio da legenda. Duas barreiras: a lista vai no prompt (`PROMPT_RULE`) e `fix_names`
troca o que escapar, fora das hashtags.

Só entra em `_FIXES` o que nunca é nome oficial no Brasil. Ficam de fora, de propósito:
"Doom" sozinho (é o jogo DOOM), "Spider-Man" (jogos da Sony saem como "Marvel's
Spider-Man" aqui), "Deadpool", "Wolverine", "Gambit", "Hulk", "Loki".
"""
import re

_FIXES = [
    (r"Avengers:?\s+Doomsday", "Vingadores: Doutor Destino"),
    (r"Vingadores:?\s+Doomsday", "Vingadores: Doutor Destino"),
    (r"Avengers:?\s+Secret Wars", "Vingadores: Guerras Secretas"),
    (r"Avengers:?\s+Endgame", "Vingadores: Ultimato"),
    (r"Avengers:?\s+Infinity War", "Vingadores: Guerra Infinita"),
    (r"(?:Doutor|Doctor|Dr\.?)\s+(?:Dem[oô]nio|Doom)", "Doutor Destino"),
    (r"Captain America", "Capitão América"),
    (r"Iron Man", "Homem de Ferro"),
    (r"Black Widow", "Viúva Negra"),
    (r"Scarlet Witch", "Feiticeira Escarlate"),
    (r"Doctor Strange", "Doutor Estranho"),
    (r"Winter Soldier", "Soldado Invernal"),
    (r"Ant-Man", "Homem-Formiga"),
    (r"Black Panther", "Pantera Negra"),
    (r"Red Guardian", "Guardião Vermelho"),
    (r"Human Torch", "Tocha Humana"),
    (r"Mister Fantastic|Mr\.? Fantastic", "Senhor Fantástico"),
    (r"Invisible Woman", "Mulher Invisível"),
    (r"Fantastic Four", "Quarteto Fantástico"),
    (r"Young Avengers", "Jovens Vingadores"),
    (r"Silver Surfer", "Surfista Prateado"),
    (r"Moon Knight", "Cavaleiro da Lua"),
    (r"Daredevil:?\s+Born Again", "Demolidor: Renascido"),
    (r"Daredevil", "Demolidor"),
    (r"Hawkeye", "Gavião Arqueiro"),
    (r"Cyclops", "Ciclope"),
    (r"Nightcrawler", "Noturno"),
    (r"Mystique", "Mística"),
    (r"Wonder Woman", "Mulher-Maravilha"),
    (r"Green Lantern", "Lanterna Verde"),
    (r"Poison Ivy", "Hera Venenosa"),
    (r"Harley Quinn", "Arlequina"),
    (r"Catwoman", "Mulher-Gato"),
    (r"Justice League", "Liga da Justiça"),
    (r"Suicide Squad", "Esquadrão Suicida"),
    (r"Blue Beetle", "Besouro Azul"),
]
# "Marvel's Iron Man VR" e afins são o nome oficial do jogo no Brasil
_FIX_RE = [(re.compile(rf"(?<![\w#])(?<!Marvel's )(?<!Marvel’s ){rx}(?!\w)"), pt) for rx, pt in _FIXES]

# Nomes que o modelo só acerta com a lista na frente (o inglês às vezes vale para
# outra coisa, então não dá para trocar no automático).
PROMPT_RULE = """
NOMES (regra absoluta): escreva nomes de filmes, séries, jogos e personagens como saíram oficialmente no Brasil, nunca traduzidos por conta própria e nunca em inglês quando existe o nome brasileiro. Na dúvida sobre a tradução, use o nome do personagem civil (Steve Rogers, Hank McCoy) em vez de inventar.
Lista obrigatória: Avengers: Doomsday = Vingadores: Doutor Destino (estreia no Brasil em 16 de dezembro de 2026) · Doctor Doom = Doutor Destino (NUNCA "Doutor Demônio" nem "Doutor Doom") · Avengers: Secret Wars = Vingadores: Guerras Secretas · Captain America = Capitão América · Ant-Man = Homem-Formiga · Red Guardian = Guardião Vermelho · Human Torch = Tocha Humana · Mister Fantastic = Senhor Fantástico · Invisible Woman = Mulher Invisível · The Thing = Coisa · Fantastic Four = Quarteto Fantástico · Beast = Fera · Cyclops = Ciclope · Rogue = Vampira · Storm = Tempestade · Mystique = Mística · Nightcrawler = Noturno · Professor X = Professor Xavier · Sentinels = Sentinelas · Hawkeye = Gavião Arqueiro · Young Avengers = Jovens Vingadores · Falcon = Falcão · Winter Soldier = Soldado Invernal · Scarlet Witch = Feiticeira Escarlate · Vision = Visão · Black Panther = Pantera Negra · Doctor Strange = Doutor Estranho · Daredevil = Demolidor · Moon Knight = Cavaleiro da Lua · Silver Surfer = Surfista Prateado · Wonder Woman = Mulher-Maravilha · Green Lantern = Lanterna Verde · Lanterns = Lanternas · Peacemaker = Pacificador · Poison Ivy = Hera Venenosa · Harley Quinn = Arlequina · Clayface = Cara-de-Barro · Penguin = Pinguim · Joker = Coringa · Justice League = Liga da Justiça.
Ficam como estão: Thor, Loki, Hulk, Wolverine, Deadpool, Gambit, Magneto, Namor, Shang-Chi, Thunderbolts, Venom, e títulos de jogo que saem em inglês no Brasil (Marvel's Spider-Man, Marvel Rivals, Grand Theft Auto VI).
"""


def fix_names(text: str) -> str:
    """Troca nomes em inglês ou mal traduzidos pelo oficial brasileiro; hashtags ficam."""
    if not text:
        return text
    for rx, pt in _FIX_RE:
        text = rx.sub(pt, text)
    return text
