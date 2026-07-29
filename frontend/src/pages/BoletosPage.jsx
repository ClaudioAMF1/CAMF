import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend } from '../api'
import AuditDrawer from '../components/AuditDrawer'
import ExportButtons from '../components/ExportButtons'
import FiltrosBar from '../components/FiltrosBar'
import { useFiltros } from '../filtros'
import { fmtBRL, fmtCpfCnpj, fmtData, ROTULOS_DIVERGENCIA, ROTULOS_SITUACAO } from '../format'
import { IconSeta } from '../icons'
import { LinhasEsqueleto, Modal, useToast, Vazio } from '../ui'

const hojeISO = () => new Date().toISOString().slice(0, 10)

function iniciais(nome = '') {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  if (!partes.length) return '?'
  return ((partes[0][0] || '') + (partes.length > 1 ? partes[partes.length - 1][0] : '')).toUpperCase()
}

function Situacao({ b }) {
  return (
    <>
      <span className={`etiqueta ${b.situacao}`}>{ROTULOS_SITUACAO[b.situacao]}</span>
      {b.vencido && <span className="etiqueta vencido" style={{ marginLeft: 5 }}>Vencido</span>}
    </>
  )
}

/* ---------- Modal de baixa (individual ou em lote) ---------- */

function ModalPagar({ alvo, onConfirmar, onFechar }) {
  const emLote = Array.isArray(alvo)
  const total = emLote ? alvo.reduce((s, b) => s + Number(b.valor), 0) : Number(alvo.valor)
  const [form, setForm] = useState({
    data_pagamento: hojeISO(),
    valor_pago: emLote ? '' : alvo.valor,
  })

  return (
    <Modal titulo={emLote ? `Baixar ${alvo.length} boletos` : 'Registrar pagamento'} onFechar={onFechar}>
      <div style={{ color: 'var(--tinta-3)', fontSize: 13, marginBottom: 16 }}>
        Total selecionado: <strong style={{ color: 'var(--tinta)' }}>{fmtBRL(total)}</strong>
      </div>
      <label className="campo" style={{ marginBottom: 13 }}>
        <span>Data do pagamento</span>
        <input type="date" value={form.data_pagamento}
          onChange={(e) => setForm((f) => ({ ...f, data_pagamento: e.target.value }))} />
      </label>
      <label className="campo" style={{ marginBottom: 18 }}>
        <span>Valor pago {emLote && '(opcional)'}</span>
        <input
          value={form.valor_pago}
          placeholder={emLote ? 'Cada boleto pelo próprio valor' : ''}
          onChange={(e) => setForm((f) => ({ ...f, valor_pago: e.target.value }))}
        />
      </label>
      <div className="acoes">
        <button className="principal-btn" onClick={() => onConfirmar(form)}>Confirmar baixa</button>
        <button onClick={onFechar}>Cancelar</button>
      </div>
    </Modal>
  )
}

/* ---------- Edição inline ---------- */

function LinhaEdicao({ boleto, onSalvar, onCancelar, colunas }) {
  const [form, setForm] = useState({
    vencimento: boleto.vencimento || '',
    valor: boleto.valor,
    num_documento: boleto.num_documento || '',
    observacao: boleto.observacao || '',
  })
  const mudar = (c) => (e) => setForm((f) => ({ ...f, [c]: e.target.value }))
  return (
    <tr>
      <td colSpan={colunas}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label className="campo"><span>Nº doc.</span><input style={{ width: 96 }} value={form.num_documento} onChange={mudar('num_documento')} /></label>
          <label className="campo"><span>Vencimento</span><input type="date" value={form.vencimento} onChange={mudar('vencimento')} /></label>
          <label className="campo"><span>Valor</span><input style={{ width: 110 }} value={form.valor} onChange={mudar('valor')} /></label>
          <label className="campo" style={{ flex: 1, minWidth: 180 }}><span>Observação</span><input value={form.observacao} onChange={mudar('observacao')} /></label>
          <button className="principal-btn mini" onClick={() => onSalvar(form)}>Salvar</button>
          <button className="mini" onClick={onCancelar}>Cancelar</button>
        </div>
      </td>
    </tr>
  )
}

