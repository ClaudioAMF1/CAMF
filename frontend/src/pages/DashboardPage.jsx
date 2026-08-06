import { useState } from 'react'
import { Link } from 'react-router-dom'
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
import { useTema, Vazio } from '../ui'

// Paleta validada para daltonismo (skill dataviz): azul p/ série única;
// situação com cor fixa por entidade, nunca por posição.
const CORES = {
  claro: { serie: '#2a78d6', aberto: '#2a78d6', pago: '#008300', cancelado: '#898781', grade: '#e9edf3', eixo: '#94a3b8', superficie: '#ffffff', tinta: '#475569' },
  escuro: { serie: '#3987e5', aberto: '#3987e5', pago: '#4ec44e', cancelado: '#7c8b9d', grade: '#232c39', eixo: '#6b7a8d', superficie: '#141a23', tinta: '#c2ccd9' },
}

const compacto = new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1,
})

function diasAte(iso) {
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0)
  return Math.round((new Date(iso + 'T00:00:00') - hoje) / 86400000)
}

function Dica({ active, payload, label, c }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: c.superficie, border: `1px solid ${c.grade}`, borderRadius: 10,
      padding: '9px 13px', fontSize: 12.5, boxShadow: '0 8px 24px rgba(0,0,0,.12)', color: c.tinta,
    }}>
      <div style={{ marginBottom: 3 }}>{label ?? payload[0].name}</div>
      {payload.map((p) => (
        <div key={p.dataKey || p.name} style={{ fontWeight: 600 }}>
          {fmtBRL(p.value)}
          {p.payload.qtd !== undefined && <span style={{ fontWeight: 400, opacity: .7 }}> · {p.payload.qtd} boleto(s)</span>}
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { ativos } = useFiltros()
  const { tema } = useTema()
  const c = CORES[tema === 'escuro' ? 'escuro' : 'claro']
  const [dias, setDias] = useState(30)

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', ativos],
    queryFn: () => apiGet('/dashboard', ativos),
  })
  const { data: alertas } = useQuery({
    queryKey: ['alertas', dias],
    queryFn: () => apiGet('/dashboard/alertas', { dias }),
  })

  if (isLoading) {
    return (
      <div>
        <div className="topo"><div><h2>Dashboard</h2></div></div>
        <div className="cartoes">
          {Array.from({ length: 6 }, (_, i) => (
            <div className="cartao" key={i}>
              <div className="esqueleto" style={{ width: '55%' }} />
              <div className="esqueleto" style={{ width: '78%', height: 22, marginTop: 10 }} />
            </div>
          ))}
        </div>
        <div className="grade-2">
          <div className="painel"><div className="esqueleto" style={{ height: 240 }} /></div>
          <div className="painel"><div className="esqueleto" style={{ height: 240 }} /></div>
        </div>
      </div>
    )
  }
  if (!data) return null

  const porPagador = Object.values(
    data.por_pagador.reduce((acc, g) => {
      acc[g.nome] = acc[g.nome] || { nome: g.nome, total: 0, qtd: 0 }
      acc[g.nome].total += Number(g.subtotal)
      acc[g.nome].qtd += g.qtd
      return acc
    }, {})
  ).sort((a, b) => b.total - a.total).slice(0, 12)

  const porMes = data.por_mes.map((m) => ({ ...m, total: Number(m.total), rotulo: fmtMes(m.mes) }))
  const porSituacao = data.por_situacao.map((s) => ({
    ...s, total: Number(s.total), nome: ROTULOS_SITUACAO[s.situacao] || s.situacao,
  }))
  const semDados = data.qtd_boletos === 0

  return (
    <div>
      <div className="topo">
        <div>
          <h2>Dashboard</h2>
          <div className="sub">Os filtros abaixo valem para os gráficos, as tabelas e as exportações.</div>
        </div>
        <ExportButtons />
      </div>

      <FiltrosBar />

      <div className="cartoes">
        <div className="cartao azul">
          <div className="rotulo">Total geral</div>
          <div className="numero">{fmtBRL(data.total_geral)}</div>
          <div className="apoio">{data.qtd_boletos} boletos · {data.qtd_pagadores} pagadores</div>
        </div>
        <div className="cartao azul">
          <div className="rotulo">Em aberto</div>
          <div className="numero">{fmtBRL(data.total_aberto)}</div>
        </div>
        <div className="cartao verde">
          <div className="rotulo">Recebido</div>
          <div className="numero">{fmtBRL(data.total_pago)}</div>
        </div>
        <div className="cartao vermelho">
          <div className="rotulo">Vencido</div>
          <div className="numero">{fmtBRL(data.total_vencido)}</div>
        </div>
        <div className="cartao">
          <div className="rotulo">Valor médio</div>
          <div className="numero">{fmtBRL(data.valor_medio)}</div>
        </div>
        <div className="cartao ambar">
          <div className="rotulo">Revisão manual</div>
          <div className="numero">{data.qtd_revisao_manual}</div>
          <div className="apoio">boletos p/ conferir</div>
        </div>
      </div>

      {semDados ? (
        <div className="painel">
          <Vazio
            titulo="Nenhum boleto no filtro atual"
            descricao="Envie PDFs de boletos Sicoob ou ajuste os filtros para ver os números aqui."
          />
        </div>
      ) : (
        <div className="grade-2">
          <div className="painel">
            <div className="painel-titulo">Total por pagador</div>
            <div className="painel-sub">Maiores saldos no filtro atual</div>
            <ResponsiveContainer width="100%" height={Math.min(460, Math.max(272, porPagador.length * 38))}>
              <BarChart data={porPagador} layout="vertical" margin={{ left: 4, right: 26 }}>
                <CartesianGrid horizontal={false} stroke={c.grade} />
                <XAxis type="number" tick={{ fontSize: 11.5, fill: c.eixo }} tickFormatter={(v) => compacto.format(v)} axisLine={{ stroke: c.grade }} tickLine={false} />
                <YAxis type="category" dataKey="nome" width={158} tick={{ fontSize: 11.5, fill: c.tinta }} axisLine={false} tickLine={false} />
                <Tooltip content={<Dica c={c} />} cursor={{ fill: 'rgba(42,120,214,.07)' }} />
                <Bar dataKey="total" fill={c.serie} radius={[0, 4, 4, 0]} barSize={15} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="painel">
            <div className="painel-titulo">Recebimentos por mês</div>
            <div className="painel-sub">Total por mês de vencimento</div>
            <ResponsiveContainer width="100%" height={272}>
              <LineChart data={porMes} margin={{ left: 4, right: 26, top: 6 }}>
                <CartesianGrid vertical={false} stroke={c.grade} />
                <XAxis dataKey="rotulo" tick={{ fontSize: 11.5, fill: c.eixo }} axisLine={{ stroke: c.grade }} tickLine={false} />
                <YAxis tick={{ fontSize: 11.5, fill: c.eixo }} tickFormatter={(v) => compacto.format(v)} width={68} axisLine={false} tickLine={false} />
                <Tooltip content={<Dica c={c} />} />
                <Line type="monotone" dataKey="total" stroke={c.serie} strokeWidth={2}
                  dot={{ r: 3.5, fill: c.serie, strokeWidth: 0 }} activeDot={{ r: 6, strokeWidth: 2, stroke: c.superficie }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="painel">
            <div className="painel-titulo">Por situação</div>
            <div className="painel-sub">Distribuição do valor total</div>
            <ResponsiveContainer width="100%" height={272}>
              <PieChart>
                <Pie data={porSituacao} dataKey="total" nameKey="nome"
                  innerRadius={60} outerRadius={94} paddingAngle={2}
                  stroke={c.superficie} strokeWidth={2}
                  label={({ nome, total }) => `${nome}: ${compacto.format(total)}`}
                  labelLine={{ stroke: c.grade }}>
                  {porSituacao.map((s) => <Cell key={s.situacao} fill={c[s.situacao] || c.cancelado} />)}
                </Pie>
                <Legend formatter={(v) => <span style={{ color: c.tinta, fontSize: 12 }}>{v}</span>} />
                <Tooltip content={<Dica c={c} />} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="painel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
              <div>
                <div className="painel-titulo">Vencimentos próximos</div>
                <div className="painel-sub">Boletos em aberto a vencer</div>
              </div>
              <div className="segmentado">
                {[7, 15, 30, 60].map((d) => (
                  <button key={d} className={dias === d ? 'ativo' : ''} onClick={() => setDias(d)}>{d}d</button>
                ))}
              </div>
            </div>
            {!alertas?.length ? (
              <Vazio titulo="Nada a vencer" descricao={`Nenhum boleto em aberto nos próximos ${dias} dias.`} />
            ) : (
              <>
                <div style={{ maxHeight: 232, overflowY: 'auto', marginTop: 12, borderTop: '1px solid var(--linha)', borderBottom: '1px solid var(--linha)' }}>
                  <table>
                    <thead><tr><th>Pagador</th><th>Vencimento</th><th className="num">Valor</th></tr></thead>
                    <tbody>
                      {alertas.map((b) => {
                        const d = diasAte(b.vencimento)
                        return (
                          <tr key={b.id}>
                            <td>
                              <div className="principal">{b.pagador_nome}</div>
                              {b.pagador_cpf_cnpj && <div className="apoio">{b.pagador_cpf_cnpj}</div>}
                            </td>
                            <td>
                              {fmtData(b.vencimento)}{' '}
                              <span className={`dias ${d <= 7 ? 'urgente' : ''}`}>
                                {d === 0 ? 'hoje' : `${d}d`}
                              </span>
                            </td>
                            <td className="num">{fmtBRL(b.valor)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <div style={{ paddingTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                  <strong style={{ fontVariantNumeric: 'tabular-nums' }}>
                    {fmtBRL(alertas.reduce((s, b) => s + Number(b.valor), 0))}
                  </strong>
                  <Link className="botao" to="/vencimentos">Ver todos e baixar PDFs →</Link>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {!semDados && (
        <>
          <h3>Resumo por pagador × valor unitário</h3>
          <div className="painel sem-padding">
            <div className="rolagem">
              <table>
                <thead>
                  <tr><th>Pagador</th><th className="num">Qtd</th><th className="num">Valor unitário</th><th className="num">Subtotal</th></tr>
                </thead>
                <tbody>
                  {data.por_pagador.map((g, i) => (
                    <tr key={i}>
                      <td className="principal">{g.nome}</td>
                      <td className="num">{g.qtd}</td>
                      <td className="num">{fmtBRL(g.valor_unitario)}</td>
                      <td className="num">{fmtBRL(g.subtotal)}</td>
                    </tr>
                  ))}
                  <tr className="total">
                    <td>TOTAL GERAL</td>
                    <td className="num">{data.qtd_boletos}</td>
                    <td />
                    <td className="num">{fmtBRL(data.total_geral)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
