import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { uploadArquivos } from '../api'

function ResultadoArquivo({ r }) {
  const classe = r.erro ? (r.erro === 'arquivo_ja_processado' ? 'duplicado' : 'erro') : ''
  return (
    <div className={`resultado-arquivo ${classe}`}>
      <div className="nome">{r.nome}</div>
      <div className="detalhes">
        {r.erro === 'arquivo_ja_processado' && <span>Arquivo já processado (upload #{r.upload_id}). </span>}
        {r.erro && r.erro !== 'arquivo_ja_processado' && <span className="erro-msg">Erro: {r.erro}</span>}
        {!r.erro && (
          <>
            <strong>{r.novos}</strong> novo(s) · <strong>{r.duplicados}</strong> duplicado(s) ignorado(s) ·{' '}
            <strong>{r.revisao_manual}</strong> p/ revisão manual
            {r.ignoradas?.length > 0 && (
              <> · páginas ignoradas: {r.ignoradas.join(', ')}</>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function UploadPage() {
  const [arrastando, setArrastando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [resultados, setResultados] = useState(null)
  const [conflito409, setConflito409] = useState(null)
  const inputRef = useRef()
  const queryClient = useQueryClient()

  async function enviar(files, forcar = false) {
    if (!files?.length) return
    setEnviando(true)
    setConflito409(null)
    try {
      const resposta = await uploadArquivos(files, forcar)
      setResultados(resposta.arquivos)
      queryClient.invalidateQueries()
    } catch (erro) {
      if (erro.status === 409) {
        setConflito409({ detalhe: erro.detail, files })
        setResultados(null)
      } else {
        setResultados([{ nome: 'Falha no envio', erro: String(erro.message || erro) }])
      }
    } finally {
      setEnviando(false)
    }
  }

  const aoSoltar = (e) => {
    e.preventDefault()
    setArrastando(false)
    enviar([...e.dataTransfer.files].filter((f) => f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf'))
  }

  return (
    <div>
      <h2>Upload de boletos (PDF)</h2>
      <div
        className={`dropzone ${arrastando ? 'ativo' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setArrastando(true) }}
        onDragLeave={() => setArrastando(false)}
        onDrop={aoSoltar}
        onClick={() => inputRef.current?.click()}
      >
        {enviando ? 'Processando…' : 'Arraste PDFs de boletos Sicoob aqui, ou clique para selecionar (múltiplos arquivos)'}
        <input
          ref={inputRef} type="file" accept="application/pdf" multiple hidden
          onChange={(e) => { enviar([...e.target.files]); e.target.value = '' }}
        />
      </div>

      {conflito409 && (
        <div className="aviso-409">
          <strong>Arquivo(s) já processado(s).</strong>
          <div style={{ fontSize: 12, margin: '6px 0' }}>
            {(conflito409.detalhe?.uploads_originais || []).map((u) => (
              <div key={u.upload.id}>
                {u.nome} → upload #{u.upload.id} de {new Date(u.upload.criado_em).toLocaleString('pt-BR')}{' '}
                ({u.upload.qtd_boletos_novos} boletos, {u.upload.qtd_ignoradas} páginas ignoradas)
              </div>
            ))}
          </div>
          <button className="primario" onClick={() => enviar(conflito409.files, true)}>
            Reprocessar mesmo assim
          </button>
        </div>
      )}

      {resultados && (
        <div style={{ marginTop: 16 }}>
          <h3>Resultado</h3>
          {resultados.map((r, i) => <ResultadoArquivo key={i} r={r} />)}
        </div>
      )}
    </div>
  )
}
