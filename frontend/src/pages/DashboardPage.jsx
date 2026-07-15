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
const INK = { fontSize: 12, fill: '#898781' }

function TooltipMoeda({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fcfcfb', border: '1px solid rgba(11,11,11,.1)', borderRadius: 6, padding: '8px 10px', fontSize: 12 }}>
      <div style={{ color: '#52514e', marginBottom: 4 }}>{label ?? payload[0].name}</div>
      {payload.map((p) => (
        <div key={p.dataKey || p.name}>
          <strong>{fmtBRL(p.value)}</strong>
          {p.payload.qtd !== undefined && <span style={{ color: '#898781' }}> · {p.payload.qtd} boleto(s)</span>}
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { ativos } = useFiltros()
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', ativos],
    queryFn: () => apiGet('/dashboard', ativos),
  })
  const { data: alertas } = useQuery({
    queryKey: ['alertas'],
    queryFn: () => apiGet('/dashboard/alertas', { dias: 30 }),
  })

  if (isLoading) return <p>Carregando…</p>
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Dashboard</h2>
        <ExportButtons />
      </div>
      <FiltrosBar />

      <div className="cards">
        <div className="card"><div className="rotulo">Total geral</div><div className="valor">{fmtBRL(data.total_geral)}</div></div>
        <div className="card"><div className="rotulo">Em aberto</div><div className="valor">{fmtBRL(data.total_aberto)}</div></div>
        <div className="card ok"><div className="rotulo">Pago</div><div className="valor">{fmtBRL(data.total_pago)}</div></div>
        <div className="card alerta"><div className="rotulo">Vencido</div><div className="valor">{fmtBRL(data.total_vencido)}</div></div>
        <div className="card"><div className="rotulo">Boletos / Pagadores</div><div className="valor">{data.qtd_boletos} / {data.qtd_pagadores}</div></div>
        <div className="card"><div className="rotulo">Valor médio</div><div className="valor">{fmtBRL(data.valor_medio)}</div></div>
        <div className="card"><div className="rotulo">Revisão manual</div><div className="valor">{data.qtd_revisao_manual}</div></div>
      </div>

      <div className="grade-graficos">
        <div className="painel">
          <div className="grafico-titulo">Total por pagador</div>
          <ResponsiveContainer width="100%" height={Math.max(220, porPagador.length * 34)}>
            <BarChart data={porPagador} layout="vertical" margin={{ left: 8, right: 24 }}>
              <CartesianGrid horizontal={false} stroke="#e1e0d9" />
              <XAxis type="number" tick={INK} tickFormatter={(v) => fmtBRL(v)} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
              <YAxis type="category" dataKey="nome" width={170} tick={{ ...INK, fill: '#52514e' }} axisLine={false} tickLine={false} />
              <Tooltip content={<TooltipMoeda />} cursor={{ fill: 'rgba(42,120,214,0.06)' }} />
              <Bar dataKey="total" fill={COR_SERIE} radius={[0, 4, 4, 0]} barSize={16} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="painel">
          <div className="grafico-titulo">Total por mês de vencimento</div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={porMes} margin={{ left: 8, right: 24, top: 8 }}>
              <CartesianGrid vertical={false} stroke="#e1e0d9" />
              <XAxis dataKey="rotulo" tick={INK} axisLine={{ stroke: '#c3c2b7' }} tickLine={false} />
              <YAxis tick={INK} tickFormatter={(v) => fmtBRL(v)} width={100} axisLine={false} tickLine={false} />
              <Tooltip content={<TooltipMoeda />} />
              <Line type="monotone" dataKey="total" stroke={COR_SERIE} strokeWidth={2} dot={{ r: 4, fill: COR_SERIE }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="painel">
          <div className="grafico-titulo">Por situação</div>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={porSituacao} dataKey="total" nameKey="nome"
                innerRadius={55} outerRadius={90} paddingAngle={2} stroke="#fcfcfb" strokeWidth={2}
                label={({ nome, total }) => `${nome}: ${fmtBRL(total)}`}
              >
                {porSituacao.map((s) => (
                  <Cell key={s.situacao} fill={CORES_SITUACAO[s.situacao] || '#898781'} />
                ))}
              </Pie>
              <Legend formatter={(v) => <span style={{ color: '#52514e', fontSize: 12 }}>{v}</span>} />
              <Tooltip content={<TooltipMoeda />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="painel">
          <div className="grafico-titulo">Alertas — vencendo nos próximos 30 dias</div>
          {!alertas?.length && <div className="vazio">Nenhum boleto vencendo no período.</div>}
          {!!alertas?.length && (
            <table>
              <thead>
                <tr><th>Pagador</th><th>Vencimento</th><th className="num">Valor</th></tr>
              </thead>
              <tbody>
                {alertas.map((b) => (
                  <tr key={b.id}>
                    <td>{b.pagador_nome}</td>
                    <td>{fmtData(b.vencimento)}</td>
                    <td className="num">{fmtBRL(b.valor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <h3>Resumo por pagador × valor unitário</h3>
      <div className="painel scroll-x">
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
