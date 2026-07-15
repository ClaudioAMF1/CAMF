import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend } from '../api'
import AuditDrawer from '../components/AuditDrawer'
import ExportButtons from '../components/ExportButtons'
import FiltrosBar from '../components/FiltrosBar'
import { useFiltros } from '../filtros'
import { fmtBRL, fmtData, ROTULOS_DIVERGENCIA, ROTULOS_SITUACAO } from '../format'

const COLUNAS = [
  ['pagador', 'Pagador'],
  ['num_documento', 'Nº Doc.'],
  ['vencimento', 'Vencimento'],
  ['valor', 'Valor'],
  ['situacao', 'Situação'],
  ['qualidade', 'Qualidade'],
]

function LinhaEdicao({ boleto, onSalvar, onCancelar }) {
  const [form, setForm] = useState({
    vencimento: boleto.vencimento || '',
    valor: boleto.valor,
    num_documento: boleto.num_documento || '',
    observacao: boleto.observacao || '',
  })
  const mudar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }))
  return (
    <tr>
      <td>{boleto.pagador_nome}</td>
      <td><input style={{ width: 90 }} value={form.num_documento} onChange={mudar('num_documento')} /></td>
      <td><input type="date" value={form.vencimento} onChange={mudar('vencimento')} /></td>
      <td><input style={{ width: 100 }} value={form.valor} onChange={mudar('valor')} /></td>
      <td colSpan={2}>
        <input style={{ width: '100%' }} placeholder="Observação" value={form.observacao} onChange={mudar('observacao')} />
      </td>
      <td>
        <div className="acoes">
          <button className="mini primario" onClick={() => onSalvar(form)}>Salvar</button>
          <button className="mini" onClick={onCancelar}>Cancelar</button>
        </div>
      </td>
    </tr>
  )
}

function ModalPagar({ boleto, onConfirmar, onFechar }) {
  const hoje = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({ data_pagamento: hoje, valor_pago: boleto.valor })
  return (
    <>
      <div className="drawer-fundo" onClick={onFechar} />
      <div className="drawer" style={{ width: 340 }}>
        <h3>Marcar boleto #{boleto.id} como pago</h3>
        <label className="filtro" style={{ marginBottom: 10 }}>
          Data do pagamento
          <input type="date" value={form.data_pagamento}
            onChange={(e) => setForm((f) => ({ ...f, data_pagamento: e.target.value }))} />
        </label>
        <label className="filtro" style={{ marginBottom: 14 }}>
          Valor pago
          <input value={form.valor_pago}
            onChange={(e) => setForm((f) => ({ ...f, valor_pago: e.target.value }))} />
        </label>
        <div className="acoes">
          <button className="primario" onClick={() => onConfirmar(form)}>Confirmar</button>
          <button onClick={onFechar}>Cancelar</button>
        </div>
      </div>
    </>
  )
}

