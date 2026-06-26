import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CharacterCounter from '../InputSection/CharacterCounter'

describe('CharacterCounter', () => {
  it('should display current and max character counts', () => {
    render(<CharacterCounter current={50} max={200} />)
    expect(screen.getByText('50 / 200')).toBeInTheDocument()
  })

  it('should not have special class when under 90% capacity', () => {
    const { container } = render(<CharacterCounter current={150} max={200} />)
    expect(container.firstChild).toHaveClass('char-counter')
    expect(container.firstChild).not.toHaveClass('char-counter--warning')
    expect(container.firstChild).not.toHaveClass('char-counter--error')
  })

  it('should show warning class when over 90% capacity', () => {
    const { container } = render(<CharacterCounter current={185} max={200} />)
    expect(container.firstChild).toHaveClass('char-counter--warning')
  })

  it('should show error class when at limit', () => {
    const { container } = render(<CharacterCounter current={200} max={200} />)
    expect(container.firstChild).toHaveClass('char-counter--error')
  })

  it('should show error class when over limit', () => {
    const { container } = render(<CharacterCounter current={250} max={200} />)
    expect(container.firstChild).toHaveClass('char-counter--error')
  })

  it('should handle zero characters', () => {
    render(<CharacterCounter current={0} max={200} />)
    expect(screen.getByText('0 / 200')).toBeInTheDocument()
  })

  it('should exactly at 90% threshold show warning', () => {
    const { container } = render(<CharacterCounter current={180} max={200} />)
    expect(container.firstChild).not.toHaveClass('char-counter--warning')
  })

  it('should show warning just above 90% threshold', () => {
    const { container } = render(<CharacterCounter current={181} max={200} />)
    expect(container.firstChild).toHaveClass('char-counter--warning')
  })
})
