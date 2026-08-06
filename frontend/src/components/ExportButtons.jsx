import { useState } from 'react'
import { qs, urlExportacao } from '../api'
import { useFiltros } from '../filtros'
import { IconBaixar } from '../icons'

export default function ExportButtons() {
  const { ativos } = useFiltros()
  const [aberto, setAberto] = useState(false)

  const opcoes = [
    ['Excel (.xlsx)', urlExportacao('xlsx', ativos), 'Abas Resumo, Pagadores e Detalhado'],
    ['PDF', urlExportacao('pdf', ativos), 'Relatório pronto para imprimir'],
    ['CSV — boletos', urlExportacao('csv', ativos), 'Uma linha por boleto, com CPF/CNPJ'],
    ['CSV — pagadores', `/api/relatorios/csv${qs({ ...ativos, aba: 'pagadores' })}`, 'Cadastro e totais por pessoa'],
  ]

  return (
    <div style={{ position: 'relative' }}>
      <button className="principal-btn" onClick={() => setAberto((a) => !a)}>
        <IconBaixar /> Exportar
      </button>
      {aberto && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 30 }} onClick={() => setAberto(false)} />
          <div className="menu-flutuante">
            {opcoes.map(([rotulo, href, descricao]) => (
              <a key={rotulo} href={href} onClick={() => setAberto(false)}>
                <span className="rotulo">{rotulo}</span>
                <span className="descricao">{descricao}</span>
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
