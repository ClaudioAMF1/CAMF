import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api'
import { useFiltros } from '../filtros'

export default function FiltrosBar() {
  const { filtros, setFiltros } = useFiltros()
  const { data: pagadores } = useQuery({
    queryKey: ['pagadores'],
    queryFn: () => apiGet('/pagadores'),
  })

  const mudar = (campo) => (e) => setFiltros((f) => ({ ...f, [campo]: e.target.value }))
  const limpar = () =>
    setFiltros({ pagador_id: '', situacao: '', qualidade: '', vencimento_de: '', vencimento_ate: '' })

  return (
    <div className="filtros">
      <label className="filtro">
        Pagador
        <select value={filtros.pagador_id} onChange={mudar('pagador_id')}>
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
        Vencimento até
        <input type="date" value={filtros.vencimento_ate} onChange={mudar('vencimento_ate')} />
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
      <button onClick={limpar}>Limpar filtros</button>
    </div>
  )
}
