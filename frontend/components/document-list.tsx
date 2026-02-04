'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, ApiDocument, ApiDocumentVersion } from '@/lib/api'

interface DocumentWithDetails {
  id: string
  templateName: string
  templateVersionNumber: number
  currentVersion: number
  createdAt: string
  versions: ApiDocumentVersion[]
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function DocumentList() {
  const [documents, setDocuments] = useState<DocumentWithDetails[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null)
  const [downloadingVersion, setDownloadingVersion] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const loadDocuments = useCallback(async () => {
    try {
      setError(null)
      
      const [apiDocs, templates] = await Promise.all([
        api.getDocuments(),
        api.getTemplates()
      ])
      
      // Build a map of template versions to template names
      const templateVersionMap = new Map<string, { name: string; versionNumber: number }>()
      
      for (const template of templates) {
        try {
          const versions = await api.getTemplateVersions(template.id)
          for (const version of versions) {
            templateVersionMap.set(version.id, {
              name: template.name,
              versionNumber: version.version_number
            })
          }
        } catch {
          // Ignore version fetch errors
        }
      }
      
      // Transform documents with details
      const docsWithDetails: DocumentWithDetails[] = await Promise.all(
        apiDocs.map(async (doc: ApiDocument) => {
          const templateInfo = templateVersionMap.get(doc.template_version_id)
          
          // Fetch versions for this document
          let versions: ApiDocumentVersion[] = []
          try {
            versions = await api.getDocumentVersions(doc.id)
          } catch {
            // Versions may not exist yet
          }
          
          return {
            id: doc.id,
            templateName: templateInfo?.name || 'Unknown Template',
            templateVersionNumber: templateInfo?.versionNumber || 1,
            currentVersion: doc.current_version,
            createdAt: formatDate(doc.created_at),
            versions,
          }
        })
      )

      setDocuments(docsWithDetails)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDocuments()
    // Poll for updates every 10 seconds
    const interval = setInterval(loadDocuments, 10000)
    return () => clearInterval(interval)
  }, [loadDocuments])

  const handleDownload = async (documentId: string, version: number, templateName: string) => {
    const versionKey = `${documentId}-${version}`
    setDownloadingVersion(versionKey)
    setDownloadError(null)

    try {
      const blob = await api.downloadDocument(documentId, version)
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${templateName.replace(/[^a-zA-Z0-9]/g, '_')}_v${version}.docx`
      document.body.appendChild(link)
      link.click()
      
      // Cleanup
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Download failed'
      setDownloadError(`Failed to download: ${errorMessage}`)
      console.error('Download error:', err)
    } finally {
      setDownloadingVersion(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <span className="ml-3 text-muted-foreground">Loading documents...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-6 text-center">
        <p className="text-red-400">{error}</p>
        <button
          onClick={loadDocuments}
          className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Retry
        </button>
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-6 sm:p-8 text-center">
        <svg className="mx-auto h-12 w-12 text-muted-foreground opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <h3 className="mt-4 text-lg font-semibold">No documents yet</h3>
        <p className="mt-2 text-muted-foreground">Generated documents will appear here once you run a document generation job</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {downloadError && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 flex items-center justify-between">
          <p className="text-sm text-red-400">{downloadError}</p>
          <button
            onClick={() => setDownloadError(null)}
            className="text-red-400 hover:text-red-300 ml-4"
          >
            ✕
          </button>
        </div>
      )}

      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="rounded-lg border border-border bg-card p-4 hover:border-primary/50 transition-all"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-foreground truncate">{doc.templateName}</h3>
                <p className="text-xs text-muted-foreground mt-1">
                  Template v{doc.templateVersionNumber}
                </p>
              </div>
              <span className="text-xs font-medium px-2 py-1 rounded bg-green-400/20 text-green-400 flex-shrink-0">
                v{doc.currentVersion}
              </span>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Document ID</span>
                <span className="font-mono text-xs text-foreground truncate max-w-[150px]" title={doc.id}>
                  {doc.id.slice(0, 8)}...
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Versions</span>
                <span className="font-medium text-foreground">{doc.versions.length}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Created</span>
                <span className="text-foreground text-xs">{doc.createdAt}</span>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-border/50 space-y-2">
              <button
                onClick={() => setExpandedDocId(expandedDocId === doc.id ? null : doc.id)}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-all"
              >
                {expandedDocId === doc.id ? 'Hide Versions' : 'Show All Versions'}
              </button>
              
              {doc.currentVersion > 0 && (
                <button
                  onClick={() => handleDownload(doc.id, doc.currentVersion, doc.templateName)}
                  disabled={downloadingVersion === `${doc.id}-${doc.currentVersion}`}
                  className="w-full rounded-lg bg-primary/20 text-primary px-3 py-2 text-sm font-medium hover:bg-primary/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {downloadingVersion === `${doc.id}-${doc.currentVersion}` 
                    ? 'Downloading...' 
                    : `Download Latest (v${doc.currentVersion})`}
                </button>
              )}
            </div>

            {/* Expanded versions list */}
            {expandedDocId === doc.id && doc.versions.length > 0 && (
              <div className="mt-4 pt-4 border-t border-primary/30 space-y-2">
                <h4 className="text-sm font-medium text-foreground mb-2">All Versions</h4>
                {doc.versions.map((version) => (
                  <div
                    key={version.id}
                    className="flex items-center justify-between rounded-lg bg-muted/30 p-2"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-foreground">
                        Version {version.version_number}
                      </span>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(version.created_at)}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDownload(doc.id, version.version_number, doc.templateName)}
                      disabled={downloadingVersion === `${doc.id}-${version.version_number}`}
                      className="rounded px-2 py-1 text-xs font-medium bg-primary/20 text-primary hover:bg-primary/30 transition-all disabled:opacity-50"
                    >
                      {downloadingVersion === `${doc.id}-${version.version_number}` 
                        ? '...' 
                        : 'Download'}
                    </button>
                  </div>
                ))}
              </div>
            )}

            {expandedDocId === doc.id && doc.versions.length === 0 && (
              <div className="mt-4 pt-4 border-t border-primary/30">
                <p className="text-sm text-muted-foreground text-center">
                  No versions available yet. Document generation may still be in progress.
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Summary stats */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold mb-3">Document Statistics</h3>
        <div className="grid gap-4 grid-cols-2 md:grid-cols-3">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Total Documents</p>
            <p className="text-2xl font-bold text-foreground">{documents.length}</p>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Total Versions</p>
            <p className="text-2xl font-bold text-foreground">
              {documents.reduce((acc, doc) => acc + doc.versions.length, 0)}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">Ready to Download</p>
            <p className="text-2xl font-bold text-green-400">
              {documents.filter(d => d.currentVersion > 0).length}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
