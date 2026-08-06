import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api'
import { useFiltros } from '../filtros'

/** Barra compacta: o essencial sempre visível, o resto atrás de "Mais filtros". */
export default function FiltrosBar({ children }) {
  const { filtros, setFiltros, limpar, temAtivos } = useFiltros()
  const [expandido, setExpandido] = useState(false)
  const { data: pagadores } = useQuery({ queryKey: ['pagadores'], queryFn: () => apiGet('/pagadores') })

  const mudar = (campo) => (e) => setFiltros((f) => ({ ...f, [campo]: e.target.value }))
  const avancadosAtivos = !!(filtros.valor_min || filtros.valor_max || filtros.qualidade)

  return (
    <div className="barra-filtros">
      <select value={filtros.pagador_id} onChange={mudar('pagador_id')} style={{ maxWidth: 210 }}>
        <option value="">Todos os pagadores</option>
        {(pagadores || []).map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
      </select>

      <select value={filtros.situacao} onChange={mudar('situacao')}>
        <option value="">Todas as situações</option>
        <option value="aberto">Aberto</option>
        <option value="pago">Pago</option>
        <option value="cancelado">Cancelado</option>
      </select>

      <div className="par-datas">
        <input type="date" value={filtros.vencimento_de} onChange={mudar('vencimento_de')} title="Vencimento de" />
        <span>–</span>
        <input type="date" value={filtros.vencimento_ate} onChange={mudar('vencimento_ate')} title="Vencimento até" />
      </div>

      {children}

      <div className="acoes" style={{ marginLeft: 'auto' }}>
        <button className={`mini ${avancadosAtivos ? 'ativo-sutil' : ''}`} onClick={() => setExpandido((x) => !x)}>
          {expandido ? 'Menos' : 'Mais filtros'}{avancadosAtivos ? ' •' : ''}
        </button>
        {temAtivos && <button className="mini fantasma" onClick={limpar}>Limpar</button>}
      </div>

      {expandido && (
        <div className="filtros-extra">
          <label className="campo">
            <span>Valor mín.</span>
            <input type="number" min="0" step="0.01" placeholder="0,00" style={{ width: 108 }}
              value={filtros.valor_min} onChange={mudar('valor_min')} />
          </label>
          <label className="campo">
            <span>Valor máx.</span>
            <input type="number" min="0" step="0.01" placeholder="—" style={{ width: 108 }}
              value={filtros.valor_max} onChange={mudar('valor_max')} />
          </label>
          <label className="campo">
            <span>Qualidade</span>
            <select value={filtros.qualidade} onChange={mudar('qualidade')}>
              <option value="">Todas</option>
              <option value="ok">OK</option>
              <option value="revisao_manual">Revisão manual</option>
            </select>
          </label>
        </div>
      )}
    </div>
  )
}
