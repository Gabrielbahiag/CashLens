def formatar_moeda(centavos: int) -> str:
    """Formata centavos como 'R$ 1.234,56' (padrão brasileiro), usado por todas as interfaces."""
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(centavos), 100)
    reais_str = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {reais_str},{resto:02d}"
