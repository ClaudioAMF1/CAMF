import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend } from '../api'
import { fmtBRL, fmtCpfCnpj } from '../format'
import { LinhasEsqueleto, useToast, Vazio } from '../ui'

function iniciais(nome = '') {
  const p = nome.trim().split(/\s+/).filter(Boolean)
  if (!p.length) return '?'
  return ((p[0][0] || '') + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase()
}

function LinhaEdicao({ pagador, onSalvar, onCancelar }) {
  const [form, setForm] = useState({
    nome: pagador.nome,
    cpf_cnpj: pagador.cpf_cnpj || '',
    municipio: pagador.municipio || '',
    uf: pagador.uf || '',
  })
  const mudar = (c) => (e) => setForm((f) => ({ ...f, [c]: e.target.value }))
  return (
    <tr>
      <td colSpan={6}>
        <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label className="campo" style={{ flex: 1, minWidth: 190 }}><span>Nome</span><input value={form.nome} onChange={mudar('nome')} /></label>
          <label className="campo"><span>CPF/CNPJ</span><input value={form.cpf_cnpj} onChange={mudar('cpf_cnpj')} placeholder="somente números" style={{ width: 165 }} /></label>
          <label className="campo"><span>Município</span><input value={form.municipio} onChange={mudar('municipio')} style={{ width: 145 }} /></label>
          <label className="campo"><span>UF</span><input value={form.uf} onChange={mudar('uf')} maxLength={2} style={{ width: 56 }} /></label>
          <button className="principal-btn mini" onClick={() => onSalvar(form)}>Salvar</button>
          <button className="mini" onClick={onCancelar}>Cancelar</button>
        </div>
      </td>
    </tr>
  )
}

export default function PagadoresPage() {
  const [editando, setEditando] = useState(null)
  const [busca, setBusca] = useState('')
  const queryClient = useQueryClient()
  const notificar = useToast()

  const { data: pagadores, isLoading } = useQuery({
    queryKey: ['pagadores'],
    queryFn: () => apiGet('/pagadores'),
  })
  const { data: sugestoes } = useQuery({
    queryKey: ['sugestoes-merge'],
    queryFn: () => apiGet('/pagadores/sugestoes-merge'),
  })

  const mut = useMutation({
    mutationFn: ({ metodo, path, corpo }) => apiSend(metodo, path, corpo),
    onSuccess: () => queryClient.invalidateQueries(),
    onError: (e) => notificar(typeof e.detail === 'string' ? e.detail : e.message, 'erro'),
  })

  const salvar = (pagador, form) => {
    const corpo = { nome: form.nome, municipio: form.municipio || null, uf: form.uf || null }
    if (form.cpf_cnpj && form.cpf_cnpj !== (pagador.cpf_cnpj || '')) corpo.cpf_cnpj = form.cpf_cnpj
    mut.mutate({ metodo: 'PATCH', path: `/pagadores/${pagador.id}`, corpo },
      { onSuccess: () => { queryClient.invalidateQueries(); notificar('Pagador atualizado') } })
    setEditando(null)
  }

  const mesclar = (destinoId, origemId) => {
    if (confirm(`Migrar os boletos do pagador #${origemId} para o #${destinoId} e arquivar a origem?`)) {
      mut.mutate({ metodo: 'POST', path: `/pagadores/${destinoId}/merge`, corpo: { pagador_origem_id: origemId } },
        { onSuccess: () => { queryClient.invalidateQueries(); notificar('Pagadores mesclados') } })
    }
  }

  const termo = busca.trim().toLowerCase()
  const filtrados = (pagadores || []).filter(
    (p) => !termo || p.nome.toLowerCase().includes(termo) || (p.cpf_cnpj || '').includes(termo.replace(/\D/g, ''))
  )

  return (
    <div>
      <div className="topo">
        <div>
          <h2>Pagadores</h2>
          <div className="sub">
            A identidade é o CPF/CNPJ. Pagadores provisórios (sem documento) se regularizam ao informar o CPF/CNPJ em “Editar”.
          </div>
        </div>
        <input placeholder="Buscar por nome ou documento…" value={busca}
          onChange={(e) => setBusca(e.target.value)} style={{ minWidth: 250 }} />
      </div>

      {!!sugestoes?.length && (
        <div className="painel" style={{ borderLeft: '3px solid var(--ambar)' }}>
          <div className="painel-titulo">Possíveis duplicados</div>
          <div className="painel-sub">
            Mesmo nome com documentos diferentes. Nada é mesclado automaticamente — a decisão é sua.
          </div>
          {sugestoes.map((s) => (
            <div key={s.nome_normalizado} style={{ marginBottom: 10 }}>
              <strong>{s.nome_normalizado}</strong>
              <div className="acoes" style={{ marginTop: 5 }}>
                {s.pagadores.map((p) => (
                  <span key={p.id} className="etiqueta neutra sem-ponto">
                    #{p.id} · {fmtCpfCnpj(p.cpf_cnpj) || 'sem documento'}
                  </span>
                ))}
                {s.pagadores.length === 2 && (
                  <>
                    <button className="mini" onClick={() => mesclar(s.pagadores[0].id, s.pagadores[1].id)}>Manter #{s.pagadores[0].id}</button>
                    <button className="mini" onClick={() => mesclar(s.pagadores[1].id, s.pagadores[0].id)}>Manter #{s.pagadores[1].id}</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="painel sem-padding">
        <div className="rolagem">
          <table>
            <thead>
              <tr>
                <th>Nome</th><th>CPF/CNPJ</th><th>Localidade</th>
                <th className="num">Boletos</th><th className="num">Total</th><th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && <LinhasEsqueleto linhas={5} colunas={6} />}
              {!isLoading && filtrados.length === 0 && (
                <tr><td colSpan={6}>
                  <Vazio titulo={termo ? 'Nenhum pagador encontrado' : 'Nenhum pagador ainda'}
                    descricao={termo ? 'Tente outro termo de busca.' : 'Os pagadores aparecem ao importar boletos.'} />
                </td></tr>
              )}
              {filtrados.map((p) =>
                editando === p.id ? (
                  <LinhaEdicao key={p.id} pagador={p} onSalvar={(f) => salvar(p, f)} onCancelar={() => setEditando(null)} />
                ) : (
                  <tr key={p.id}>
                    <td>
                      <div className="linha-nome">
                        <span className={`avatar ${p.provisorio ? 'provisorio' : ''}`}>{iniciais(p.nome)}</span>
                        <div>
                          <div className="principal">
                            {p.nome}
                            {p.provisorio && <span className="etiqueta provisorio" style={{ marginLeft: 7 }}>Provisório</span>}
                          </div>
                          {p.nomes_alternativos.length > 0 && (
                            <div className="apoio">Também aparece como: {p.nomes_alternativos.join(' · ')}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>{fmtCpfCnpj(p.cpf_cnpj)}</td>
                    <td>{[p.municipio, p.uf].filter(Boolean).join(' - ') || '—'}</td>
                    <td className="num">{p.qtd_boletos}</td>
                    <td className="num principal">{fmtBRL(p.total)}</td>
                    <td>
                      <div className="acoes">
                        <button className="mini" onClick={() => setEditando(p.id)}>Editar</button>
                        {p.qtd_boletos === 0 && (
                          <button className="mini fantasma perigo"
                            onClick={() => confirm(`Remover o pagador "${p.nome}"?`) && mut.mutate({ metodo: 'DELETE', path: `/pagadores/${p.id}` })}>
                            Remover
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
