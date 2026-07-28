import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiSend } from '../api'
import { fmtDataHora } from '../format'

export default function UploadsPage() {
  const [incluirDeletados, setIncluirDeletados] = useState(false)
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['uploads', incluirDeletados],
    queryFn: () => apiGet('/uploads', { incluir_deletados: incluirDeletados }),
  })
  const mut = useMutation({
    mutationFn: ({ metodo, path }) => apiSend(metodo, path),
    onSuccess: () => queryClient.invalidateQueries(),
    onError: (e) => alert(e.message),
  })

  return (
    <div>
      <div className="cabecalho-pagina">
        <div>
          <h2>Histórico de uploads</h2>
          <div className="subtitulo">
            Deletar um upload arquiva os boletos dele em cascata; restaurar desfaz. Reenviar o mesmo arquivo com "reprocessar" reaproveita boletos deletados com a extração nova.
          </div>
        </div>
      </div>
      <label className="check" style={{ marginBottom: 10 }}>
        <input type="checkbox" checked={incluirDeletados} onChange={(e) => setIncluirDeletados(e.target.checked)} />
        Incluir deletados
      </label>
      <div className="painel tabela-envolto">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Arquivo</th><th>Enviado em</th><th className="num">Páginas</th>
              <th className="num">Novos</th><th className="num">Atualizados</th><th className="num">Duplicados</th>
              <th className="num">Ignoradas</th><th className="num">Revisão</th>
              <th>Reprocessado de</th><th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={11} className="vazio">Carregando…</td></tr>}
            {data?.length === 0 && <tr><td colSpan={11} className="vazio">Nenhum upload ainda.</td></tr>}
            {(data || []).map((u) => (
              <tr key={u.id} className={u.deletado_em ? 'deletado' : ''}>
                <td>{u.id}</td>
                <td>{u.nome_arquivo}</td>
                <td>{fmtDataHora(u.criado_em)}</td>
                <td className="num">{u.qtd_paginas}</td>
                <td className="num">{u.qtd_boletos_novos}</td>
                <td className="num">{u.qtd_atualizados}</td>
                <td className="num">{u.qtd_duplicados}</td>
                <td className="num">{u.qtd_ignoradas}</td>
                <td className="num">{u.qtd_revisao}</td>
                <td>{u.reprocessado_de_id ? `#${u.reprocessado_de_id}` : '—'}</td>
                <td>
                  {!u.deletado_em ? (
                    <button
                      className="mini perigo"
                      onClick={() => {
                        if (confirm(`Deletar o upload #${u.id} e todos os boletos dele?`))
                          mut.mutate({ metodo: 'DELETE', path: `/uploads/${u.id}` })
                      }}
                    >
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
  )
}
