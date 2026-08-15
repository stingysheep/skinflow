import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  loading?: boolean
  icon?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({
  variant = 'secondary',
  loading = false,
  icon,
  children,
  disabled,
  className,
  ...props
}, ref) {
  const classes = ['ui-button', `ui-button-${variant}`, className].filter(Boolean).join(' ')

  return (
    <button
      ref={ref}
      {...props}
      aria-busy={loading || undefined}
      className={classes}
      disabled={disabled || loading}
      type={props.type ?? 'button'}
    >
      {loading ? <span aria-hidden="true" className="ui-button-spinner" /> : icon}
      {children}
    </button>
  )
})
