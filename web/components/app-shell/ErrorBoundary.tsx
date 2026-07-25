"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="m-6 rounded-xl border border-rose-400 bg-rose-950/30 p-6">
          <p className="font-semibold text-rose-200">Something went wrong.</p>
          <p className="mt-2 text-sm text-rose-100">
            The view failed to render. Try reloading the page; if this keeps happening, the
            story data may be in an unexpected state.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
