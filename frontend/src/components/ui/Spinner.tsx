type Size = 'xs' | 'sm' | 'md' | 'lg'

interface Props {
  size?: Size
  className?: string
}

export function Spinner({ size = 'md', className }: Props) {
  return <span className={`spinner spinner-${size}${className ? ` ${className}` : ''}`} />
}

interface LoadingProps {
  text?: string
}

export function LoadingState({ text = 'Loading…' }: LoadingProps) {
  return (
    <div className="loading-state">
      <Spinner size="sm" />
      <span>{text}</span>
    </div>
  )
}
