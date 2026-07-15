import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { uploadArquivos } from '../api'
import { fmtBRL, fmtData, ROTULOS_DIVERGENCIA } from '../format'

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

function CampoDiag({ rotulo, valor }) {
  return (
    <div className="campo">
      <b>{rotulo}</b>
      {valor === null || valor === undefined || valor === '' ? <span style={{ color: '#d03b3b' }}>não extraído</span> : String(valor)}
    </div>
  )
}

function DiagnosticoArquivo({ arquivo }) {
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontWeight: 600 }}>{arquivo.nome}</div>
      {arquivo.erro && <div className="erro-msg">Erro: {arquivo.erro}</div>}
      {arquivo.paginas.map((p) => (
        <div className="pagina-diagnostico" key={p.pagina}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <strong>Página {p.pagina}</strong>
            {p.tem_linha_digitavel
              ? <span className="tag pago">linha digitável OK</span>
              : p.parece_boleto
                ? <span className="tag vencido">parece boleto, linha não reconhecida</span>
                : <span className="tag cancelado">ignorada (não é boleto)</span>}
            {p.divergencias?.length > 0 && (
              <span className="tag revisao">{p.divergencias.map((d) => ROTULOS_DIVERGENCIA[d] || d).join('; ')}</span>
            )}
            {p.divergencias?.length === 0 && p.tem_linha_digitavel && <span className="tag pago">sem divergências</span>}
          </div>
          {p.campos && (
            <div className="grade-campos">
              <CampoDiag rotulo="Pagador" valor={p.campos.pagador_nome} />
              <CampoDiag rotulo="CPF/CNPJ" valor={p.campos.pagador_cpf_cnpj} />
              <CampoDiag rotulo="Valor (texto)" valor={p.campos.valor && fmtBRL(p.campos.valor)} />
              <CampoDiag rotulo="Valor (linha)" valor={p.campos.valor_linha && fmtBRL(p.campos.valor_linha)} />
              <CampoDiag rotulo="Vencimento (texto)" valor={p.campos.vencimento && fmtData(p.campos.vencimento)} />
              <CampoDiag rotulo="Vencimento (linha)" valor={p.campos.vencimento_linha && fmtData(p.campos.vencimento_linha)} />
              <CampoDiag rotulo="Nº documento" valor={p.campos.num_documento} />
              <CampoDiag rotulo="Nosso número" valor={p.campos.nosso_numero} />
              <CampoDiag rotulo="Emissão" valor={p.campos.data_emissao && fmtData(p.campos.data_emissao)} />
              <CampoDiag rotulo="Beneficiário" valor={p.campos.beneficiario_nome} />
              <CampoDiag rotulo="Endereço" valor={p.campos.endereco} />
              <CampoDiag rotulo="Município/UF" valor={[p.campos.municipio, p.campos.uf].filter(Boolean).join(' - ')} />
            </div>
          )}
          <details>
            <summary>Ver texto extraído da página</summary>
            <pre>{p.texto || '(página sem texto)'}</pre>
          </details>
        </div>
      ))}
    </div>
  )
}

export default function UploadPage() {
  const [arrastando, setArrastando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [diagnostico, setDiagnostico] = useState(false)
  const [resultados, setResultados] = useState(null)
  const [resultadoDiag, setResultadoDiag] = useState(null)
  const [conflito409, setConflito409] = useState(null)
  const inputRef = useRef()
  const queryClient = useQueryClient()

  async function analisar(files) {
    const form = new FormData()
    for (const f of files) form.append('arquivos', f)
    const resp = await fetch('/api/uploads/analisar', { method: 'POST', body: form })
    if (!resp.ok) throw new Error('Falha na análise')
    setResultadoDiag((await resp.json()).arquivos)
    setResultados(null)
  }

  async function enviar(files, forcar = false) {
    if (!files?.length) return
    setEnviando(true)
    setConflito409(null)
    try {
      if (diagnostico && !forcar) {
        await analisar(files)
        return
      }
      const resposta = await uploadArquivos(files, forcar)
      setResultados(resposta.arquivos)
      setResultadoDiag(null)
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
      <div className="cabecalho-pagina">
        <div>
          <h2>Enviar boletos (PDF)</h2>
          <div className="subtitulo">
            Cada página com linha digitável vira um boleto; duplicados são ignorados automaticamente.
          </div>
        </div>
        <label className="check" title="Extrai e mostra os campos reconhecidos sem gravar nada — útil para conferir o parser com um PDF novo">
          <input type="checkbox" checked={diagnostico} onChange={(e) => setDiagnostico(e.target.checked)} />
          Modo diagnóstico (não grava)
        </label>
      </div>

      <div
        className={`dropzone ${arrastando ? 'ativo' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setArrastando(true) }}
        onDragLeave={() => setArrastando(false)}
        onDrop={aoSoltar}
        onClick={() => inputRef.current?.click()}
      >
        {enviando ? (
          'Processando…'
        ) : (
          <>
            <strong>{diagnostico ? 'Solte PDFs para analisar sem gravar' : 'Arraste PDFs de boletos Sicoob aqui'}</strong>
            ou clique para selecionar — múltiplos arquivos são aceitos
          </>
        )}
        <input
          ref={inputRef} type="file" accept="application/pdf" multiple hidden
          onChange={(e) => { enviar([...e.target.files]); e.target.value = '' }}
        />
      </div>

      {conflito409 && (
        <div className="aviso-409">
          <strong>Arquivo(s) já processado(s).</strong>
          <div style={{ fontSize: 12.5, margin: '6px 0 10px' }}>
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
        <div style={{ marginTop: 18 }}>
          <h3>Resultado</h3>
          {resultados.map((r, i) => <ResultadoArquivo key={i} r={r} />)}
        </div>
      )}

      {resultadoDiag && (
        <div style={{ marginTop: 18 }}>
          <h3>Diagnóstico de extração (nada foi gravado)</h3>
          {resultadoDiag.map((a, i) => <DiagnosticoArquivo key={i} arquivo={a} />)}
        </div>
      )}
    </div>
  )
}
