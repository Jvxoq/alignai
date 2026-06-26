import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function FallbackUI({ error, errorInfo, onReset }) {
  const [showDetails, setShowDetails] = useState(false)
  const navigate = useNavigate()
  const isDev = import.meta.env.DEV

  const handleGoHome = () => {
    onReset()
    navigate('/')
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      padding: '2rem',
      backgroundColor: '#0a0a0a',
      color: '#e0e0e0',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>
      <div style={{
        maxWidth: '600px',
        width: '100%',
        textAlign: 'center',
      }}>
        <h1 style={{
          fontSize: '2rem',
          fontWeight: '600',
          marginBottom: '1rem',
          color: '#ef4444',
        }}>
          Something went wrong
        </h1>

        <p style={{
          fontSize: '1rem',
          marginBottom: '2rem',
          color: '#a0a0a0',
        }}>
          The application encountered an unexpected error. Please try refreshing the page or returning to the home page.
        </p>

        <div style={{
          display: 'flex',
          gap: '1rem',
          justifyContent: 'center',
          marginBottom: '2rem',
        }}>
          <button
            onClick={onReset}
            style={{
              padding: '0.75rem 1.5rem',
              fontSize: '1rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              fontWeight: '500',
            }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#2563eb'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#3b82f6'}
          >
            Try Again
          </button>

          <button
            onClick={handleGoHome}
            style={{
              padding: '0.75rem 1.5rem',
              fontSize: '1rem',
              backgroundColor: '#374151',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              fontWeight: '500',
            }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#4b5563'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#374151'}
          >
            Go Home
          </button>
        </div>

        {isDev && error && (
          <div style={{ textAlign: 'left' }}>
            <button
              onClick={() => setShowDetails(!showDetails)}
              style={{
                marginBottom: '1rem',
                padding: '0.5rem 1rem',
                fontSize: '0.875rem',
                backgroundColor: '#1f2937',
                color: '#9ca3af',
                border: '1px solid #374151',
                borderRadius: '0.25rem',
                cursor: 'pointer',
                width: '100%',
              }}
            >
              {showDetails ? 'Hide' : 'Show'} Error Details
            </button>

            {showDetails && (
              <div style={{
                padding: '1rem',
                backgroundColor: '#1f2937',
                borderRadius: '0.375rem',
                border: '1px solid #374151',
                overflowX: 'auto',
              }}>
                <p style={{
                  fontSize: '0.875rem',
                  fontWeight: '600',
                  marginBottom: '0.5rem',
                  color: '#ef4444',
                }}>
                  {error.toString()}
                </p>
                {errorInfo && errorInfo.componentStack && (
                  <pre style={{
                    fontSize: '0.75rem',
                    color: '#9ca3af',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    margin: 0,
                  }}>
                    {errorInfo.componentStack}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
