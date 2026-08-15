import * as DialogPrimitive from '@radix-ui/react-dialog'
import type { ReactNode, RefObject } from 'react'
import { X } from 'lucide-react'

type DialogProps = {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  trigger?: ReactNode
  finalFocusRef?: RefObject<HTMLElement | null>
  title: string
  description?: string
  contentClassName?: string
  children: ReactNode
}

export function Dialog({ open, onOpenChange, trigger, finalFocusRef, title, description, contentClassName, children }: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      {trigger ? <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger> : null}
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="dialog-overlay" />
        <DialogPrimitive.Content
          className={contentClassName ? `dialog-content ${contentClassName}` : 'dialog-content'}
          onCloseAutoFocus={(event) => {
            if (!finalFocusRef?.current) return
            event.preventDefault()
            finalFocusRef.current.focus()
          }}
        >
          <DialogPrimitive.Title className="dialog-title">{title}</DialogPrimitive.Title>
          {description ? <DialogPrimitive.Description className="dialog-description">{description}</DialogPrimitive.Description> : null}
          <div className="dialog-body">{children}</div>
          <DialogPrimitive.Close asChild>
            <button className="dialog-close" type="button" aria-label="关闭">
              <X aria-hidden="true" size={18} />
            </button>
          </DialogPrimitive.Close>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
