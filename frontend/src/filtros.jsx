import { createContext, useContext, useMemo, useState } from 'react'

const FiltrosContext = createContext(null)

export function FiltrosProvider({ children }) {
  const [filtros, setFiltros] = useState({
    pagador_id: '',
    situacao: '',
    qualidade: '',
    vencimento_de: '',
    vencimento_ate: '',
  })

  const valor = useMemo(() => {
    const ativos = Object.fromEntries(
      Object.entries(filtros).filter(([, v]) => v !== '' && v !== null)
    )
    return { filtros, ativos, setFiltros }
  }, [filtros])

  return <FiltrosContext.Provider value={valor}>{children}</FiltrosContext.Provider>
}

export function useFiltros() {
  return useContext(FiltrosContext)
}