export default function BoletosPage() {
  const { ativos } = useFiltros()
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState('-vencimento')
  const [incluirDeletados, setIncluirDeletados] = useState(false)
  const [editando, setEditando] = useState(null)
  const [pagando, setPagando] = useState(null)
  const [drawerId, setDrawerId] = useState(null)
  const queryClient = useQueryClient()

  const params = { ...ativos, page, size: 25, sort, incluir_deletados: incluirDeletados }
  const { data, isLoading } = useQuery({
    queryKey: ['boletos', params],
    queryFn: () => apiGet('/boletos', params),
  })

  const invalidar = () => queryClient.invalidateQueries()
  const mut = useMutation({
    mutationFn: ({ metodo, path, corpo }) => apiSend(metodo, path, corpo),
    onSuccess: invalidar,
    onError: (e) => alert(e.message || 'Erro'),
  })

  const ordenar = (chave) => {
    setSort((s) => (s === chave ? `-${chave}` : chave))
    setPage(1)
  }

  return (
    <div>
      <div className="cabecalho-pagina">
        <div>
          <h2>Boletos</h2>
          <div className="subtitulo">Linhas amarelas precisam de revisão manual — as divergências aparecem abaixo do pagador.</div>
        </div>
        <ExportButtons />
      </div>
      <FiltrosBar />
      <label className="check" style={{ marginBottom: 10 }}>
        <input type="checkbox" checked={incluirDeletados}
          onChange={(e) => { setIncluirDeletados(e.target.checked); setPage(1) }} />
        Incluir deletados
      </label>

      <div className="painel tabela-envolto">
        <table>
          <thead>
            <tr>
              {COLUNAS.map(([chave, rotulo]) => (
                <th key={chave} className="ordenavel" onClick={() => ordenar(chave)}>
                  {rotulo}{sort.replace('-', '') === chave ? (sort.startsWith('-') ? ' ↓' : ' ↑') : ''}
                </th>
              ))}
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} className="vazio">Carregando…</td></tr>}
            {data?.items.length === 0 && <tr><td colSpan={7} className="vazio">Nenhum boleto encontrado.</td></tr>}
            {(data?.items || []).map((b) =>
              editando === b.id ? (
                <LinhaEdicao
                  key={b.id} boleto={b}
                  onSalvar={(form) => {
                    mut.mutate({
                      metodo: 'PATCH', path: `/boletos/${b.id}`,
                      corpo: {
                        vencimento: form.vencimento || null,
                        valor: form.valor,
                        num_documento: form.num_documento || null,
                        observacao: form.observacao || null,
                      },
                    })
                    setEditando(null)
                  }}
                  onCancelar={() => setEditando(null)}
                />
              ) : (
                <tr key={b.id} className={`${b.qualidade === 'revisao_manual' ? 'revisao' : ''} ${b.deletado_em ? 'deletado' : ''}`}>
                  <td>
                    <span className="celula-principal">{b.pagador_nome}</span>
                    {b.qualidade === 'revisao_manual' && (
                      <div className="divergencias">
                        ⚠ {(b.divergencias || []).map((d) => ROTULOS_DIVERGENCIA[d] || d).join('; ')}
                      </div>
                    )}
                  </td>
                  <td>{b.num_documento || '—'}</td>
                  <td>{fmtData(b.vencimento)}</td>
                  <td className="num">{fmtBRL(b.valor)}</td>
                  <td>
                    <span className={`tag ${b.situacao}`}>{ROTULOS_SITUACAO[b.situacao]}</span>
                    {b.vencido && <span className="tag vencido" style={{ marginLeft: 4 }}>Vencido</span>}
                  </td>
                  <td>{b.qualidade === 'revisao_manual' ? <span className="tag revisao">Revisão</span> : 'OK'}</td>
                  <td>
                    <div className="acoes">
                      {!b.deletado_em && b.situacao === 'aberto' && (
                        <button className="mini primario" onClick={() => setPagando(b)}>Pagar</button>
                      )}
                      {!b.deletado_em && <button className="mini" onClick={() => setEditando(b.id)}>Editar</button>}
                      <button className="mini" onClick={() => setDrawerId(b.id)}>Histórico</button>
                      {!b.deletado_em ? (
                        <button className="mini perigo" onClick={() => mut.mutate({ metodo: 'DELETE', path: `/boletos/${b.id}` })}>
                          Deletar
                        </button>
                      ) : (
                        <button className="mini" onClick={() => mut.mutate({ metodo: 'POST', path: `/boletos/${b.id}/restaurar` })}>
                          Restaurar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
        {data && (
          <div className="paginacao">
            <span className="info">{data.total} boleto(s)</span>
            <button className="mini" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Anterior</button>
            <span>página {data.page} de {data.pages}</span>
            <button className="mini" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Próxima ›</button>
          </div>
        )}
      </div>

      {pagando && (
        <ModalPagar
          boleto={pagando} onFechar={() => setPagando(null)}
          onConfirmar={(form) => {
            mut.mutate({ metodo: 'POST', path: `/boletos/${pagando.id}/pagar`, corpo: form })
            setPagando(null)
          }}
        />
      )}
      <AuditDrawer boletoId={drawerId} onFechar={() => setDrawerId(null)} />
    </div>
  )
}
