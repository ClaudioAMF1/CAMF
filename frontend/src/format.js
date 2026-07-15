export function fmtBRL(valor) {
  if (valor === null || valor === undefined || valor === '') return '—'
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function fmtData(iso) {
  if (!iso) return '—'
  const [ano, mes, dia] = iso.split('T')[0].split('-')
  return `${dia}/${mes}/${ano}`
}

export function fmtDataHora(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

export function fmtMes(aaaamm) {
  const [ano, mes] = aaaamm.split('-')
  return `${mes}/${ano}`
}

export function fmtCpfCnpj(digitos) {
  if (!digitos) return '—'
  if (digitos.length === 11)
    return digitos.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4')
  if (digitos.length === 14)
    return digitos.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5')
  return digitos
}

export const ROTULOS_SITUACAO = { aberto: 'Aberto', pago: 'Pago', cancelado: 'Cancelado' }

export const ROTULOS_DIVERGENCIA = {
  valor_divergente: 'valor divergente',
  vencimento_divergente: 'vencimento divergente',
  dv_geral_invalido: 'DV geral inválido',
  dv_campo_invalido: 'DV de campo inválido',
  cpf_cnpj_ausente: 'CPF/CNPJ ausente ou inválido',
  valor_ausente_na_linha: 'valor ausente na linha digitável',
}
