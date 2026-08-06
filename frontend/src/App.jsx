import { NavLink, Route, Routes } from 'react-router-dom'
import { FiltrosProvider } from './filtros'
import {
  IconBoletos, IconDashboard, IconHistorico, IconPagadores, IconUpload, IconVencimentos,
} from './icons'
import BoletosPage from './pages/BoletosPage'
import DashboardPage from './pages/DashboardPage'
import PagadoresPage from './pages/PagadoresPage'
import UploadPage from './pages/UploadPage'
import UploadsPage from './pages/UploadsPage'
import VencimentosPage from './pages/VencimentosPage'
import { BotaoTema } from './ui'

const secoes = [
  ['Visão geral', [
    ['/', 'Dashboard', IconDashboard],
    ['/vencimentos', 'Vencimentos', IconVencimentos],
    ['/boletos', 'Boletos', IconBoletos],
    ['/pagadores', 'Pagadores', IconPagadores],
  ]],
  ['Importação', [
    ['/upload', 'Enviar PDFs', IconUpload],
    ['/uploads', 'Histórico', IconHistorico],
  ]],
]

export default function App() {
  return (
    <FiltrosProvider>
      <div className="layout">
        <nav className="lateral">
          <div className="marca">
            <div className="marca-selo">CA</div>
            <div>
              <h1>CAMF Construtora</h1>
              <small>Contas a Receber</small>
            </div>
          </div>

          {secoes.map(([titulo, itens]) => (
            <div key={titulo}>
              <div className="nav-grupo">{titulo}</div>
              {itens.map(([para, rotulo, Icone]) => (
                <NavLink key={para} to={para} end={para === '/'} className={({ isActive }) => (isActive ? 'ativo' : '')}>
                  <Icone />
                  {rotulo}
                </NavLink>
              ))}
            </div>
          ))}

          <div className="lateral-rodape">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <div>
                Sicoob · Banco 756
                <div style={{ opacity: .75 }}>CNPJ 42.800.118/0001-44</div>
              </div>
              <BotaoTema />
            </div>
          </div>
        </nav>

        <main className="conteudo">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/vencimentos" element={<VencimentosPage />} />
            <Route path="/boletos" element={<BoletosPage />} />
            <Route path="/pagadores" element={<PagadoresPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/uploads" element={<UploadsPage />} />
          </Routes>
        </main>
      </div>
    </FiltrosProvider>
  )
}
