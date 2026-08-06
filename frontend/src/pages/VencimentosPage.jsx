import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend, qs } from '../api'
import PdfViewer from '../components/PdfViewer'
import { fmtBRL, fmtCpfCnpj, fmtData } from '../format'
import { IconBaixar, IconLixeira, IconOlho } from '../icons'
import { LinhasEsqueleto, Modal, useToast, Vazio } from '../ui'

const hojeISO = () => new Date().toISOString().slice(0, 10)

function limitesDoMes(deslocamento = 0) {
  const hoje = new Date()
  const inicio = new Date(hoje.getFullYear(), hoje.getMonth() + deslocamento, 1)
  const fim = new Date(hoje.getFullYear(), hoje.getMonth() + deslocamento + 1, 0)
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const rotulo = inicio.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })
  return { de: iso(inicio), ate: iso(fim), rotulo: rotulo.charAt(0).toUpperCase() + rotulo.slice(1) }
}

const PRESETS = [
  { id: 'mes', rotulo: 'Este mês' },
  { id: 'proximo', rotulo: 'Próximo mês' },
  { id: '7', rotulo: '7 dias' },
  { id: '15', rotulo: '15 dias' },
  { id: '30', rotulo: '30 dias' },
  { id: '60', rotulo: '60 dias' },
]

function diasAte(iso) {
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0)
  return Math.round((new Date(iso + 'T00:00:00') - hoje) / 86400000)
}

function rotuloPrazo(dias) {
  if (dias < 0) return { texto: `${Math.abs(dias)}d atrasado`, classe: 'urgente' }
  if (dias === 0) return { texto: 'vence hoje', classe: 'urgente' }
  if (dias === 1) return { texto: 'amanhã', classe: 'urgente' }
  return { texto: `em ${dias} dias`, classe: dias <= 7 ? 'urgente' : '' }
}

function ModalPagarLote({ boletos, onConfirmar, onFechar }) {
  const [data, setData] = useState(hojeISO())
  const total = boletos.reduce((s, b) => s + Number(b.valor), 0)
  return (
    <Modal titulo={`Baixar ${boletos.length} boleto(s)`} onFechar={onFechar}>
      <div style={{ color: 'var(--tinta-3)', fontSize: 13, marginBottom: 16 }}>
        Total: <strong style={{ color: 'var(--tinta)' }}>{fmtBRL(total)}</strong>
        <div style={{ marginTop: 4 }}>Cada boleto é baixado pelo próprio valor.</div>
      </div>
      <label className="campo" style={{ marginBottom: 18 }}>
        <span>Data do pagamento</span>
        <input type="date" value={data} onChange={(e) => setData(e.target.value)} />
      </label>
      <div className="acoes">
        <button className="principal-btn" onClick={() => onConfirmar(data)}>Confirmar</button>
        <button onClick={onFechar}>Cancelar</button>
      </div>
    </Modal>
  )
}

