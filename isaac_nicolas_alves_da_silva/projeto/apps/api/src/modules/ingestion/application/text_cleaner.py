"""Servico de limpeza e normalizacao de texto."""

import re


class TextCleaner:
    """Limpa e normaliza texto bruto vindo do scraping.

    Responsabilidades: normalizar quebras de linha, remover caracteres de
    controle, colapsar linhas em branco consecutivas e retirar espacos
    desnecessarios dentro de cada linha.
    """

    def clean(self, raw_text: str) -> str:
        if not raw_text:
            return ""

        # Normaliza quebras de linha Windows/Mac para Unix
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove caracteres de controle, preservando \n (0x0a) e \t (0x09)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Normaliza espacos dentro de cada linha (colapsa multiplos espacos/tabs)
        lines = [
            " ".join(line.split()) if line.strip() else ""
            for line in text.split("\n")
        ]

        # Colapsa linhas em branco consecutivas para no maximo uma
        result: list[str] = []
        prev_blank = False
        for line in lines:
            is_blank = line == ""
            if is_blank and prev_blank:
                continue
            result.append(line)
            prev_blank = is_blank

        return "\n".join(result).strip()
