/**
 * Error Boundary for SuperAdmin Dashboard
 * Separated into its own file because Vite's React Fast Refresh
 * cannot handle files that mix class and function components.
 */
import React, { Component } from 'react';

export default class AdminErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('SuperAdmin Error:', error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ minHeight: '100vh', background: '#0a0e17', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
          <div style={{ maxWidth: 480, width: '100%', background: '#111827', border: '1px solid rgba(127,29,29,0.4)', borderRadius: 12, padding: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 900, color: '#f87171', marginBottom: 12 }}>Admin Dashboard Error</h2>
            <p style={{ fontSize: 13, color: '#9ca3af', marginBottom: 16 }}>{this.state.error?.message || 'Unknown error'}</p>
            <pre style={{ fontSize: 9, color: '#6b7280', background: 'rgba(0,0,0,0.4)', padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 160, marginBottom: 16, whiteSpace: 'pre-wrap' }}>
              {this.state.errorInfo?.componentStack || 'No stack trace'}
            </pre>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
                style={{ padding: '8px 16px', background: 'rgba(30,58,138,0.3)', color: '#60a5fa', border: '1px solid rgba(30,58,138,0.4)', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
              >Retry</button>
              <button
                onClick={this.props.onBack}
                style={{ padding: '8px 16px', background: '#374151', color: '#9ca3af', border: '1px solid #4b5563', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
              >← Back to Dashboard</button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
