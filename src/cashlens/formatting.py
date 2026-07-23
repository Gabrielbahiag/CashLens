from html import escape
from typing import Optional


def formatar_moeda(centavos: int) -> str:
    """Formata centavos como 'R$ 1.234,56' (padrão brasileiro), usado por todas as interfaces."""
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(centavos), 100)
    reais_str = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {reais_str},{resto:02d}"


# Paleta categórica (ordem fixa, validada contra daltonismo e contraste - dataviz skill).
CORES_CATEGORICAS = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
COR_NAO_CATEGORIZADO = "#898781"  # muted ink


def cores_por_categoria(nomes_categorias: list[str]) -> dict[str, str]:
    """Atribui uma cor fixa e determinística a cada nome de categoria (ordem alfabética)."""
    nomes_ordenados = sorted(set(nomes_categorias))
    return {nome: CORES_CATEGORICAS[i % len(CORES_CATEGORICAS)] for i, nome in enumerate(nomes_ordenados)}


def badge_categoria_html(nome: Optional[str], mapa_cores: dict[str, str]) -> str:
    """Tag HTML colorida pra uma categoria, na mesma cor usada nos gráficos (color-mix, tema-adaptável)."""
    cor = mapa_cores.get(nome, COR_NAO_CATEGORIZADO) if nome else COR_NAO_CATEGORIZADO
    texto = escape(nome or "Não categorizado")
    return (
        f'<span style="display:inline-block; padding:2px 10px; border-radius:999px; '
        f'font-size:0.85em; font-weight:600; white-space:nowrap; '
        f'background:color-mix(in srgb, {cor} 18%, transparent); '
        f'color:{cor}; border:1px solid color-mix(in srgb, {cor} 35%, transparent);">'
        f"{texto}</span>"
    )
