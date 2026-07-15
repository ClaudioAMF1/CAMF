import { createContext, useContext, useMemo, useState } from 'react'

const FiltrosContext = createContext(null)

const VAZIO = {
  pagador_id: '',
  situacao: '',
  qualidade: '',
  vencimento_de: '',
  vencimento_ate: '',
  valor_min: '',
  valor_max: '',
}

export function FiltrosProvider({ children }) {
  const [filtros, setFiltros] = useState(VAZIO)

  const valor = useMemo(() => {
    const ativos = Object.fromEntries(
      Object.entries(filtros).filter(([, v]) => v !== '' && v !== null)
    )
    const limpar = () => setFiltros(VAZIO)
    const temAtivos = Object.keys(ativos).length > 0
    return { filtros, ativos, temAtivos, setFiltros, limpar }
  }, [filtros])

  return <FiltrosContext.Provider value={valor}>{children}</FiltrosContext.Provider>
}

export function useFiltros() {
  return useContext(FiltrosContext)
}
