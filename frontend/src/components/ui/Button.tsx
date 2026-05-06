import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'success'
type Size = 'xs' | 'sm' | 'md' | 'lg'

interface BaseProps {
  variant?: Variant
  size?: Size
  loading?: boolean
}

type ButtonProps = BaseProps & ButtonHTMLAttributes<HTMLButtonElement> & { as?: 'button' }
type AnchorProps = BaseProps & AnchorHTMLAttributes<HTMLAnchorElement> & { as: 'a' }
type Props = ButtonProps | AnchorProps

function classes(variant: Variant = 'primary', size: Size = 'md') {
  return `btn btn-${variant} btn-${size}`
}

export function Button({ variant = 'primary', size = 'md', loading, as: Tag = 'button', children, ...rest }: Props) {
  const cls = classes(variant, size)

  if (Tag === 'a') {
    return (
      <a className={cls} {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}>
        {loading ? <span className="spinner spinner-xs" /> : null}
        {children}
      </a>
    )
  }

  const btnRest = rest as ButtonHTMLAttributes<HTMLButtonElement>
  return (
    <button className={cls} disabled={btnRest.disabled || loading} {...btnRest}>
      {loading ? <span className="spinner spinner-xs" /> : null}
      {children}
    </button>
  )
}
