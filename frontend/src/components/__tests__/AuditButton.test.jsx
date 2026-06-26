import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuditButton from '../InputSection/AuditButton'

describe('AuditButton', () => {
  it('should render with default text', () => {
    render(<AuditButton onClick={vi.fn()} disabled={false} loading={false} compact={false} />)
    expect(screen.getByRole('button', { name: /Audit for Compliance/i })).toBeInTheDocument()
  })

  it('should render with compact text', () => {
    render(<AuditButton onClick={vi.fn()} disabled={false} loading={false} compact={true} />)
    expect(screen.getByRole('button', { name: /Send/i })).toBeInTheDocument()
  })

  it('should show loading text when loading', () => {
    render(<AuditButton onClick={vi.fn()} disabled={false} loading={true} compact={false} />)
    expect(screen.getByText('Auditing...')).toBeInTheDocument()
  })

  it('should call onClick when clicked', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()

    render(<AuditButton onClick={handleClick} disabled={false} loading={false} compact={false} />)

    await user.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('should be disabled when disabled prop is true', () => {
    render(<AuditButton onClick={vi.fn()} disabled={true} loading={false} compact={false} />)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('should be disabled when loading', () => {
    render(<AuditButton onClick={vi.fn()} disabled={false} loading={true} compact={false} />)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('should not call onClick when disabled', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()

    render(<AuditButton onClick={handleClick} disabled={true} loading={false} compact={false} />)

    await user.click(screen.getByRole('button'))
    expect(handleClick).not.toHaveBeenCalled()
  })

  it('should apply loading class when loading', () => {
    const { container } = render(<AuditButton onClick={vi.fn()} disabled={false} loading={true} compact={false} />)
    expect(container.firstChild).toHaveClass('audit-button--loading')
  })

  it('should show spinner when loading', () => {
    const { container } = render(<AuditButton onClick={vi.fn()} disabled={false} loading={true} compact={false} />)
    expect(container.querySelector('.audit-spinner')).toBeInTheDocument()
  })

  it('should not show spinner when not loading', () => {
    const { container } = render(<AuditButton onClick={vi.fn()} disabled={false} loading={false} compact={false} />)
    expect(container.querySelector('.audit-spinner')).not.toBeInTheDocument()
  })
})
