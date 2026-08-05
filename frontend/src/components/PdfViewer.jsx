import { useEffect, useState } from 'react'
import { fmtBRL, fmtData } from '../format'

/** Abre o PDF original do boleto — por padrão só a página dele. */
export default function PdfViewer({ boleto, onFechar }) {
  const [completo, setCompleto] = useState(false)
  const [erro, setErro] = useState(null)

  const url = `/api/boletos/${boleto.id}/pdf${completo ? '?completo=true' : ''}`
  // view=Fit encaixa a página inteira; navpanes=0 esconde as miniaturas,
  // que só ocupam espaço quando o PDF tem uma página só
  const visorUrl = `${url}#view=Fit&navpanes=0`

  useEffect(() => {
    const fechar = (e) => e.key === 'Escape' && onFechar()
    window.addEventListener('keydown', fechar)
    return () => window.removeEventListener('keydown', fechar)
  }, [onFechar])

  // Confere antes de exibir: sem o arquivo guardado, mostra a orientação
  useEffect(() => {
    let ativo = true
    setErro(null)
    fetch(url, { method: 'GET', headers: { Range: 'bytes=0-0' } })
      .then(async (r) => {
        if (!ativo || r.ok || r.status === 206) return
        const corpo = await r.json().catch(() => ({}))
        setErro(corpo.detail || 'Não foi possível abrir o PDF.')
      })
      .catch(() => ativo && setErro('Não foi possível abrir o PDF.'))
    return () => { ativo = false }
  }, [url])

  return (
    <>
      <div className="veu" onClick={onFechar} />
      <div className="visor" role="dialog" aria-label="Visualizador de boleto">
        <div className="visor-topo">
          <div>
            <div className="titulo">
              Boleto {boleto.num_documento || `#${boleto.id}`}
              {boleto.pagador_nome ? ` — ${boleto.pagador_nome}` : ''}
            </div>
            <div className="sub-info">
              Vencimento {fmtData(boleto.vencimento)} · {fmtBRL(boleto.valor)}
              {boleto.pagina ? ` · página ${boleto.pagina} do arquivo` : ''}
            </div>
          </div>
          <div className="acoes" style={{ marginLeft: 'auto' }}>
            {boleto.pagina && (
              <div className="segmentado">
                <button className={!completo ? 'ativo' : ''} onClick={() => setCompleto(false)}>Só este boleto</button>
                <button className={completo ? 'ativo' : ''} onClick={() => setCompleto(true)}>Arquivo inteiro</button>
              </div>
            )}
            <a className="botao" href={url} target="_blank" rel="noreferrer">Abrir em nova aba</a>
            <a className="botao" href={url} download={`boleto_${boleto.num_documento || boleto.id}.pdf`}>Baixar</a>
            <button onClick={onFechar}>Fechar</button>
          </div>
        </div>
        <div className="visor-corpo">
          {erro ? (
            <div className="visor-erro">
              <div>
                <strong style={{ display: 'block', marginBottom: 8 }}>PDF não disponível</strong>
                <div style={{ color: 'var(--tinta-3)', maxWidth: 460 }}>{erro}</div>
              </div>
            </div>
          ) : (
            <iframe src={visorUrl} title="Boleto em PDF" />
          )}
        </div>
      </div>
    </>
  )
}
