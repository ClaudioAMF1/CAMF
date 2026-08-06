import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend } from '../api'
import AuditDrawer from '../components/AuditDrawer'
import ExportButtons from '../components/ExportButtons'
import FiltrosBar from '../components/FiltrosBar'
import PdfViewer from '../components/PdfViewer'
import { useFiltros } from '../filtros'
import { fmtBRL, fmtCpfCnpj, fmtData, ROTULOS_DIVERGENCIA, ROTULOS_SITUACAO } from '../format'
import { IconBaixar, IconHistorico, IconLixeira, IconOlho, IconSeta } from '../icons'
import { LinhasEsqueleto, Modal, useToast, Vazio } from '../ui'

const hojeISO = () => new Date().toISOString().slice(0, 10)

function iniciais(nome = '') {
  const p = nome.trim().split(/\s+/).filter(Boolean)
  if (!p.length) return '?'
  return ((p[0][0] || '') + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase()
}

function Situacao({ b }) {
  return (
    <>
      <span className={`etiqueta ${b.situacao}`}>{ROTULOS_SITUACAO[b.situacao]}</span>
      {b.vencido && <span className="etiqueta vencido" style={{ marginLeft: 4 }}>Vencido</span>}
    </>
  )
}

function ModalPagar({ alvo, onConfirmar, onFechar }) {
  const emLote = Array.isArray(alvo)
  // Só soma quando conhecemos o valor de todos (seleção por pessoa não traz)
  const total = emLote
    ? (alvo.every((b) => b.valor) ? alvo.reduce((s, b) => s + Number(b.valor), 0) : null)
    : Number(alvo.valor)
  const [form, setForm] = useState({
    data_pagamento: hojeISO(),
    valor_pago: emLote ? '' : alvo.valor,
  })
  return (
    <Modal titulo={emLote ? `Baixar ${alvo.length} boletos` : 'Registrar pagamento'} onFechar={onFechar}>
      <div style={{ color: 'var(--tinta-3)', fontSize: 12.5, marginBottom: 16 }}>
        {total !== null
          ? <>Total: <strong style={{ color: 'var(--tinta)' }}>{fmtBRL(total)}</strong></>
          : 'Boletos já pagos são ignorados.'}
      </div>
      <label className="campo" style={{ marginBottom: 12 }}>
        <span>Data do pagamento</span>
        <input type="date" value={form.data_pagamento}
          onChange={(e) => setForm((f) => ({ ...f, data_pagamento: e.target.value }))} />
      </label>
      <label className="campo" style={{ marginBottom: 18 }}>
        <span>Valor pago {emLote && '(opcional)'}</span>
        <input value={form.valor_pago} placeholder={emLote ? 'Cada um pelo próprio valor' : ''}
          onChange={(e) => setForm((f) => ({ ...f, valor_pago: e.target.value }))} />
      </label>
      <div className="acoes">
        <button className="principal-btn" onClick={() => onConfirmar(form)}>Confirmar</button>
        <button onClick={onFechar}>Cancelar</button>
      </div>
    </Modal>
  )
}

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
          <label className="campo"><span>Nº doc.</span><input style={{ width: 92 }} value={form.num_documento} onChange={mudar('num_documento')} /></label>
          <label className="campo"><span>Vencimento</span><input type="date" value={form.vencimento} onChange={mudar('vencimento')} /></label>
          <label className="campo"><span>Valor</span><input style={{ width: 106 }} value={form.valor} onChange={mudar('valor')} /></label>
          <label className="campo" style={{ flex: 1, minWidth: 170 }}><span>Observação</span><input value={form.observacao} onChange={mudar('observacao')} /></label>
          <button className="principal-btn mini" onClick={() => onSalvar(form)}>Salvar</button>
          <button className="mini" onClick={onCancelar}>Cancelar</button>
        </div>
      </td>
    </tr>
  )
}

