import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from './Button'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.setState({
      error,
      errorInfo,
    })
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900 p-4">
          <div className="max-w-md w-full bg-gray-800 rounded-lg p-6 space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertCircle className="w-6 h-6" />
              <h2 className="text-xl font-semibold">Something went wrong</h2>
            </div>
            
            <p className="text-gray-300">
              An unexpected error occurred. Please try refreshing the page or contact support if the problem persists.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <div className="bg-gray-900 rounded p-4 text-sm font-mono text-red-400 overflow-auto max-h-48">
                <div className="font-semibold mb-2">Error:</div>
                <div>{this.state.error.toString()}</div>
                {this.state.errorInfo && (
                  <>
                    <div className="font-semibold mt-4 mb-2">Stack trace:</div>
                    <div className="text-xs text-gray-500">
                      {this.state.errorInfo.componentStack}
                    </div>
                  </>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <Button onClick={this.handleReset} variant="primary">
                Try Again
              </Button>
              <Button
                onClick={() => window.location.reload()}
                variant="secondary"
              >
                Reload Page
              </Button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
