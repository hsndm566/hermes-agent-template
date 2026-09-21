import React, { type ErrorInfo, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { error: Error | null }

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Maw3idi dashboard render error', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas p-6" dir="rtl">
        <div className="w-full max-w-lg rounded-xl2 border border-rose-200 bg-surface p-6 shadow-card">
          <h1 className="text-lg font-semibold text-ink-900">تعذر تحميل لوحة موعدي</h1>
          <p className="mt-2 text-sm text-ink-500">
            حدث خطأ في الواجهة. أعد تحميل الصفحة. إذا استمر الخطأ فسيظهر هنا بدلاً من شاشة فارغة.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-lg bg-moss-700 px-4 py-2 text-sm font-semibold text-white"
          >
            إعادة التحميل
          </button>
          <details className="mt-4 text-xs text-ink-400">
            <summary>تفاصيل الخطأ</summary>
            <pre className="mt-2 whitespace-pre-wrap">{this.state.error.message}</pre>
          </details>
        </div>
      </main>
    )
  }
}