function LinhaBoleto({ b, marcado, alternar, acoes, editando, setEditando, onSalvar, colunas }) {
  if (editando === b.id) {
    return <LinhaEdicao boleto={b} colunas={colunas} onSalvar={(f) => onSalvar(b, f)} onCancelar={() => setEditando(null)} />
  }
  return (
    <tr className={`${b.qualidade === 'revisao_manual' ? 'revisao' : ''} ${b.deletado_em ? 'deletado' : ''} ${marcado ? 'selecionada' : ''}`}>
      <td style={{ width: 32 }}>
        <input type="checkbox" checked={marcado} onChange={() => alternar(b)}
          aria-label={`Selecionar boleto ${b.num_documento || b.id}`} />
      </td>
      <td className="principal">{b.num_documento || `#${b.id}`}</td>
      <td>{fmtData(b.vencimento)}</td>
      <td className="num principal">{fmtBRL(b.valor)}</td>
      <td><Situacao b={b} /></td>
      <td>
        {b.qualidade === 'revisao_manual' && (
          <>
            <span className="etiqueta revisao">Revisão</span>
            <div className="divergencia">{(b.divergencias || []).map((d) => ROTULOS_DIVERGENCIA[d] || d).join('; ')}</div>
          </>
        )}
      </td>
      <td>{acoes(b)}</td>
    </tr>
  )
}

