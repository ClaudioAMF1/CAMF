import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api'
import { fmtDataHora } from '../format'

const ROTULOS_ACAO = {
  criar: 'Criação',
  editar: 'Edição',
  deletar: 'Exclusão',
  restaurar: 'Restauração',
  marcar_pago: 'Marcado como pago',
  divergencia_nome: 'Divergência de nome',
}

export default function AuditDrawer({ boletoId, onFechar }) {
  const { data, isLoading } = useQuery({
    queryKey: ['auditoria', boletoId],
    queryFn: () => apiGet(`/boletos/${boletoId}/auditoria`),
    enabled: boletoId != null,
  })

  if (boletoId == null) return null
  return (
    <>
      <div className="drawer-fundo" onClick={onFechar} />
      <div className="drawer">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3>Histórico do boleto #{boletoId}</h3>
          <button className="mini" onClick={onFechar}>Fechar</button>
        </div>
        {isLoading && <p>Carregando…</p>}
        {data?.length === 0 && <div className="vazio">Sem registros.</div>}
        {(data || []).map((r) => (
          <div className="trilha-item" key={r.id}>
            <div className="quando">
              {fmtDataHora(r.criado_em)} · {r.autor} · origem: {r.origem}
            </div>
            <div className="oque">
              <strong>{ROTULOS_ACAO[r.acao] || r.acao}</strong>
              {r.campo && <> — {r.campo}</>}
              {(r.valor_anterior != null || r.valor_novo != null) && (
                <div style={{ fontSize: 12, color: '#52514e' }}>
                  {r.valor_anterior != null && <>de <code>{r.valor_anterior}</code> </>}
                  {r.valor_novo != null && <>para <code>{r.valor_novo}</code></>}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
