export function qs(params = {}) {
  const partes = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
  return partes.length ? `?${partes.join('&')}` : ''
}

async function tratar(resp) {
  if (!resp.ok) {
    let detalhe
    try {
      detalhe = (await resp.json()).detail
    } catch {
      detalhe = resp.statusText
    }
    const erro = new Error(typeof detalhe === 'string' ? detalhe : 'Erro na requisição')
    erro.status = resp.status
    erro.detail = detalhe
    throw erro
  }
  return resp.json()
}

export const apiGet = (path, params) => fetch(`/api${path}${qs(params)}`).then(tratar)

export const apiSend = (method, path, body) =>
  fetch(`/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Autor': 'web' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(tratar)

export function uploadArquivos(arquivos, forcar = false) {
  const form = new FormData()
  for (const arquivo of arquivos) form.append('arquivos', arquivo)
  return fetch(`/api/uploads?forcar=${forcar}`, {
    method: 'POST',
    headers: { 'X-Autor': 'web' },
    body: form,
  }).then(tratar)
}

export function urlExportacao(formato, filtros) {
  return `/api/relatorios/${formato}${qs(filtros)}`
}
