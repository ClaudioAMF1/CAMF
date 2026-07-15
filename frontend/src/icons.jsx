const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  viewBox: '0 0 24 24',
}

export const IconDashboard = () => (
  <svg {...base}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>
)
export const IconBoletos = () => (
  <svg {...base}><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M7 9v6M10 9v6M13 9v6M17 9v6" /></svg>
)
export const IconPagadores = () => (
  <svg {...base}><circle cx="9" cy="8" r="3.2" /><path d="M3.5 19c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5" /><circle cx="17" cy="9" r="2.4" /><path d="M15.6 14.7c2.6.2 4.3 1.6 4.9 4.3" /></svg>
)
export const IconUpload = () => (
  <svg {...base}><path d="M12 16V5M7.5 9.5 12 5l4.5 4.5" /><path d="M4 16.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5" /></svg>
)
export const IconHistorico = () => (
  <svg {...base}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></svg>
)
