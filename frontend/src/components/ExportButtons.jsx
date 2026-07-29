import { urlExportacao } from '../api'
import { useFiltros } from '../filtros'

export default function ExportButtons() {
  const { ativos } = useFiltros()
  return (
    <div className="acoes">
      <a className="botao" href={urlExportacao('pdf', ativos)}>PDF</a>
      <a className="botao" href={urlExportacao('xlsx', ativos)}>Excel</a>
      <a className="botao" href={urlExportacao('csv', ativos)}>CSV</a>
    </div>
  )
}
