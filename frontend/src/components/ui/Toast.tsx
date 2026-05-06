import { createContext, useCallback, useContext, useState } from 'react'

interface Toast {
  id: number
  message: string
  variant: 'success' | 'error' | 'warning' | 'info'
}

interface ToastContextValue {
  addToast: (message: string, variant?: Toast['variant']) => void
}

const ToastContext = createContext<ToastContextValue>({ addToast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

let nextId = 0

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, variant: Toast['variant'] = 'success') => {
    const id = ++nextId
    setToasts((prev) => [...prev, { id, message, variant }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.variant}`} onClick={() => dismiss(t.id)}>
            <span className="toast-icon">
              {t.variant === 'success' && '✓'}
              {t.variant === 'error' && '✕'}
              {t.variant === 'warning' && '⚠'}
              {t.variant === 'info' && 'ℹ'}
            </span>
            <span className="toast-message">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
