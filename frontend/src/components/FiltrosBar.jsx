import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api'
import { useFiltros } from '../filtros'

export default function FiltrosBar() {
  const { filtros, setFiltros, limpar, temAtivos } = useFiltros()
  const { data: pagadores } = useQuery({
    queryKey: ['pagadores'],
    queryFn: () => apiGet('/pagadores'),
  })

  const mudar = (campo) => (e) => setFiltros((f) => ({ ...f, [campo]: e.target.value }))

  const periodo = (meses) => {
    const de = new Date()
    const ate = new Date()
    ate.setMonth(ate.getMonth() + meses)
    setFiltros((f) => ({
      ...f,
      vencimento_de: de.toISOString().slice(0, 10),
      vencimento_ate: ate.toISOString().slice(0, 10),
    }))
  }

  return (
    <div className="barra-filtros">
      <label className="campo">
        <span>Pagador</span>
        <select value={filtros.pagador_id} onChange={mudar('pagador_id')} style={{ maxWidth: 210 }}>
          <option value="">Todos</option>
          {(pagadores || []).map((p) => (
            <option key={p.id} value={p.id}>{p.nome}</option>
          ))}
        </select>
      </label>
      <label className="campo">
        <span>Vencimento de</span>
        <input type="date" value={filtros.vencimento_de} onChange={mudar('vencimento_de')} />
      </label>
      <label className="campo">
        <span>até</span>
        <input type="date" value={filtros.vencimento_ate} onChange={mudar('vencimento_ate')} />
      </label>
      <label className="campo">
        <span>Valor mín.</span>
        <input type="number" min="0" step="0.01" placeholder="0,00" style={{ width: 104 }}
          value={filtros.valor_min} onChange={mudar('valor_min')} />
      </label>
      <label className="campo">
        <span>Valor máx.</span>
        <input type="number" min="0" step="0.01" placeholder="—" style={{ width: 104 }}
          value={filtros.valor_max} onChange={mudar('valor_max')} />
      </label>
      <label className="campo">
        <span>Situação</span>
        <select value={filtros.situacao} onChange={mudar('situacao')}>
          <option value="">Todas</option>
          <option value="aberto">Aberto</option>
          <option value="pago">Pago</option>
          <option value="cancelado">Cancelado</option>
        </select>
      </label>
      <label className="campo">
        <span>Qualidade</span>
        <select value={filtros.qualidade} onChange={mudar('qualidade')}>
          <option value="">Todas</option>
          <option value="ok">OK</option>
          <option value="revisao_manual">Revisão manual</option>
        </select>
      </label>
      <div className="acoes" style={{ marginLeft: 'auto' }}>
        <button className="mini fantasma" onClick={() => periodo(1)}>Próximos 30 dias</button>
        <button className="mini fantasma" onClick={() => periodo(3)}>3 meses</button>
        {temAtivos && <button className="mini" onClick={limpar}>✕ Limpar</button>}
      </div>
    </div>
  )
}
