interface Props {
  error: Error | null | unknown
  title?: string
}

export function ErrorBanner({ error, title = 'Error' }: Props) {
  if (!error) return null
  const msg = error instanceof Error ? error.message : String(error)
  return (
    <div className="error-banner">
      <svg className="error-banner-icon" width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
        <circle cx="8" cy="8" r="6" />
        <path d="M8 5v3M8 11v.5" />
      </svg>
      <div>
        <span className="error-banner-title">{title}: </span>
        {msg}
      </div>
    </div>
  )
}
