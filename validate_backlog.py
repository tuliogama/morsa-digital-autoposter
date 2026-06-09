"""
validate_backlog.py — verifica integridade de data/trailer_backlog.json

Detecta:
  - Chaves duplicadas dentro de um objeto (corrupção de JSON)
  - Datas com formato inválido
  - Status inconsistente com a data (vai ser corrigido em runtime, mas aqui avisa)
  - Filmes muito antigos (> 90 dias) marcados como não postados
  - Campos obrigatórios ausentes

Uso:
  python3 validate_backlog.py            # só valida
  python3 validate_backlog.py --fix      # corrige status automaticamente e salva
"""
import json
import sys
import os
from datetime import datetime

BACKLOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "trailer_backlog.json")
CAMPOS_OBRIGATORIOS = ["id", "titulo", "data_estreia", "elenco", "contexto", "query_youtube"]

# ---------------------------------------------------------------------------
# Detecta chaves duplicadas (erro silencioso no Python padrão)
# ---------------------------------------------------------------------------

class _DuplicateKeyError(Exception):
    pass

class _DuplicateKeyDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        kwargs["object_pairs_hook"] = self._check_pairs
        super().__init__(*args, **kwargs)

    @staticmethod
    def _check_pairs(pairs):
        seen = {}
        for k, v in pairs:
            if k in seen:
                raise _DuplicateKeyError(f"Chave duplicada detectada: '{k}'")
            seen[k] = v
        return seen


def load_strict(path: str) -> list:
    """Carrega JSON detectando chaves duplicadas."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    # Testa cada objeto individualmente para localizar o problemático
    data = json.loads(raw)  # carrega normal primeiro para pegar a lista
    errors = []
    for i, item in enumerate(data):
        item_raw = json.dumps(item)
        try:
            json.loads(item_raw, cls=_DuplicateKeyDecoder)
        except _DuplicateKeyError as e:
            errors.append(f"  Item #{i+1} ({item.get('titulo','?')}): {e}")
    if errors:
        print("❌ CHAVES DUPLICADAS ENCONTRADAS:")
        for e in errors:
            print(e)
        print("   → Abra data/trailer_backlog.json e corrija manualmente.")
        return data, True
    return data, False


# ---------------------------------------------------------------------------
# Validações
# ---------------------------------------------------------------------------

def validate(items: list, fix: bool = False) -> tuple[list, int]:
    hoje = datetime.now()
    erros = 0
    avisos = 0
    meses = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

    for item in items:
        titulo = item.get("titulo", item.get("id", "?"))

        # 1. Campos obrigatórios
        for campo in CAMPOS_OBRIGATORIOS:
            if not item.get(campo):
                print(f"❌ CAMPO AUSENTE '{campo}': {titulo}")
                erros += 1

        # 2. Formato da data
        data_str = item.get("data_estreia", "")
        if not data_str:
            continue

        try:
            dt = datetime.strptime(data_str, "%Y-%m-%d")
        except ValueError:
            print(f"❌ DATA INVÁLIDA '{data_str}': {titulo}")
            erros += 1
            continue

        # 3. Calcular status real
        dias = (hoje - dt).days
        if dias < 0:
            status_real = "pre_estreia"
            data_legivel = f"{dt.day} {meses[dt.month-1]}/{dt.year} (daqui {-dias}d)"
        elif dias <= 90:
            status_real = "em_cartaz"
            data_legivel = f"{dt.day} {meses[dt.month-1]}/{dt.year} ({dias}d atrás)"
        else:
            status_real = "EXPIRADO"
            data_legivel = f"{dt.day} {meses[dt.month-1]}/{dt.year} ({dias}d atrás — MUITO ANTIGO)"

        stored_status = item.get("status", "")

        # 4. Status inconsistente
        if stored_status != status_real:
            if status_real == "EXPIRADO" and not item.get("postado", False):
                print(f"⚠️  MUITO ANTIGO ({dias}d): {titulo} — considere marcar postado=true ou remover")
                avisos += 1
            else:
                marker = "✅" if fix else "⚠️ "
                print(f"{marker} STATUS ERRADO: {titulo}")
                print(f"      arquivo='{stored_status}' | calculado='{status_real}' | data={data_legivel}")
                if fix:
                    item["status"] = status_real
                else:
                    avisos += 1

        else:
            print(f"✅  {titulo} — {status_real} | {data_legivel}")

    return items, erros, avisos


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    fix_mode = "--fix" in sys.argv

    print(f"\n{'='*60}")
    print(f"  validate_backlog.py — {'MODO CORREÇÃO' if fix_mode else 'modo leitura'}")
    print(f"  Data de hoje: {datetime.now().strftime('%d/%m/%Y')}")
    print(f"{'='*60}\n")

    if not os.path.exists(BACKLOG_PATH):
        print(f"❌ Arquivo não encontrado: {BACKLOG_PATH}")
        sys.exit(1)

    items, tem_duplicatas = load_strict(BACKLOG_PATH)
    print(f"\n{'─'*60}\n")

    items, erros, avisos = validate(items, fix=fix_mode)

    print(f"\n{'─'*60}")
    print(f"  Total de itens: {len(items)}")
    print(f"  Erros críticos: {erros}")
    print(f"  Avisos: {avisos}")

    if fix_mode and avisos == 0 and erros == 0:
        print("  Nada a corrigir.")
    elif fix_mode and not tem_duplicatas:
        print("\n  Salvando correções...")
        with open(BACKLOG_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"  ✅ {BACKLOG_PATH} salvo com status corrigidos.")
    elif not fix_mode and (erros > 0 or avisos > 0):
        print("\n  Dica: rode com --fix para corrigir status automaticamente.")

    print()
    sys.exit(1 if erros > 0 or tem_duplicatas else 0)


if __name__ == "__main__":
    main()