export default function VencimentosPage() {
  const [preset, setPreset] = useState('mes')
  const [incluirVencidos, setIncluirVencidos] = useState(true)
  const [selecionados, setSelecionados] = useState(new Map())
  const [vendoPdf, setVendoPdf] = useState(null)
  const [pagandoLote, setPagandoLote] = useState(false)
  const queryClient = useQueryClient()
  const notificar = useToast()

  const periodo = useMemo(() => {
    if (preset === 'mes') return limitesDoMes(0)
    if (preset === 'proximo') return limitesDoMes(1)
    return { dias: Number(preset), rotulo: `próximos ${preset} dias` }
  }, [preset])

  const params = {
    ...(periodo.de ? { de: periodo.de, ate: periodo.ate } : { dias: periodo.dias }),
    incluir_vencidos: incluirVencidos,
  }

  const { data, isLoading } = useQuery({
    queryKey: ['vencimentos', params],
    queryFn: () => apiGet('/dashboard/alertas', params),
  })

  const mut = useMutation({
    mutationFn: (corpo) => apiSend('POST', '/boletos/pagar-lote', corpo),
    onSuccess: (r) => {
      queryClient.invalidateQueries()
      setSelecionados(new Map())
      notificar(`${r.pagos} boleto(s) baixados`)
    },
    onError: (e) => notificar(e.message || 'Erro ao baixar', 'erro'),
  })

  const boletos = data || []
  const total = boletos.reduce((s, b) => s + Number(b.valor), 0)
  const atrasados = boletos.filter((b) => b.vencido)
  const totalAtrasado = atrasados.reduce((s, b) => s + Number(b.valor), 0)

  // Agrupa por dia de vencimento: fica claro o que cai em cada data
  const porDia = useMemo(() => {
    const mapa = new Map()
    for (const b of boletos) {
      if (!mapa.has(b.vencimento)) mapa.set(b.vencimento, [])
      mapa.get(b.vencimento).push(b)
    }
    return [...mapa.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [boletos])

  const deletarSelecionados = () => {
    const ids = [...selecionados.keys()]
    if (!confirm(`Deletar ${ids.length} boleto(s)? Podem ser restaurados depois.`)) return
    apiSend('POST', '/boletos/deletar-lote', { ids })
      .then((r) => {
        queryClient.invalidateQueries()
        setSelecionados(new Map())
        notificar(`${r.afetados} boleto(s) deletados`)
      })
      .catch((e) => notificar(e.message || 'Erro', 'erro'))
  }

  const alternar = (b) =>
    setSelecionados((m) => {
      const novo = new Map(m)
      novo.has(b.id) ? novo.delete(b.id) : novo.set(b.id, b)
      return novo
    })

  const alternarDia = (lista) =>
    setSelecionados((m) => {
      const novo = new Map(m)
      const todosMarcados = lista.every((b) => novo.has(b.id))
      lista.forEach((b) => (todosMarcados ? novo.delete(b.id) : novo.set(b.id, b)))
      return novo
    })

  const idsSelecionados = [...selecionados.keys()]
  const urlLote = (ids) => `/api/boletos/pdf-lote${qs({ ids: ids.join(',') })}`

  return (
    <div>
      <div className="topo">
        <div>
          <h2>Vencimentos</h2>
          <div className="sub">Boletos em aberto, agrupados por dia.</div>
        </div>
        <div className="acoes">
          {boletos.length > 0 && (
            <a className="botao" href={urlLote(boletos.map((b) => b.id))}>
              <IconBaixar /> Baixar todos ({boletos.length})
            </a>
          )}
        </div>
      </div>

      <div className="barra-filtros">
        <div className="segmentado">
          {PRESETS.map((p) => (
            <button key={p.id} className={preset === p.id ? 'ativo' : ''} onClick={() => setPreset(p.id)}>
              {p.rotulo}
            </button>
          ))}
        </div>
        <label className="marcador" style={{ marginLeft: 8 }}>
          <input type="checkbox" checked={incluirVencidos} onChange={(e) => setIncluirVencidos(e.target.checked)} />
          Incluir atrasados
        </label>
        <div style={{ marginLeft: 'auto', fontSize: 12.5, color: 'var(--tinta-3)' }}>
          {periodo.rotulo}
        </div>
      </div>

      <div className="cartoes">
        <div className="cartao azul">
          <div className="rotulo">A receber no período</div>
          <div className="numero">{fmtBRL(total)}</div>
          <div className="apoio">{boletos.length} boleto(s)</div>
        </div>
        <div className="cartao vermelho">
          <div className="rotulo">Em atraso</div>
          <div className="numero">{fmtBRL(totalAtrasado)}</div>
          <div className="apoio">{atrasados.length} boleto(s)</div>
        </div>
        <div className="cartao">
          <div className="rotulo">Pessoas</div>
          <div className="numero">{new Set(boletos.map((b) => b.pagador_id)).size}</div>
          <div className="apoio">com boletos no período</div>
        </div>
      </div>

      <div className="painel sem-padding">
        {isLoading ? (
          <table><tbody><LinhasEsqueleto linhas={6} colunas={6} /></tbody></table>
        ) : boletos.length === 0 ? (
          <Vazio titulo="Nenhum boleto a vencer" descricao={`Nada em aberto ${periodo.rotulo}.`} />
        ) : (
          porDia.map(([dia, lista]) => {
            const prazo = rotuloPrazo(diasAte(dia))
            const somaDia = lista.reduce((s, b) => s + Number(b.valor), 0)
            const todosMarcados = lista.every((b) => selecionados.has(b.id))
            return (
              <div key={dia} className="bloco-dia">
                <div className="bloco-dia-topo">
                  <label className="marcador">
                    <input type="checkbox" checked={todosMarcados} onChange={() => alternarDia(lista)} />
                  </label>
                  <strong>{fmtData(dia)}</strong>
                  <span className={`dias ${prazo.classe}`}>{prazo.texto}</span>
                  <span style={{ marginLeft: 'auto', color: 'var(--tinta-3)', fontSize: 12.5 }}>
                    {lista.length} boleto(s)
                  </span>
                  <strong style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtBRL(somaDia)}</strong>
                  <a className="botao mini" href={urlLote(lista.map((b) => b.id))} title="Baixar os boletos deste dia">
                    <IconBaixar />
                  </a>
                </div>
                <table>
                  <tbody>
                    {lista.map((b) => (
                      <tr key={b.id} className={selecionados.has(b.id) ? 'selecionada' : ''}>
                        <td style={{ width: 34 }}>
                          <input type="checkbox" checked={selecionados.has(b.id)} onChange={() => alternar(b)}
                            aria-label={`Selecionar boleto de ${b.pagador_nome}`} />
                        </td>
                        <td>
                          <div className="principal">{b.pagador_nome}</div>
                          <div className="apoio">{fmtCpfCnpj(b.pagador_cpf_cnpj)}</div>
                        </td>
                        <td>{b.num_documento || `#${b.id}`}</td>
                        <td>
                          {b.vencido && <span className="etiqueta vencido">Atrasado</span>}
                        </td>
                        <td className="num principal">{fmtBRL(b.valor)}</td>
                        <td>
                          <div className="acoes">
                            <button className="mini" onClick={() => setVendoPdf(b)}><IconOlho /> Ver</button>
                            <a className="botao mini" href={`/api/boletos/${b.id}/pdf`} download><IconBaixar /> Baixar</a>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          })
        )}
      </div>

      {selecionados.size > 0 && (
        <div className="barra-lote">
          <strong>{selecionados.size} selecionado(s)</strong>
          <span style={{ opacity: .75 }}>
            {fmtBRL([...selecionados.values()].reduce((s, b) => s + Number(b.valor), 0))}
          </span>
          <div className="acoes" style={{ marginLeft: 'auto' }}>
            <a className="botao" href={urlLote(idsSelecionados)}><IconBaixar /> Baixar PDFs</a>
            <button className="principal-btn" onClick={() => setPagandoLote(true)}>Marcar como pagos</button>
            <button className="perigo" onClick={deletarSelecionados}><IconLixeira /> Deletar</button>
            <button onClick={() => setSelecionados(new Map())}>Limpar</button>
          </div>
        </div>
      )}

      {pagandoLote && (
        <ModalPagarLote
          boletos={[...selecionados.values()]}
          onFechar={() => setPagandoLote(false)}
          onConfirmar={(data_pagamento) => {
            mut.mutate({ ids: idsSelecionados, data_pagamento })
            setPagandoLote(false)
          }}
        />
      )}
      {vendoPdf && <PdfViewer boleto={vendoPdf} onFechar={() => setVendoPdf(null)} />}
    </div>
  )
}
