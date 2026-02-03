export function DashboardHeader() {
  return (
    <header className="border-b border-border bg-card">
      <div className="flex items-center justify-between px-6 py-4 lg:px-8">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Template Intelligence Engine</h2>
          <p className="text-sm text-muted-foreground">Automated Word template processing with AI</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 rounded-lg border border-border px-3 py-2">
            <svg className="h-4 w-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search templates..."
              className="bg-transparent text-sm focus:outline-none placeholder-muted-foreground w-32"
            />
          </div>
          <button className="rounded-lg p-2 hover:bg-muted">
            <svg className="h-5 w-5 text-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0120 15.571V11a6 6 0 00-5-5.917V5a2 2 0 10-4 0v.083A6 6 0 004 11v4.571a2.032 2.032 0 01-.595 1.424L2 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
          </button>
          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary to-accent" />
        </div>
      </div>
    </header>
  )
}
