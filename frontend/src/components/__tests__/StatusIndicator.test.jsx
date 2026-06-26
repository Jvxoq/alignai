import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusIndicator from '../ResponseSection/StatusIndicator'

describe('StatusIndicator', () => {
  it('should not render when status is idle', () => {
    const { container } = render(<StatusIndicator status="idle" message="" error={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('should not render when status is complete', () => {
    const { container } = render(<StatusIndicator status="complete" message="" error={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('should render with connecting status', () => {
    render(<StatusIndicator status="connecting" message="" error={null} />)
    expect(screen.getByText('Connecting...')).toBeInTheDocument()
  })

  it('should render with streaming status', () => {
    render(<StatusIndicator status="streaming" message="" error={null} />)
    expect(screen.getByText('Analyzing...')).toBeInTheDocument()
  })

  it('should display custom message when provided', () => {
    render(<StatusIndicator status="streaming" message="Retrieving documents..." error={null} />)
    expect(screen.getByText('Retrieving documents...')).toBeInTheDocument()
  })

  it('should render error status', () => {
    render(<StatusIndicator status="error" message="" error="Network error" />)
    expect(screen.getByText('Network error')).toBeInTheDocument()
  })

  it('should apply error class when error occurs', () => {
    const { container } = render(<StatusIndicator status="error" message="" error="Error message" />)
    expect(container.firstChild).toHaveClass('status-indicator--error')
  })

  it('should apply active class when streaming', () => {
    const { container } = render(<StatusIndicator status="streaming" message="" error={null} />)
    expect(container.firstChild).toHaveClass('status-indicator--active')
  })

  it('should show status dot when active', () => {
    const { container } = render(<StatusIndicator status="connecting" message="" error={null} />)
    expect(container.querySelector('.status-dot')).toBeInTheDocument()
  })

  it('should not show status dot when error', () => {
    const { container } = render(<StatusIndicator status="error" message="" error="Error" />)
    expect(container.querySelector('.status-dot')).not.toBeInTheDocument()
  })

  it('should show default error message when error is true but no message', () => {
    render(<StatusIndicator status="error" message="" error="" />)
    expect(screen.getByText('An error occurred')).toBeInTheDocument()
  })
})
