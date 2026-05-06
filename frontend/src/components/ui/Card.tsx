type Padding = 'none' | 'sm' | 'md' | 'lg'

interface Props {
  children: React.ReactNode
  padding?: Padding
  className?: string
  style?: React.CSSProperties
}

interface HeaderProps {
  title: string
  action?: React.ReactNode
}

export function Card({ children, padding = 'md', className, style }: Props) {
  return (
    <div className={`card card-${padding}${className ? ` ${className}` : ''}`} style={style}>
      {children}
    </div>
  )
}

export function CardHeader({ title, action }: HeaderProps) {
  return (
    <div className="card-header">
      <span className="card-title">{title}</span>
      {action}
    </div>
  )
}
