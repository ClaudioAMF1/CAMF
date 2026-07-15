"""Validação e normalização de CPF/CNPJ e nomes."""

import re
import unicodedata


def somente_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def validar_cpf(cpf: str) -> bool:
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for n_digitos in (9, 10):
        soma = sum(int(d) * p for d, p in zip(cpf[:n_digitos], range(n_digitos + 1, 1, -1)))
        dv = (soma * 10) % 11
        if dv == 10:
            dv = 0
        if dv != int(cpf[n_digitos]):
            return False
    return True


def validar_cnpj(cnpj: str) -> bool:
    cnpj = somente_digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(d) * p for d, p in zip(cnpj[:pos], pesos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(cnpj[pos]):
            return False
    return True


def normalizar_cpf_cnpj(valor: str | None) -> str | None:
    """Retorna o CPF/CNPJ só com dígitos se os DVs forem válidos, senão None."""
    digitos = somente_digitos(valor)
    if len(digitos) == 11 and validar_cpf(digitos):
        return digitos
    if len(digitos) == 14 and validar_cnpj(digitos):
        return digitos
    return None


def formatar_cpf_cnpj(digitos: str | None) -> str | None:
    if not digitos:
        return None
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return digitos


def normalizar_nome(nome: str) -> str:
    """Uppercase, sem acentos, espaços colapsados."""
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().upper()
