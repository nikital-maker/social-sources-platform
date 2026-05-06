import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'

interface LabeledProps {
  label?: string
  id?: string
}

type InputProps = LabeledProps & InputHTMLAttributes<HTMLInputElement>
type SelectProps = LabeledProps & SelectHTMLAttributes<HTMLSelectElement>
type TextareaProps = LabeledProps & TextareaHTMLAttributes<HTMLTextAreaElement>

export function Input({ label, id, className, ...rest }: InputProps) {
  return (
    <div className="form-field">
      {label && <label className="form-label" htmlFor={id}>{label}</label>}
      <input id={id} className={`form-input${className ? ` ${className}` : ''}`} {...rest} />
    </div>
  )
}

export function Select({ label, id, children, className, ...rest }: SelectProps) {
  return (
    <div className="form-field">
      {label && <label className="form-label" htmlFor={id}>{label}</label>}
      <select id={id} className={`form-select${className ? ` ${className}` : ''}`} {...rest}>
        {children}
      </select>
    </div>
  )
}

export function Textarea({ label, id, className, ...rest }: TextareaProps) {
  return (
    <div className="form-field">
      {label && <label className="form-label" htmlFor={id}>{label}</label>}
      <textarea id={id} className={`form-textarea${className ? ` ${className}` : ''}`} {...rest} />
    </div>
  )
}
