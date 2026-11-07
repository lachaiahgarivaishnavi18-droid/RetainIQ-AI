import axios from 'axios'
const configuredApi = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')
export const backendConfigured = !import.meta.env.PROD || Boolean(configuredApi)
export const api = axios.create({baseURL: configuredApi || '/api', timeout: 180000})
api.interceptors.request.use(config => { const token = sessionStorage.getItem('retainiq-token'); if(token) config.headers.Authorization = `Bearer ${token}`; return config })
export const errorMessage = (e: unknown): string => {
  if (axios.isAxiosError(e)) {
    const detail = e.response?.data?.detail
    return typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : e.message
  }
  return e instanceof Error ? e.message : 'Operation failed'
}
export const pct = (v: number | null | undefined) => v == null ? '—' : `${(v * 100).toFixed(1)}%`
export const money = (v: number | null | undefined) => v == null ? '—' : new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(v)
