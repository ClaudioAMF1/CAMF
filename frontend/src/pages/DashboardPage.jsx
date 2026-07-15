import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { apiGet } from '../api'
import ExportButtons from '../components/ExportButtons'
import FiltrosBar from '../components/FiltrosBar'
import { useFiltros } from '../filtros'
import { fmtBRL, fmtData, fmtMes, ROTULOS_SITUACAO } from '../format'

// Paleta validada (dataviz): azul p/ série única; situação com cores fixas por entidade
const COR_SERIE = '#2a78d6'
const CORES_SITUACAO = { aberto: '#2a78d6', pago: '#008300', cancelado: '#898781' }
const INK = { fontSize: 12, fill: '#8a9099' }

const brlCompacto = new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1,
})

function TooltipMoeda({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fff', border: '1px solid rgba(20,24,30,.1)', borderRadius: 8, padding: '8px 12px', fontSize: 12, boxShadow: '0 4px 14px rgba(0,0,0,.08)' }}>
      <div style={{ color: '#4b5158', marginBottom: 4 }}>{label ?? payload[0].name}</div>
      {payload.map((p) => (
        <div key={p.dataKey || p.name}>
          <strong>{fmtBRL(p.value)}</strong>
          {p.payload.qtd !== undefined && <span style={{ color: '#8a9099' }}> · {p.payload.qtd} boleto(s)</span>}
        </div>
      ))}
    </div>
  )
}

function diasAte(iso) {
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0)
  return Math.round((new Date(iso + 'T00:00:00') - hoje) / 86400000)
}

