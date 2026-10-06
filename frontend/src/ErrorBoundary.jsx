import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Uncaught error in React tree:', error, info);
    this.setState({ info });
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, fontFamily: 'Inter, Arial, sans-serif' }}>
          <h2>Something went wrong</h2>
          <p>DocuMind encountered an unexpected error while rendering. The app will still be usable — try refreshing or opening a different route.</p>
          <details style={{ whiteSpace: 'pre-wrap', marginTop: 12 }}>
            <summary>Show error details</summary>
            <div>{String(this.state.error && this.state.error.toString())}</div>
            <div>{this.state.info?.componentStack}</div>
          </details>
        </div>
      );
    }

    return this.props.children;
  }
}
