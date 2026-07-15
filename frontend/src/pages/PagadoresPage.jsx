import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend } from '../api'
import { fmtBRL, fmtCpfCnpj } from '../format'

function LinhaEdicao({ pagador, onSalvar, onCancelar }) {
  const [form, setForm] = useState({
    nome: pagador.nome,
    cpf_cnpj: pagador.cpf_cnpj || '',
    municipio: pagador.municipio || '',
    uf: pagador.uf || '',
  })
  const mudar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }))
  return (
    <tr>
      <td><input value={form.nome} onChange={mudar('nome')} style={{ width: '100%' }} /></td>
      <td><input value={form.cpf_cnpj} onChange={mudar('cpf_cnpj')} placeholder="CPF/CNPJ" /></td>
      <td>
        <input value={form.municipio} onChange={mudar('municipio')} style={{ width: 130 }} placeholder="Município" />{' '}
        <input value={form.uf} onChange={mudar('uf')} style={{ width: 44 }} placeholder="UF" maxLength={2} />
      </td>
      <td colSpan={2}>
        <div className="acoes">
          <button className="mini primario" onClick={() => onSalvar(form)}>Salvar</button>
          <button className="mini" onClick={onCancelar}>Cancelar</button>
        </div>
      </td>
      <td></td>
    </tr>
  )
}

export default function PagadoresPage() {
  const [editando, setEditando] = useState(null)
  const queryClient = useQueryClient()

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
    onError: (e) => alert(typeof e.detail === 'string' ? e.detail : e.message),
  })

  const salvar = (pagador, form) => {
    const corpo = { nome: form.nome, municipio: form.municipio || null, uf: form.uf || null }
    if (form.cpf_cnpj && form.cpf_cnpj !== (pagador.cpf_cnpj || '')) corpo.cpf_cnpj = form.cpf_cnpj
    mut.mutate({ metodo: 'PATCH', path: `/pagadores/${pagador.id}`, corpo })
    setEditando(null)
  }

  const mesclar = (destinoId, origemId) => {
    if (confirm(`Migrar os boletos do pagador #${origemId} para o #${destinoId} e arquivar a origem?`)) {
      mut.mutate({ metodo: 'POST', path: `/pagadores/${destinoId}/merge`, corpo: { pagador_origem_id: origemId } })
    }
  }

  return (
    <div>
      <h2>Pagadores</h2>

      {!!sugestoes?.length && (
        <div className="painel" style={{ borderLeft: '4px solid #eda100' }}>
          <div className="grafico-titulo">
            Sugestões de merge — mesmo nome, documentos diferentes (a decisão é sua; nada é mesclado automaticamente)
          </div>
          {sugestoes.map((s) => (
            <div key={s.nome_normalizado} style={{ marginBottom: 8 }}>
              <strong>{s.nome_normalizado}</strong>
              <div className="acoes" style={{ marginTop: 4 }}>
                {s.pagadores.map((p) => (
                  <span key={p.id} className="tag aberto">
                    #{p.id} {fmtCpfCnpj(p.cpf_cnpj) || 'sem documento'}
                  </span>
                ))}
                {s.pagadores.length === 2 && (
                  <>
                    <button className="mini" onClick={() => mesclar(s.pagadores[0].id, s.pagadores[1].id)}>
                      Manter #{s.pagadores[0].id}
                    </button>
                    <button className="mini" onClick={() => mesclar(s.pagadores[1].id, s.pagadores[0].id)}>
                      Manter #{s.pagadores[1].id}
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="painel scroll-x">
        <table>
          <thead>
            <tr>
              <th>Nome</th><th>CPF/CNPJ</th><th>Localidade</th>
              <th className="num">Boletos</th><th className="num">Total</th><th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="vazio">Carregando…</td></tr>}
            {(pagadores || []).map((p) =>
              editando === p.id ? (
                <LinhaEdicao key={p.id} pagador={p} onSalvar={(f) => salvar(p, f)} onCancelar={() => setEditando(null)} />
              ) : (
                <tr key={p.id}>
                  <td>
                    {p.nome}
                    {p.provisorio && <span className="tag provisorio" style={{ marginLeft: 6 }}>Provisório</span>}
                    {p.nomes_alternativos.length > 0 && (
                      <div style={{ fontSize: 11, color: '#898781', marginTop: 2 }}>
                        Também aparece como: {p.nomes_alternativos.join(' · ')}
                      </div>
                    )}
                  </td>
                  <td>{fmtCpfCnpj(p.cpf_cnpj)}</td>
                  <td>{[p.municipio, p.uf].filter(Boolean).join(' - ') || '—'}</td>
                  <td className="num">{p.qtd_boletos}</td>
                  <td className="num">{fmtBRL(p.total)}</td>
                  <td><button className="mini" onClick={() => setEditando(p.id)}>Editar</button></td>
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