export default function DashboardPage() {
  const { ativos } = useFiltros()
  const [diasAlerta, setDiasAlerta] = useState(30)
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', ativos],
    queryFn: () => apiGet('/dashboard', ativos),
  })
  const { data: alertas } = useQuery({
    queryKey: ['alertas', diasAlerta],
    queryFn: () => apiGet('/dashboard/alertas', { dias: diasAlerta }),
  })

  if (isLoading) return <div className="vazio">Carregando dashboard…</div>
  if (!data) return null

  // por_pagador vem por (pagador × valor unitário); o gráfico agrega por pagador
  const porPagador = Object.values(
    data.por_pagador.reduce((acc, g) => {
      acc[g.nome] = acc[g.nome] || { nome: g.nome, total: 0, qtd: 0 }
      acc[g.nome].total += Number(g.subtotal)
      acc[g.nome].qtd += g.qtd
      return acc
    }, {})
  ).sort((a, b) => b.total - a.total)

  const porMes = data.por_mes.map((m) => ({ ...m, total: Number(m.total), rotulo: fmtMes(m.mes) }))
  const porSituacao = data.por_situacao.map((s) => ({
    ...s, total: Number(s.total), nome: ROTULOS_SITUACAO[s.situacao] || s.situacao,
  }))

  return (
    <div>
      <div className="cabecalho-pagina">
        <div>
          <h2>Dashboard</h2>
          <div className="subtitulo">Visão geral das contas a receber — os filtros valem para os gráficos, tabelas e exportações.</div>
        </div>
        <ExportButtons />
      </div>
      <FiltrosBar />

      <div className="cards">
        <div className="card azul"><div className="rotulo">Total geral</div><div className="valor">{fmtBRL(data.total_geral)}</div><div className="apoio">{data.qtd_boletos} boletos · {data.qtd_pagadores} pagadores</div></div>
        <div className="card azul"><div className="rotulo">Em aberto</div><div className="valor">{fmtBRL(data.total_aberto)}</div></div>
        <div className="card ok"><div className="rotulo">Pago</div><div className="valor">{fmtBRL(data.total_pago)}</div></div>
        <div className="card alerta"><div className="rotulo">Vencido</div><div className="valor">{fmtBRL(data.total_vencido)}</div></div>
        <div className="card"><div className="rotulo">Valor médio</div><div className="valor">{fmtBRL(data.valor_medio)}</div></div>
        <div className="card atencao"><div className="rotulo">Revisão manual</div><div className="valor">{data.qtd_revisao_manual}</div><div className="apoio">boletos p/ conferir</div></div>
      </div>

      <div className="grade-graficos">
        <div className="painel">
          <div className="grafico-titulo">Total por pagador</div>
          <div className="grafico-subtitulo">Soma dos boletos no filtro atual</div>
          {porPagador.length === 0 ? <div className="vazio">Sem dados no filtro atual.</div> : (
            <ResponsiveContainer width="100%" height={Math.min(520, Math.max(200, porPagador.length * 36))}>
              <BarChart data={porPagador} layout="vertical" margin={{ left: 8, right: 28 }}>
                <CartesianGrid horizontal={false} stroke="#eceef1" />
                <XAxis type="number" tick={INK} tickFormatter={(v) => brlCompacto.format(v)} axisLine={{ stroke: '#d5d9de' }} tickLine={false} />
                <YAxis type="category" dataKey="nome" width={170} tick={{ ...INK, fill: '#4b5158' }} axisLine={false} tickLine={false} />
                <Tooltip content={<TooltipMoeda />} cursor={{ fill: 'rgba(42,120,214,0.06)' }} />
                <Bar dataKey="total" fill={COR_SERIE} radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="painel">
          <div className="grafico-titulo">Total por mês de vencimento</div>
          <div className="grafico-subtitulo">Evolução mensal no filtro atual</div>
          {porMes.length === 0 ? <div className="vazio">Sem dados no filtro atual.</div> : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={porMes} margin={{ left: 8, right: 28, top: 8 }}>
                <CartesianGrid vertical={false} stroke="#eceef1" />
                <XAxis dataKey="rotulo" tick={INK} axisLine={{ stroke: '#d5d9de' }} tickLine={false} />
                <YAxis tick={INK} tickFormatter={(v) => brlCompacto.format(v)} width={72} axisLine={false} tickLine={false} />
                <Tooltip content={<TooltipMoeda />} />
                <Line type="monotone" dataKey="total" stroke={COR_SERIE} strokeWidth={2} dot={{ r: 4, fill: COR_SERIE }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="painel">
          <div className="grafico-titulo">Por situação</div>
          <div className="grafico-subtitulo">Distribuição do valor total</div>
          <ResponsiveContainer width="100%" height={270}>
            <PieChart>
              <Pie
                data={porSituacao} dataKey="total" nameKey="nome"
                innerRadius={58} outerRadius={92} paddingAngle={2} stroke="#ffffff" strokeWidth={2}
                label={({ nome, total }) => `${nome}: ${brlCompacto.format(total)}`}
              >
                {porSituacao.map((s) => (
                  <Cell key={s.situacao} fill={CORES_SITUACAO[s.situacao] || '#898781'} />
                ))}
              </Pie>
              <Legend formatter={(v) => <span style={{ color: '#4b5158', fontSize: 12 }}>{v}</span>} />
              <Tooltip content={<TooltipMoeda />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="painel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <div>
              <div className="grafico-titulo">Vencimentos próximos</div>
              <div className="grafico-subtitulo">Boletos em aberto vencendo em breve</div>
            </div>
            <div className="chips">
              {[7, 15, 30, 60].map((d) => (
                <button key={d} className={`chip ${diasAlerta === d ? 'ativo' : ''}`} onClick={() => setDiasAlerta(d)}>
                  {d} dias
                </button>
              ))}
            </div>
          </div>
          {!alertas?.length && <div className="vazio">Nenhum boleto vencendo nos próximos {diasAlerta} dias.</div>}
          {!!alertas?.length && (
            <div style={{ maxHeight: 220, overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr><th>Pagador</th><th>Vencimento</th><th className="num">Valor</th></tr>
                </thead>
                <tbody>
                  {alertas.map((b) => {
                    const dias = diasAte(b.vencimento)
                    return (
                      <tr key={b.id}>
                        <td className="celula-principal">{b.pagador_nome}</td>
                        <td>
                          {fmtData(b.vencimento)}{' '}
                          <span className={`dias-restantes ${dias <= 7 ? 'urgente' : ''}`}>
                            ({dias === 0 ? 'hoje' : `${dias} dia${dias > 1 ? 's' : ''}`})
                          </span>
                        </td>
                        <td className="num">{fmtBRL(b.valor)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <h3>Resumo por pagador × valor unitário</h3>
      <div className="painel tabela-envolto">
        <table>
          <thead>
            <tr><th>Pagador</th><th className="num">Qtd</th><th className="num">Valor unitário</th><th className="num">Subtotal</th></tr>
          </thead>
          <tbody>
            {data.por_pagador.map((g, i) => (
              <tr key={i}>
                <td>{g.nome}</td>
                <td className="num">{g.qtd}</td>
                <td className="num">{fmtBRL(g.valor_unitario)}</td>
                <td className="num">{fmtBRL(g.subtotal)}</td>
              </tr>
            ))}
            <tr className="total-geral">
              <td>TOTAL GERAL</td>
              <td className="num">{data.qtd_boletos}</td>
              <td></td>
              <td className="num">{fmtBRL(data.total_geral)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
