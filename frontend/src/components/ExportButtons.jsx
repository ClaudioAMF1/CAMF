import { urlExportacao } from '../api'
import { useFiltros } from '../filtros'

export default function ExportButtons() {
  const { ativos } = useFiltros()
  return (
    <div className="acoes">
      <a className="botao" href={urlExportacao('pdf', ativos)}>Exportar PDF</a>
      <a className="botao" href={urlExportacao('xlsx', ativos)}>Exportar Excel</a>
      <a className="botao" href={urlExportacao('csv', ativos)}>Exportar CSV</a>
    </div>
  )
}
