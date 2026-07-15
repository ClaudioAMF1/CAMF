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

  return (
    <div className="filtros">
      <label className="filtro">
        Pagador
        <select value={filtros.pagador_id} onChange={mudar('pagador_id')} style={{ maxWidth: 220 }}>
          <option value="">Todos</option>
          {(pagadores || []).map((p) => (
            <option key={p.id} value={p.id}>{p.nome}</option>
          ))}
        </select>
      </label>
      <label className="filtro">
        Vencimento de
        <input type="date" value={filtros.vencimento_de} onChange={mudar('vencimento_de')} />
      </label>
      <label className="filtro">
        até
        <input type="date" value={filtros.vencimento_ate} onChange={mudar('vencimento_ate')} />
      </label>
      <label className="filtro">
        Valor mín. (R$)
        <input type="number" min="0" step="0.01" placeholder="0,00" style={{ width: 110 }}
          value={filtros.valor_min} onChange={mudar('valor_min')} />
      </label>
      <label className="filtro">
        Valor máx. (R$)
        <input type="number" min="0" step="0.01" placeholder="—" style={{ width: 110 }}
          value={filtros.valor_max} onChange={mudar('valor_max')} />
      </label>
      <label className="filtro">
        Situação
        <select value={filtros.situacao} onChange={mudar('situacao')}>
          <option value="">Todas</option>
          <option value="aberto">Aberto</option>
          <option value="pago">Pago</option>
          <option value="cancelado">Cancelado</option>
        </select>
      </label>
      <label className="filtro">
        Qualidade
        <select value={filtros.qualidade} onChange={mudar('qualidade')}>
          <option value="">Todas</option>
          <option value="ok">OK</option>
          <option value="revisao_manual">Revisão manual</option>
        </select>
      </label>
      {temAtivos && <button className="fantasma" onClick={limpar}>✕ Limpar</button>}
    </div>
  )
}
