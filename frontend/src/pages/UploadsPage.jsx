import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend } from '../api'
import { fmtDataHora } from '../format'
import { LinhasEsqueleto, useToast, Vazio } from '../ui'

export default function UploadsPage() {
  const [incluirDeletados, setIncluirDeletados] = useState(false)
  const queryClient = useQueryClient()
  const notificar = useToast()

  const { data, isLoading } = useQuery({
    queryKey: ['uploads', incluirDeletados],
    queryFn: () => apiGet('/uploads', { incluir_deletados: incluirDeletados }),
  })
  const mut = useMutation({
    mutationFn: ({ metodo, path }) => apiSend(metodo, path),
    onSuccess: () => queryClient.invalidateQueries(),
    onError: (e) => notificar(e.message, 'erro'),
  })

  return (
    <div>
      <div className="topo">
        <div>
          <h2>Histórico de uploads</h2>
          <div className="sub">
            Deletar um upload arquiva os boletos dele em cascata; restaurar desfaz.
            Reenviar o mesmo arquivo com “reprocessar” re-extrai e atualiza os boletos.
          </div>
        </div>
        <label className="marcador">
          <input type="checkbox" checked={incluirDeletados} onChange={(e) => setIncluirDeletados(e.target.checked)} />
          Incluir deletados
        </label>
      </div>

      <div className="painel sem-padding">
        <div className="rolagem">
          <table>
            <thead>
              <tr>
                <th>#</th><th>Arquivo</th><th>Enviado em</th>
                <th className="num">Páginas</th><th className="num">Novos</th>
                <th className="num">Atualizados</th><th className="num">Duplicados</th>
                <th className="num">Ignoradas</th><th className="num">Revisão</th>
                <th>Reproc. de</th><th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && <LinhasEsqueleto linhas={4} colunas={11} />}
              {data?.length === 0 && (
                <tr><td colSpan={11}>
                  <Vazio titulo="Nenhum upload ainda" descricao="Os arquivos enviados aparecem aqui, com o resumo de cada importação." />
                </td></tr>
              )}
              {(data || []).map((u) => (
                <tr key={u.id} className={u.deletado_em ? 'deletado' : ''}>
                  <td style={{ color: 'var(--tinta-fraca)' }}>{u.id}</td>
                  <td className="principal">
                    <a href={`/api/uploads/${u.id}/pdf`} target="_blank" rel="noreferrer"
                       title="Abrir o PDF original" style={{ color: 'var(--azul)', textDecoration: 'none' }}>
                      {u.nome_arquivo}
                    </a>
                  </td>
                  <td>{fmtDataHora(u.criado_em)}</td>
                  <td className="num">{u.qtd_paginas}</td>
                  <td className="num">{u.qtd_boletos_novos || '—'}</td>
                  <td className="num">{u.qtd_atualizados || '—'}</td>
                  <td className="num">{u.qtd_duplicados || '—'}</td>
                  <td className="num">{u.qtd_ignoradas || '—'}</td>
                  <td className="num">
                    {u.qtd_revisao ? <span className="etiqueta revisao">{u.qtd_revisao}</span> : '—'}
                  </td>
                  <td>{u.reprocessado_de_id ? `#${u.reprocessado_de_id}` : '—'}</td>
                  <td>
                    {!u.deletado_em ? (
                      <button className="mini fantasma perigo"
                        onClick={() => confirm(`Deletar o upload #${u.id} e todos os boletos dele?`)
                          && mut.mutate({ metodo: 'DELETE', path: `/uploads/${u.id}` })}>
                        Deletar
                      </button>
                    ) : (
                      <button className="mini" onClick={() => mut.mutate({ metodo: 'POST', path: `/uploads/${u.id}/restaurar` })}>
                        Restaurar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
