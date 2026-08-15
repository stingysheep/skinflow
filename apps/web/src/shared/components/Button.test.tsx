import { render, screen } from '@testing-library/react'

import { Button } from './Button'

describe('Button', () => {
  it('keeps native button semantics and marks loading state', () => {
    render(<Button loading>保存</Button>)
    const button = screen.getByRole('button', { name: '保存' })

    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button.tagName).toBe('BUTTON')
  })

  it('supports an accessible icon-only label', () => {
    render(<Button aria-label="打开设置" icon={<span aria-hidden="true">+</span>} />)
    expect(screen.getByRole('button', { name: '打开设置' })).toBeInTheDocument()
  })
})