/* ---------- Linhas de boleto (usadas nos dois modos) ---------- */

function LinhaBoleto({ b, selecionados, alternar, acoes, colunas, editando, setEditando, onSalvar }) {
  if (editando === b.id) {
    return <LinhaEdicao boleto={b} colunas={colunas} onSalvar={(f) => onSalvar(b, f)} onCancelar={() => setEditando(null)} />
  }
  const marcado = selecionados.has(b.id)
  return (
    <tr className={`${b.qualidade === 'revisao_manual' ? 'revisao' : ''} ${b.deletado_em ? 'deletado' : ''} ${marcado ? 'selecionada' : ''}`}>
      <td style={{ width: 34 }}>
        {!b.deletado_em && b.situacao === 'aberto' && (
          <input type="checkbox" checked={marcado} onChange={() => alternar(b)} aria-label={`Selecionar boleto ${b.num_documento || b.id}`} />
        )}
      </td>
      <td className="principal">{b.num_documento || `#${b.id}`}</td>
      <td>{fmtData(b.vencimento)}</td>
      <td className="num principal">{fmtBRL(b.valor)}</td>
      <td><Situacao b={b} /></td>
      <td>
        {b.qualidade === 'revisao_manual' ? (
          <>
            <span className="etiqueta revisao">Revisão</span>
            <div className="divergencia">{(b.divergencias || []).map((d) => ROTULOS_DIVERGENCIA[d] || d).join('; ')}</div>
          </>
        ) : (
          <span style={{ color: 'var(--tinta-fraca)' }}>OK</span>
        )}
      </td>
      <td>{acoes(b)}</td>
    </tr>
  )
}

/* ---------- Modo agrupado: uma linha por pessoa ---------- */

