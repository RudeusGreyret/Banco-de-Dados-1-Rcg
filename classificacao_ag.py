"""Pré-classificação de militares da AG por posto/graduação.

A classificação é apenas consultiva. A designação efetiva depende
das regras e habilitações validadas pelo responsável pela escala.
"""
import re
import unicodedata

SERVICOS = (
    "Oficial de Dia",
    "Adjunto de Dia",
    "Comandante da Guarda",
    "Cabo da Guarda",
    "Motorista de Dia",
)

def normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", texto.upper()).strip()


def extrair_posto(valor):
    """Aceita textos como '1º TEN', '2 TENENTE', '3º SGT', 'CB', 'SD EP'."""
    t = normalizar(valor)
    t = re.sub(r"[º°ª.\-/]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return ""
    if re.search(r"\b(OFICIAL GENERAL|GENERAL|GEN|CORONEL|CEL|TEN CEL|TC|MAJOR|MAJ|CAPITAO|CAP|TENENTE|TEN|ASPIRANTE|ASP)\b", t):
        return "OFICIAL"
    if re.search(r"\b(SUBTENENTE|SUB TEN|STEN|ST)\b", t):
        return "SUBTENENTE"
    if re.search(r"\b(SARGENTO|SGT|SG)\b", t):
        return "SARGENTO"
    if re.search(r"\b(CABO|CB)\b", t):
        return "CABO"
    if re.search(r"\b(SOLDADO|SOLD|SD|SLD)\b", t):
        return "SOLDADO"
    return ""


def escalas_possiveis(posto):
    regras = {
        "OFICIAL": ["Oficial de Dia"],
        "SUBTENENTE": ["Adjunto de Dia", "Comandante da Guarda"],
        "SARGENTO": ["Adjunto de Dia", "Comandante da Guarda"],
        "CABO": ["Cabo da Guarda", "Motorista de Dia"],
        "SOLDADO": ["Motorista de Dia"],
    }
    return regras.get(posto, [])


def sugerir_coluna(linhas, nomes_alvo, linha_cabecalho):
    if not linhas or linha_cabecalho < 0 or linha_cabecalho >= len(linhas):
        return None
    for i, rotulo in enumerate(linhas[linha_cabecalho]):
        texto = normalizar(rotulo)
        if any(nome in texto for nome in nomes_alvo):
            return i
    return None
