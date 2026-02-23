import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'

// Typed axios instance that reflects the response interceptor's runtime behavior:
// the interceptor unwraps `response.data`, so callers receive `T` directly instead
// of `AxiosResponse<T>`.
export interface TypedAxiosInstance {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
}

const _axios: AxiosInstance = axios.create({
  baseURL: '/',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Unwrap response.data so callers receive the payload directly.
// TypedAxiosInstance above keeps the TypeScript types aligned with this behavior.
_axios.interceptors.response.use(
  (response) => response.data,
  (error) => {
    return Promise.reject(error)
  }
)

export const api = _axios as unknown as TypedAxiosInstance

export default api