function GrupoPagador({ grupo, filtros, selecionados, alternar, acoes, editando, setEditando, onSalvar }) {
  const [aberto, setAberto] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ['boletos-do-pagador', grupo.pagador_id, filtros],
    queryFn: () => apiGet('/boletos', { ...filtros, pagador_id: grupo.pagador_id, size: 200, sort: 'vencimento' }),
    enabled: aberto,
  })

  const pct = (v) => (grupo.total > 0 ? (Number(v) / Number(grupo.total)) * 100 : 0)

  return (
    <>
      <tr className="clicavel" onClick={() => setAberto((a) => !a)}>
        <td>
          <div className="linha-nome">
            <span className={`seta ${aberto ? 'aberta' : ''}`}><IconSeta /></span>
            <span className={`avatar ${grupo.provisorio ? 'provisorio' : ''}`}>{iniciais(grupo.nome)}</span>
            <div>
              <div className="principal">
                {grupo.nome}
                {grupo.provisorio && <span className="etiqueta provisorio" style={{ marginLeft: 7 }}>Provisório</span>}
                {grupo.qtd_revisao > 0 && <span className="etiqueta revisao" style={{ marginLeft: 5 }}>{grupo.qtd_revisao} p/ revisão</span>}
              </div>
              <div className="apoio">{fmtCpfCnpj(grupo.cpf_cnpj)}</div>
            </div>
          </div>
        </td>
        <td className="num">{grupo.qtd}</td>
        <td>
          <div className="barra-mix" title={`Aberto ${fmtBRL(grupo.total_aberto)} · Pago ${fmtBRL(grupo.total_pago)} · Vencido ${fmtBRL(grupo.total_vencido)}`}>
            <span className="b-pago" style={{ width: `${pct(grupo.total_pago)}%` }} />
            <span className="b-vencido" style={{ width: `${pct(grupo.total_vencido)}%` }} />
            <span className="b-aberto" style={{ width: `${pct(Number(grupo.total_aberto) - Number(grupo.total_vencido))}%` }} />
          </div>
        </td>
        <td className="num">{grupo.qtd_pago > 0 ? <span style={{ color: 'var(--verde)' }}>{fmtBRL(grupo.total_pago)}</span> : <span style={{ color: 'var(--tinta-fraca)' }}>—</span>}</td>
        <td className="num">{Number(grupo.total_vencido) > 0 ? <span style={{ color: 'var(--vermelho)' }}>{fmtBRL(grupo.total_vencido)}</span> : <span style={{ color: 'var(--tinta-fraca)' }}>—</span>}</td>
        <td>{grupo.proximo_vencimento ? fmtData(grupo.proximo_vencimento) : <span style={{ color: 'var(--tinta-fraca)' }}>—</span>}</td>
        <td className="num principal">{fmtBRL(grupo.total)}</td>
      </tr>
      {aberto && (
        <tr className="gaveta abrindo">
          <td colSpan={7}>
            <div className="gaveta-interna">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 34 }} />
                    <th>Nº doc.</th><th>Vencimento</th><th className="num">Valor</th>
                    <th>Situação</th><th>Qualidade</th><th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && <LinhasEsqueleto linhas={Math.min(grupo.qtd, 4)} colunas={7} />}
                  {(data?.items || []).map((b) => (
                    <LinhaBoleto
                      key={b.id} b={b} colunas={7}
                      selecionados={selecionados} alternar={alternar} acoes={acoes}
                      editando={editando} setEditando={setEditando} onSalvar={onSalvar}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

/* ---------- Página ---------- */

export default function BoletosPage() {
  const { ativos } = useFiltros()
  const [modo, setModo] = useState('agrupado')
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState('-vencimento')
  const [incluirDeletados, setIncluirDeletados] = useState(false)
  const [selecionados, setSelecionados] = useState(new Map())
  const [editando, setEditando] = useState(null)
  const [pagando, setPagando] = useState(null)
  const [drawerId, setDrawerId] = useState(null)
  const queryClient = useQueryClient()
  const notificar = useToast()

  const paramsLista = { ...ativos, page, size: 25, sort, incluir_deletados: incluirDeletados }

  const grupos = useQuery({
    queryKey: ['por-pagador', ativos],
    queryFn: () => apiGet('/boletos/por-pagador', ativos),
    enabled: modo === 'agrupado',
  })
  const lista = useQuery({
    queryKey: ['boletos', paramsLista],
    queryFn: () => apiGet('/boletos', paramsLista),
    enabled: modo === 'lista',
  })

  const aoErro = (e) => notificar(typeof e.detail === 'string' ? e.detail : e.message || 'Erro', 'erro')
  const invalidar = () => queryClient.invalidateQueries()

  const mut = useMutation({
    mutationFn: ({ metodo, path, corpo }) => apiSend(metodo, path, corpo),
    onSuccess: invalidar,
    onError: aoErro,
  })

  const alternar = (b) =>
    setSelecionados((m) => {
      const novo = new Map(m)
      novo.has(b.id) ? novo.delete(b.id) : novo.set(b.id, b)
      return novo
    })

  const salvarEdicao = (b, form) => {
    mut.mutate({
      metodo: 'PATCH', path: `/boletos/${b.id}`,
      corpo: {
        vencimento: form.vencimento || null,
        valor: form.valor,
        num_documento: form.num_documento || null,
        observacao: form.observacao || null,
      },
    }, { onSuccess: () => { invalidar(); notificar('Boleto atualizado') } })
    setEditando(null)
  }

  const confirmarPagamento = (form) => {
    const emLote = Array.isArray(pagando)
    const corpoComum = {
      data_pagamento: form.data_pagamento,
      ...(form.valor_pago ? { valor_pago: form.valor_pago } : {}),
    }
    if (emLote) {
      apiSend('POST', '/boletos/pagar-lote', { ids: pagando.map((b) => b.id), ...corpoComum })
        .then((r) => { invalidar(); setSelecionados(new Map()); notificar(`${r.pagos} boleto(s) baixados`) })
        .catch(aoErro)
    } else {
      apiSend('POST', `/boletos/${pagando.id}/pagar`, { valor_pago: pagando.valor, ...corpoComum })
        .then(() => { invalidar(); notificar('Pagamento registrado') })
        .catch(aoErro)
    }
    setPagando(null)
  }

  const acoes = (b) => (
    <div className="acoes" onClick={(e) => e.stopPropagation()}>
      {!b.deletado_em && b.situacao === 'aberto' && (
        <button className="principal-btn mini" onClick={() => setPagando(b)}>Pagar</button>
      )}
      {!b.deletado_em && <button className="mini" onClick={() => setEditando(b.id)}>Editar</button>}
      <button className="mini fantasma" onClick={() => setDrawerId(b.id)}>Histórico</button>
      {!b.deletado_em ? (
        <button className="mini fantasma perigo" onClick={() => mut.mutate({ metodo: 'DELETE', path: `/boletos/${b.id}` })}>Deletar</button>
      ) : (
        <button className="mini" onClick={() => mut.mutate({ metodo: 'POST', path: `/boletos/${b.id}/restaurar` })}>Restaurar</button>
      )}
    </div>
  )

  const ordenar = (chave) => { setSort((s) => (s === chave ? `-${chave}` : chave)); setPage(1) }
  const seta = (chave) => (sort.replace('-', '') === chave ? (sort.startsWith('-') ? ' ↓' : ' ↑') : '')

  const totalGeral = (grupos.data || []).reduce((s, g) => s + Number(g.total), 0)
  const totalBoletos = (grupos.data || []).reduce((s, g) => s + g.qtd, 0)

  return (
    <div>
      <div className="topo">
        <div>
          <h2>Boletos</h2>
          <div className="sub">
            {modo === 'agrupado'
              ? 'Cada pessoa aparece uma única vez — clique no nome para ver os boletos dela.'
              : 'Lista completa. Linhas amarelas precisam de revisão manual.'}
          </div>
        </div>
        <div className="acoes">
          <div className="segmentado">
            <button className={modo === 'agrupado' ? 'ativo' : ''} onClick={() => setModo('agrupado')}>Por pessoa</button>
            <button className={modo === 'lista' ? 'ativo' : ''} onClick={() => setModo('lista')}>Lista</button>
          </div>
          <ExportButtons />
        </div>
      </div>

      <FiltrosBar />

      {modo === 'lista' && (
        <label className="marcador" style={{ marginBottom: 11 }}>
          <input type="checkbox" checked={incluirDeletados}
            onChange={(e) => { setIncluirDeletados(e.target.checked); setPage(1) }} />
          Incluir deletados
        </label>
      )}

      <div className="painel sem-padding">
        <div className="rolagem">
          {modo === 'agrupado' ? (
            <table>
              <thead>
                <tr>
                  <th>Pagador</th>
                  <th className="num">Boletos</th>
                  <th>Composição</th>
                  <th className="num">Pago</th>
                  <th className="num">Vencido</th>
                  <th>Próx. vencimento</th>
                  <th className="num">Total</th>
                </tr>
              </thead>
              <tbody>
                {grupos.isLoading && <LinhasEsqueleto linhas={5} colunas={7} />}
                {grupos.data?.length === 0 && (
                  <tr><td colSpan={7}>
                    <Vazio titulo="Nenhum boleto encontrado" descricao="Ajuste os filtros ou envie novos PDFs." />
                  </td></tr>
                )}
                {(grupos.data || []).map((g) => (
                  <GrupoPagador
                    key={g.pagador_id} grupo={g} filtros={ativos}
                    selecionados={selecionados} alternar={alternar} acoes={acoes}
                    editando={editando} setEditando={setEditando} onSalvar={salvarEdicao}
                  />
                ))}
                {!!grupos.data?.length && (
                  <tr className="total">
                    <td>TOTAL — {grupos.data.length} pagador(es)</td>
                    <td className="num">{totalBoletos}</td>
                    <td colSpan={4} />
                    <td className="num">{fmtBRL(totalGeral)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : (
            <table>
              <thead>
                <tr>
                  <th style={{ width: 34 }} />
                  <th className="ordenavel" onClick={() => ordenar('pagador')}>Pagador{seta('pagador')}</th>
                  <th className="ordenavel" onClick={() => ordenar('num_documento')}>Nº doc.{seta('num_documento')}</th>
                  <th className="ordenavel" onClick={() => ordenar('vencimento')}>Vencimento{seta('vencimento')}</th>
                  <th className="ordenavel num" onClick={() => ordenar('valor')}>Valor{seta('valor')}</th>
                  <th className="ordenavel" onClick={() => ordenar('situacao')}>Situação{seta('situacao')}</th>
                  <th>Qualidade</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {lista.isLoading && <LinhasEsqueleto linhas={6} colunas={8} />}
                {lista.data?.items.length === 0 && (
                  <tr><td colSpan={8}><Vazio titulo="Nenhum boleto encontrado" descricao="Ajuste os filtros ou envie novos PDFs." /></td></tr>
                )}
                {(lista.data?.items || []).map((b) =>
                  editando === b.id ? (
                    <LinhaEdicao key={b.id} boleto={b} colunas={8} onSalvar={(f) => salvarEdicao(b, f)} onCancelar={() => setEditando(null)} />
                  ) : (
                    <tr key={b.id} className={`${b.qualidade === 'revisao_manual' ? 'revisao' : ''} ${b.deletado_em ? 'deletado' : ''} ${selecionados.has(b.id) ? 'selecionada' : ''}`}>
                      <td>
                        {!b.deletado_em && b.situacao === 'aberto' && (
                          <input type="checkbox" checked={selecionados.has(b.id)} onChange={() => alternar(b)} aria-label={`Selecionar boleto ${b.num_documento || b.id}`} />
                        )}
                      </td>
                      <td>
                        <div className="linha-nome">
                          <span className="avatar">{iniciais(b.pagador_nome)}</span>
                          <span className="principal">{b.pagador_nome}</span>
                        </div>
                      </td>
                      <td>{b.num_documento || `#${b.id}`}</td>
                      <td>{fmtData(b.vencimento)}</td>
                      <td className="num principal">{fmtBRL(b.valor)}</td>
                      <td><Situacao b={b} /></td>
                      <td>
                        {b.qualidade === 'revisao_manual' ? (
                          <>
                            <span className="etiqueta revisao">Revisão</span>
                            <div className="divergencia">{(b.divergencias || []).map((d) => ROTULOS_DIVERGENCIA[d] || d).join('; ')}</div>
                          </>
                        ) : <span style={{ color: 'var(--tinta-fraca)' }}>OK</span>}
                      </td>
                      <td>{acoes(b)}</td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          )}
        </div>

        {modo === 'lista' && lista.data && (
          <div className="paginacao">
            <span className="contagem">{lista.data.total} boleto(s)</span>
            <button className="mini" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Anterior</button>
            <span>página {lista.data.page} de {lista.data.pages}</span>
            <button className="mini" disabled={page >= lista.data.pages} onClick={() => setPage(page + 1)}>Próxima ›</button>
          </div>
        )}
      </div>

      {selecionados.size > 0 && (
        <div className="barra-lote">
          <strong>{selecionados.size} boleto(s) selecionado(s)</strong>
          <span style={{ opacity: .75 }}>
            {fmtBRL([...selecionados.values()].reduce((s, b) => s + Number(b.valor), 0))}
          </span>
          <div className="acoes" style={{ marginLeft: 'auto' }}>
            <button className="principal-btn" onClick={() => setPagando([...selecionados.values()])}>
              Marcar como pagos
            </button>
            <button onClick={() => setSelecionados(new Map())}>Limpar seleção</button>
          </div>
        </div>
      )}

      {pagando && <ModalPagar alvo={pagando} onFechar={() => setPagando(null)} onConfirmar={confirmarPagamento} />}
      <AuditDrawer boletoId={drawerId} onFechar={() => setDrawerId(null)} />
    </div>
  )
}
