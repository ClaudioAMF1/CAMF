import { NavLink, Route, Routes } from 'react-router-dom'
import { FiltrosProvider } from './filtros'
import { IconBoletos, IconDashboard, IconHistorico, IconPagadores, IconUpload } from './icons'
import BoletosPage from './pages/BoletosPage'
import DashboardPage from './pages/DashboardPage'
import PagadoresPage from './pages/PagadoresPage'
import UploadPage from './pages/UploadPage'
import UploadsPage from './pages/UploadsPage'

const links = [
  ['/', 'Dashboard', IconDashboard],
  ['/boletos', 'Boletos', IconBoletos],
  ['/pagadores', 'Pagadores', IconPagadores],
  ['/upload', 'Enviar PDFs', IconUpload],
  ['/uploads', 'Histórico de uploads', IconHistorico],
]

export default function App() {
  return (
    <FiltrosProvider>
      <div className="layout">
        <nav className="sidebar">
          <div className="marca">
            <h1>
              CAMF Construtora
              <small>Contas a Receber · Sicoob 756</small>
            </h1>
          </div>
          {links.map(([para, rotulo, Icone]) => (
            <NavLink key={para} to={para} end={para === '/'} className={({ isActive }) => (isActive ? 'ativo' : '')}>
              <Icone />
              {rotulo}
            </NavLink>
          ))}
          <div className="rodape">CNPJ 42.800.118/0001-44</div>
        </nav>
        <main className="conteudo">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
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
