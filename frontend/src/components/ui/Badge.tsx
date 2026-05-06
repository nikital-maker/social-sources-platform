type Variant = 'success' | 'danger' | 'warning' | 'info' | 'neutral' | 'accent'
type Size = 'sm' | 'md'

interface Props {
  variant?: Variant
  size?: Size
  children: React.ReactNode
  className?: string
}

export function Badge({ variant = 'neutral', size = 'sm', children, className }: Props) {
  return (
    <span className={`badge badge-${size} badge-${variant}${className ? ` ${className}` : ''}`}>
      {children}
    </span>
  )
}