function GrupoPagador({ grupo, filtros, selecionados, alternar, alternarVarios, acoes, editando, setEditando, onSalvar }) {
  const [aberto, setAberto] = useState(false)
  const { data, isLoading } = useQuery({
    queryKey: ['boletos-do-pagador', grupo.pagador_id, filtros],
    queryFn: () => apiGet('/boletos', { ...filtros, pagador_id: grupo.pagador_id, size: 200, sort: 'vencimento' }),
    enabled: aberto,
  })

  const marcados = grupo.ids.filter((id) => selecionados.has(id)).length
  const todos = marcados === grupo.ids.length && grupo.ids.length > 0
  const pct = (v) => (Number(grupo.total) > 0 ? (Number(v) / Number(grupo.total)) * 100 : 0)

  return (
    <>
      <tr className={`clicavel ${marcados > 0 ? 'selecionada' : ''}`} onClick={() => setAberto((a) => !a)}>
        <td style={{ width: 32 }} onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox" checked={todos}
            ref={(el) => el && (el.indeterminate = marcados > 0 && !todos)}
            onChange={() => alternarVarios(grupo.ids, !todos)}
            aria-label={`Selecionar os ${grupo.qtd} boletos de ${grupo.nome}`}
          />
        </td>
        <td>
          <div className="linha-nome">
            <span className={`seta ${aberto ? 'aberta' : ''}`}><IconSeta /></span>
            <span className={`avatar ${grupo.provisorio ? 'provisorio' : ''}`}>{iniciais(grupo.nome)}</span>
            <div>
              <div className="principal">
                {grupo.nome}
                {grupo.provisorio && <span className="etiqueta provisorio" style={{ marginLeft: 6 }}>Provisório</span>}
                {grupo.qtd_revisao > 0 && <span className="etiqueta revisao" style={{ marginLeft: 4 }}>{grupo.qtd_revisao} revisão</span>}
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
        <td className="num" style={{ color: grupo.qtd_pago ? 'var(--verde)' : 'var(--tinta-fraca)' }}>
          {grupo.qtd_pago ? fmtBRL(grupo.total_pago) : '—'}
        </td>
        <td className="num" style={{ color: Number(grupo.total_vencido) > 0 ? 'var(--vermelho)' : 'var(--tinta-fraca)' }}>
          {Number(grupo.total_vencido) > 0 ? fmtBRL(grupo.total_vencido) : '—'}
        </td>
        <td>{grupo.proximo_vencimento ? fmtData(grupo.proximo_vencimento) : '—'}</td>
        <td className="num principal">{fmtBRL(grupo.total)}</td>
      </tr>
      {aberto && (
        <tr className="gaveta abrindo">
          <td colSpan={8}>
            <div className="gaveta-interna">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 32 }} />
                    <th>Nº doc.</th><th>Vencimento</th><th className="num">Valor</th>
                    <th>Situação</th><th /><th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && <LinhasEsqueleto linhas={Math.min(grupo.qtd, 4)} colunas={7} />}
                  {(data?.items || []).map((b) => (
                    <LinhaBoleto
                      key={b.id} b={b} colunas={7} marcado={selecionados.has(b.id)}
                      alternar={alternar} acoes={(x) => acoes(x, grupo.nome)}
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

export default function BoletosPage() {
  const { ativos } = useFiltros()
  const [modo, setModo] = useState('agrupado')
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState('-vencimento')
  const [incluirDeletados, setIncluirDeletados] = useState(false)
  const [selecionados, setSelecionados] = useState(new Map())
  const [editando, setEditando] = useState(null)
  const [pagando, setPagando] = useState(null)
  const [vendoPdf, setVendoPdf] = useState(null)
  const [drawerId, setDrawerId] = useState(null)
  const queryClient = useQueryClient()
  const notificar = useToast()

  // "Deletados" vale nos dois modos: sem isso, o agrupado não os lista e a
  // seleção em massa não alcança nada para restaurar.
  const filtrosBase = { ...ativos, incluir_deletados: incluirDeletados }
  const paramsLista = { ...filtrosBase, page, size: 25, sort }
  const grupos = useQuery({
    queryKey: ['por-pagador', filtrosBase],
    queryFn: () => apiGet('/boletos/por-pagador', filtrosBase),
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

  // Seleciona/limpa vários de uma vez (uma pessoa inteira ou a página toda)
  const alternarVarios = (ids, marcar, mapaDados = null) =>
    setSelecionados((m) => {
      const novo = new Map(m)
      ids.forEach((id) => {
        if (marcar) novo.set(id, mapaDados?.get(id) || novo.get(id) || { id, valor: 0 })
        else novo.delete(id)
      })
      return novo
    })

  const selecao = [...selecionados.values()]
  const idsSelecionados = [...selecionados.keys()]
  // Ao marcar uma pessoa inteira não temos os dados de cada boleto; o backend
  // ignora os já pagos, então as ações ficam sempre disponíveis.

  const emLote = (path, mensagem) =>
    apiSend('POST', path, { ids: idsSelecionados })
      .then((r) => {
        invalidar()
        setSelecionados(new Map())
        notificar(`${r.afetados} ${mensagem}`)
      })
      .catch(aoErro)

  const deletarSelecionados = () => {
    if (!confirm(`Deletar ${idsSelecionados.length} boleto(s)? Ficam arquivados e podem ser restaurados.`)) return
    emLote('/boletos/deletar-lote', 'boleto(s) deletados')
  }

  const salvarEdicao = (b, form) => {
    mut.mutate(
      {
        metodo: 'PATCH', path: `/boletos/${b.id}`,
        corpo: {
          vencimento: form.vencimento || null, valor: form.valor,
          num_documento: form.num_documento || null, observacao: form.observacao || null,
        },
      },
      { onSuccess: () => { invalidar(); notificar('Boleto atualizado') } }
    )
    setEditando(null)
  }

  const confirmarPagamento = (form) => {
    const corpo = {
      data_pagamento: form.data_pagamento,
      ...(form.valor_pago ? { valor_pago: form.valor_pago } : {}),
    }
    const promessa = Array.isArray(pagando)
      ? apiSend('POST', '/boletos/pagar-lote', { ids: pagando.map((b) => b.id), ...corpo })
          .then((r) => notificar(`${r.pagos} boleto(s) baixados`))
      : apiSend('POST', `/boletos/${pagando.id}/pagar`, { valor_pago: pagando.valor, ...corpo })
          .then(() => notificar('Pagamento registrado'))
    promessa.then(() => { invalidar(); setSelecionados(new Map()) }).catch(aoErro)
    setPagando(null)
  }

  const acoes = (b, nomePagador) => (
    <div className="acoes" onClick={(e) => e.stopPropagation()}>
      <button className="mini" title="Ver o boleto em PDF"
        onClick={() => setVendoPdf({ ...b, pagador_nome: b.pagador_nome || nomePagador })}>
        <IconOlho /> PDF
      </button>
      <a className="botao mini so-icone" href={`/api/boletos/${b.id}/pdf`} download title="Baixar o PDF">
        <IconBaixar />
      </a>
      {!b.deletado_em && b.situacao === 'aberto' && (
        <button className="principal-btn mini" onClick={() => setPagando(b)}>Pagar</button>
      )}
      {!b.deletado_em && <button className="mini" onClick={() => setEditando(b.id)}>Editar</button>}
      <button className="mini fantasma so-icone" title="Histórico" onClick={() => setDrawerId(b.id)}>
        <IconHistorico />
      </button>
      {!b.deletado_em ? (
        <button className="mini fantasma perigo so-icone" title="Deletar"
          onClick={() => mut.mutate({ metodo: 'DELETE', path: `/boletos/${b.id}` })}>
          <IconLixeira />
        </button>
      ) : (
        <button className="mini" onClick={() => mut.mutate({ metodo: 'POST', path: `/boletos/${b.id}/restaurar` })}>
          Restaurar
        </button>
      )}
    </div>
  )

  const ordenar = (c) => { setSort((s) => (s === c ? `-${c}` : c)); setPage(1) }
  const seta = (c) => (sort.replace('-', '') === c ? (sort.startsWith('-') ? ' ↓' : ' ↑') : '')

  const todosGrupos = (grupos.data || []).flatMap((g) => g.ids)
  const idsPagina = (lista.data?.items || []).map((b) => b.id)
  const mapaPagina = new Map((lista.data?.items || []).map((b) => [b.id, b]))
  const idsVisiveis = modo === 'agrupado' ? todosGrupos : idsPagina
  const todosMarcados = idsVisiveis.length > 0 && idsVisiveis.every((id) => selecionados.has(id))

  return (
    <div>
      <div className="topo">
        <div>
          <h2>Boletos</h2>
          <div className="sub">Marque para pagar, baixar ou deletar em lote.</div>
        </div>
        <div className="acoes">
          <div className="segmentado">
            <button className={modo === 'agrupado' ? 'ativo' : ''} onClick={() => setModo('agrupado')}>Por pessoa</button>
            <button className={modo === 'lista' ? 'ativo' : ''} onClick={() => setModo('lista')}>Lista</button>
          </div>
          <ExportButtons />
        </div>
      </div>

      <FiltrosBar>
        <label className="marcador">
          <input type="checkbox" checked={incluirDeletados}
            onChange={(e) => { setIncluirDeletados(e.target.checked); setPage(1) }} />
          Deletados
        </label>
      </FiltrosBar>

      <div className="painel sem-padding">
        <div className="rolagem">
          {modo === 'agrupado' ? (
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }}>
                    <input type="checkbox" checked={todosMarcados}
                      onChange={() => alternarVarios(todosGrupos, !todosMarcados)}
                      aria-label="Selecionar todos" />
                  </th>
                  <th>Pagador</th>
                  <th className="num">Qtd</th>
                  <th>Composição</th>
                  <th className="num">Pago</th>
                  <th className="num">Vencido</th>
                  <th>Próx. venc.</th>
                  <th className="num">Total</th>
                </tr>
              </thead>
              <tbody>
                {grupos.isLoading && <LinhasEsqueleto linhas={5} colunas={8} />}
                {grupos.data?.length === 0 && (
                  <tr><td colSpan={8}><Vazio titulo="Nenhum boleto" descricao="Ajuste os filtros ou envie novos PDFs." /></td></tr>
                )}
                {(grupos.data || []).map((g) => (
                  <GrupoPagador
                    key={g.pagador_id} grupo={g} filtros={filtrosBase}
                    selecionados={selecionados} alternar={alternar} alternarVarios={alternarVarios}
                    acoes={acoes} editando={editando} setEditando={setEditando} onSalvar={salvarEdicao}
                  />
                ))}
                {!!grupos.data?.length && (
                  <tr className="total">
                    <td />
                    <td>{grupos.data.length} pagador(es)</td>
                    <td className="num">{grupos.data.reduce((s, g) => s + g.qtd, 0)}</td>
                    <td colSpan={4} />
                    <td className="num">{fmtBRL(grupos.data.reduce((s, g) => s + Number(g.total), 0))}</td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : (
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }}>
                    <input type="checkbox" checked={todosMarcados}
                      onChange={() => alternarVarios(idsPagina, !todosMarcados, mapaPagina)}
                      aria-label="Selecionar todos" />
                  </th>
                  <th className="ordenavel" onClick={() => ordenar('pagador')}>Pagador{seta('pagador')}</th>
                  <th className="ordenavel" onClick={() => ordenar('num_documento')}>Nº doc.{seta('num_documento')}</th>
                  <th className="ordenavel" onClick={() => ordenar('vencimento')}>Vencimento{seta('vencimento')}</th>
                  <th className="ordenavel num" onClick={() => ordenar('valor')}>Valor{seta('valor')}</th>
                  <th className="ordenavel" onClick={() => ordenar('situacao')}>Situação{seta('situacao')}</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {lista.isLoading && <LinhasEsqueleto linhas={6} colunas={7} />}
                {lista.data?.items.length === 0 && (
                  <tr><td colSpan={7}><Vazio titulo="Nenhum boleto" descricao="Ajuste os filtros ou envie novos PDFs." /></td></tr>
                )}
                {(lista.data?.items || []).map((b) =>
                  editando === b.id ? (
                    <LinhaEdicao key={b.id} boleto={b} colunas={7} onSalvar={(f) => salvarEdicao(b, f)} onCancelar={() => setEditando(null)} />
                  ) : (
                    <tr key={b.id} className={`${b.qualidade === 'revisao_manual' ? 'revisao' : ''} ${b.deletado_em ? 'deletado' : ''} ${selecionados.has(b.id) ? 'selecionada' : ''}`}>
                      <td>
                        <input type="checkbox" checked={selecionados.has(b.id)} onChange={() => alternar(b)}
                          aria-label={`Selecionar boleto ${b.num_documento || b.id}`} />
                      </td>
                      <td>
                        <div className="principal">{b.pagador_nome}</div>
                        {b.qualidade === 'revisao_manual' && (
                          <div className="divergencia">
                            {(b.divergencias || []).map((d) => ROTULOS_DIVERGENCIA[d] || d).join('; ')}
                          </div>
                        )}
                      </td>
                      <td>{b.num_documento || `#${b.id}`}</td>
                      <td>{fmtData(b.vencimento)}</td>
                      <td className="num principal">{fmtBRL(b.valor)}</td>
                      <td><Situacao b={b} /></td>
                      <td>{acoes(b)}</td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          )}
        </div>

        {modo === 'lista' && lista.data && lista.data.pages > 1 && (
          <div className="paginacao">
            <span className="contagem">{lista.data.total} boleto(s)</span>
            <button className="mini" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button>
            <span>{lista.data.page} / {lista.data.pages}</span>
            <button className="mini" disabled={page >= lista.data.pages} onClick={() => setPage(page + 1)}>›</button>
          </div>
        )}
      </div>

      {selecionados.size > 0 && (
        <div className="barra-lote">
          <strong>{selecionados.size} selecionado(s)</strong>
          <div className="acoes" style={{ marginLeft: 'auto' }}>
            <a className="botao" href={`/api/boletos/pdf-lote?ids=${idsSelecionados.join(',')}`}>
              <IconBaixar /> Baixar
            </a>
            {incluirDeletados && (
              <button onClick={() => emLote('/boletos/restaurar-lote', 'boleto(s) restaurados')}>Restaurar</button>
            )}
            <button className="principal-btn" onClick={() => setPagando(selecao)}>Marcar como pagos</button>
            <button className="perigo" onClick={deletarSelecionados}><IconLixeira /> Deletar</button>
            <button onClick={() => setSelecionados(new Map())}>Limpar</button>
          </div>
        </div>
      )}

      {pagando && <ModalPagar alvo={pagando} onFechar={() => setPagando(null)} onConfirmar={confirmarPagamento} />}
      {vendoPdf && <PdfViewer boleto={vendoPdf} onFechar={() => setVendoPdf(null)} />}
      <AuditDrawer boletoId={drawerId} onFechar={() => setDrawerId(null)} />
    </div>
  )
}
