import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, errorId: null, error: null };
  }

  static getDerivedStateFromError(error) {
    const errorId = 'ERR-' + Math.random().toString(36).substring(2, 8).toUpperCase();
    return { hasError: true, errorId, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[React ErrorBoundary Caught Error]:', error, errorInfo);
    if (window.Sentry && typeof window.Sentry.captureException === 'function') {
      window.Sentry.captureException(error, { extra: errorInfo });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '400px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
        >
          <div
            className="glass-panel"
            style={{
              maxWidth: '520px',
              width: '100%',
              padding: '36px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '16px',
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(244, 63, 94, 0.15)',
                color: 'var(--accent-rose)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <AlertTriangle size={24} />
            </div>

            <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-main)' }}>
              Component Rendering Interrupted
            </h3>

            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
              An unexpected condition occurred. Our automated production crash logger has cataloged
              this incident for root cause analysis.
            </p>

            <div
              style={{
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
                background: 'rgba(0, 0, 0, 0.3)',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-dim)',
              }}
            >
              Incident ID: {this.state.errorId}
            </div>

            <button
              onClick={() => window.location.reload()}
              className="btn btn-primary"
              style={{ marginTop: '8px' }}
            >
              <RefreshCw size={16} />
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
