import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { uploadArquivos } from '../api'
import { fmtBRL, fmtData, ROTULOS_DIVERGENCIA } from '../format'
import { IconUpload } from '../icons'
import { useToast } from '../ui'

function ResultadoArquivo({ r }) {
  const classe = r.erro ? (r.erro === 'arquivo_ja_processado' ? 'duplicado' : 'erro') : ''
  return (
    <div className={`res-arquivo ${classe}`}>
      <div className="nome">{r.nome}</div>
      <div className="detalhes">
        {r.erro === 'arquivo_ja_processado' && <span>Arquivo já processado (upload #{r.upload_id}).</span>}
        {r.erro && r.erro !== 'arquivo_ja_processado' && <span className="erro-txt">Erro: {r.erro}</span>}
        {!r.erro && (
          <div className="acoes">
            <span className="etiqueta pago sem-ponto">{r.novos} novo(s)</span>
            {r.atualizados > 0 && <span className="etiqueta aberto sem-ponto">{r.atualizados} atualizado(s)</span>}
            {r.duplicados > 0 && <span className="etiqueta neutra sem-ponto">{r.duplicados} duplicado(s)</span>}
            {r.revisao_manual > 0 && <span className="etiqueta revisao">{r.revisao_manual} p/ revisão</span>}
            {r.ignoradas?.length > 0 && (
              <span className="etiqueta neutra sem-ponto">
                {r.ignoradas.length} página(s) ignorada(s): {r.ignoradas.join(', ')}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function Campo({ rotulo, valor }) {
  const vazio = valor === null || valor === undefined || valor === ''
  return (
    <div>
      <b>{rotulo}</b>
      {vazio ? <span style={{ color: 'var(--vermelho)' }}>não extraído</span> : String(valor)}
    </div>
  )
}

function Diagnostico({ arquivo }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontWeight: 600 }}>{arquivo.nome}</div>
      {arquivo.erro && <div className="erro-txt">Erro: {arquivo.erro}</div>}
      {arquivo.paginas.map((p) => (
        <div className="diag" key={p.pagina}>
          <div className="acoes">
            <strong>Página {p.pagina}</strong>
            {p.tem_linha_digitavel
              ? <span className="etiqueta pago">linha digitável OK</span>
              : p.parece_boleto
                ? <span className="etiqueta vencido">parece boleto, linha não reconhecida</span>
                : <span className="etiqueta neutra">ignorada (não é boleto)</span>}
            {p.divergencias?.length > 0 && (
              <span className="etiqueta revisao">
                {p.divergencias.map((d) => ROTULOS_DIVERGENCIA[d] || d).join('; ')}
              </span>
            )}
            {p.divergencias?.length === 0 && p.tem_linha_digitavel && (
              <span className="etiqueta pago">sem divergências</span>
            )}
          </div>
          {p.campos && (
            <div className="grade-campos">
              <Campo rotulo="Pagador" valor={p.campos.pagador_nome} />
              <Campo rotulo="CPF/CNPJ" valor={p.campos.pagador_cpf_cnpj} />
              <Campo rotulo="Valor (texto)" valor={p.campos.valor && fmtBRL(p.campos.valor)} />
              <Campo rotulo="Valor (linha digitável)" valor={p.campos.valor_linha && fmtBRL(p.campos.valor_linha)} />
              <Campo rotulo="Vencimento (texto)" valor={p.campos.vencimento && fmtData(p.campos.vencimento)} />
              <Campo rotulo="Vencimento (linha)" valor={p.campos.vencimento_linha && fmtData(p.campos.vencimento_linha)} />
              <Campo rotulo="Nº documento" valor={p.campos.num_documento} />
              <Campo rotulo="Nosso número" valor={p.campos.nosso_numero} />
              <Campo rotulo="Emissão" valor={p.campos.data_emissao && fmtData(p.campos.data_emissao)} />
              <Campo rotulo="Beneficiário" valor={p.campos.beneficiario_nome} />
              <Campo rotulo="Endereço" valor={p.campos.endereco} />
              <Campo rotulo="Município/UF" valor={[p.campos.municipio, p.campos.uf].filter(Boolean).join(' - ')} />
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
  const [conflito, setConflito] = useState(null)
  const inputRef = useRef()
  const queryClient = useQueryClient()
  const notificar = useToast()

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
    setConflito(null)
    try {
      if (diagnostico && !forcar) {
        await analisar(files)
        return
      }
      const resposta = await uploadArquivos(files, forcar)
      setResultados(resposta.arquivos)
      setResultadoDiag(null)
      queryClient.invalidateQueries()
      const novos = resposta.arquivos.reduce((s, a) => s + (a.novos || 0), 0)
      const atualizados = resposta.arquivos.reduce((s, a) => s + (a.atualizados || 0), 0)
      notificar(
        atualizados > 0
          ? `${novos} novo(s), ${atualizados} atualizado(s)`
          : `${novos} boleto(s) importado(s)`
      )
    } catch (erro) {
      if (erro.status === 409) {
        setConflito({ detalhe: erro.detail, files })
        setResultados(null)
      } else {
        setResultados([{ nome: 'Falha no envio', erro: String(erro.message || erro) }])
        notificar('Falha no envio', 'erro')
      }
    } finally {
      setEnviando(false)
    }
  }

  const aoSoltar = (e) => {
    e.preventDefault()
    setArrastando(false)
    enviar([...e.dataTransfer.files].filter(
      (f) => f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf'
    ))
  }

  return (
    <div>
      <div className="topo">
        <div>
          <h2>Enviar boletos</h2>
          <div className="sub">
            Cada página com linha digitável vira um boleto. Duplicados são ignorados automaticamente.
          </div>
        </div>
        <label className="marcador" title="Extrai e mostra os campos reconhecidos sem gravar nada">
          <input type="checkbox" checked={diagnostico} onChange={(e) => setDiagnostico(e.target.checked)} />
          Modo diagnóstico (não grava)
        </label>
      </div>

      <div
        className={`solta ${arrastando ? 'ativa' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setArrastando(true) }}
        onDragLeave={() => setArrastando(false)}
        onDrop={aoSoltar}
        onClick={() => inputRef.current?.click()}
      >
        <div className="icone-grande"><IconUpload /></div>
        {enviando ? (
          <strong>Processando…</strong>
        ) : (
          <>
            <strong>{diagnostico ? 'Solte PDFs para analisar sem gravar' : 'Arraste PDFs de boletos Sicoob aqui'}</strong>
            <span>ou clique para selecionar — vários arquivos de uma vez</span>
          </>
        )}
        <input ref={inputRef} type="file" accept="application/pdf" multiple hidden
          onChange={(e) => { enviar([...e.target.files]); e.target.value = '' }} />
      </div>

      {conflito && (
        <div className="aviso">
          <strong>Arquivo(s) já processado(s)</strong>
          <div style={{ fontSize: 12.5, margin: '7px 0 12px' }}>
            {(conflito.detalhe?.uploads_originais || []).map((u) => (
              <div key={u.upload.id}>
                {u.nome} → upload #{u.upload.id} de {new Date(u.upload.criado_em).toLocaleString('pt-BR')}
                {' '}({u.upload.qtd_boletos_novos} boletos, {u.upload.qtd_ignoradas} páginas ignoradas)
              </div>
            ))}
          </div>
          <button className="principal-btn" onClick={() => enviar(conflito.files, true)}>
            Reprocessar e atualizar os boletos
          </button>
          <div style={{ fontSize: 12, color: 'var(--ambar)', marginTop: 8 }}>
            Os boletos deste arquivo são re-extraídos e atualizados (pagador, CPF/CNPJ, valores).
            Pagamentos já registrados e o histórico são preservados.
          </div>
        </div>
      )}

      {resultados && (
        <div style={{ marginTop: 20 }}>
          <h3>Resultado</h3>
          {resultados.map((r, i) => <ResultadoArquivo key={i} r={r} />)}
        </div>
      )}

      {resultadoDiag && (
        <div style={{ marginTop: 20 }}>
          <h3>Diagnóstico de extração — nada foi gravado</h3>
          {resultadoDiag.map((a, i) => <Diagnostico key={i} arquivo={a} />)}
        </div>
      )}
    </div>
  )
}
