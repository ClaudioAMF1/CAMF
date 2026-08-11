import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api'
import { fmtDataHora } from '../format'
import { Modal, Vazio } from '../ui'

const ROTULOS_ACAO = {
  criar: 'Criação',
  editar: 'Edição',
  deletar: 'Exclusão',
  restaurar: 'Restauração',
  marcar_pago: 'Pagamento registrado',
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
    <Modal titulo={`Histórico do boleto #${boletoId}`} onFechar={onFechar} largura={470}>
      {isLoading && (
        <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
          {Array.from({ length: 4 }, (_, i) => <div className="esqueleto" key={i} style={{ height: 34 }} />)}
        </div>
      )}
      {data?.length === 0 && <Vazio titulo="Sem registros" descricao="Nenhuma alteração neste boleto." />}
      {(data || []).map((r) => (
        <div className="trilha" key={r.id}>
          <div className="quando">{fmtDataHora(r.criado_em)} · {r.autor} · {r.origem}</div>
          <div style={{ fontSize: 13.5, marginTop: 2 }}>
            <strong>{ROTULOS_ACAO[r.acao] || r.acao}</strong>
            {r.campo && <span style={{ color: 'var(--t-3)' }}> — {r.campo}</span>}
          </div>
          {(r.valor_anterior != null || r.valor_novo != null) && (
            <div style={{ fontSize: 12.5, color: 'var(--t-2)', marginTop: 4 }}>
              {r.valor_anterior != null && <>de <code>{r.valor_anterior}</code> </>}
              {r.valor_novo != null && <>para <code>{r.valor_novo}</code></>}
            </div>
          )}
        </div>
      ))}
    </Modal>
  )
}
