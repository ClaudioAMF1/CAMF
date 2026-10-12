import { useState } from 'react'
import { qs, urlExportacao } from '../api'
import { useFiltros } from '../filtros'
import { IconBaixar } from '../icons'

const CHAVE_TAXA = 'camf-taxa-juros'

function lerTaxa() {
  try { return localStorage.getItem(CHAVE_TAXA) ?? '1,69' } catch { return '1,69' }
}

/** "1,69" -> "1.69"; vazio ou inválido -> undefined (a coluna sai em branco). */
function taxaParaApi(texto) {
  const numero = Number(String(texto).replace(/\./g, '').replace(',', '.'))
  return texto.trim() && Number.isFinite(numero) && numero >= 0 && numero <= 100 ? numero : undefined
}

export default function ExportButtons() {
  const { ativos } = useFiltros()
  const [aberto, setAberto] = useState(false)
  const [taxa, setTaxa] = useState(lerTaxa)

  const mudarTaxa = (valor) => {
    setTaxa(valor)
    try { localStorage.setItem(CHAVE_TAXA, valor) } catch { /* sem armazenamento: só não lembra */ }
  }

  const fechar = () => setAberto(false)

  const opcoes = [
    ['Excel (.xlsx)', urlExportacao('xlsx', ativos), 'Abas Resumo, Pagadores e Detalhado'],
    ['PDF', urlExportacao('pdf', ativos), 'Relatório pronto para imprimir'],
    ['CSV — boletos', urlExportacao('csv', ativos), 'Uma linha por boleto, com CPF/CNPJ'],
    ['CSV — pagadores', `/api/relatorios/csv${qs({ ...ativos, aba: 'pagadores' })}`, 'Cadastro e totais por pessoa'],
  ]

  const parametrosTitulos = { ...ativos, taxa: taxaParaApi(taxa) }
  const modelos = [
    {
      rotulo: 'Parcelas em aberto',
      descricao: 'Por data de vencimento, com Total Cedente',
      url: (f) => `/api/relatorios/parcelas-em-aberto.${f}${qs(ativos)}`,
    },
    {
      rotulo: 'Relação de títulos',
      descricao: 'DOC, valores, vencimento, taxa e pagador',
      url: (f) => `/api/relatorios/titulos.${f}${qs(parametrosTitulos)}`,
      taxa: true,
    },
  ]

  return (
    <div style={{ position: 'relative' }}>
      <button className="principal-btn" onClick={() => setAberto((a) => !a)}>
        <IconBaixar /> Exportar
      </button>
      {aberto && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 30 }} onClick={fechar} />
          <div className="menu-flutuante menu-largo">
            <div className="menu-secao">Relatórios</div>
            {opcoes.map(([rotulo, href, descricao]) => (
              <a key={rotulo} href={href} onClick={fechar}>
                <span className="rotulo">{rotulo}</span>
                <span className="descricao">{descricao}</span>
              </a>
            ))}

            <div className="menu-secao">Modelos impressos <span>· só em aberto</span></div>
            {modelos.map((m) => (
              <div className="menu-modelo" key={m.rotulo}>
                <div className="menu-modelo-linha">
                  <div>
                    <span className="rotulo">{m.rotulo}</span>
                    <span className="descricao">{m.descricao}</span>
                  </div>
                  <div className="menu-formatos">
                    <a href={m.url('pdf')} onClick={fechar}>PDF</a>
                    <a href={m.url('xlsx')} onClick={fechar}>Excel</a>
                  </div>
                </div>
                {m.taxa && (
                  <label className="menu-taxa">
                    Tx. juros
                    <input
                      value={taxa} inputMode="decimal" placeholder="—"
                      onChange={(e) => mudarTaxa(e.target.value)}
                      aria-label="Taxa de juros em porcentagem"
                    />
                    %
                  </label>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
