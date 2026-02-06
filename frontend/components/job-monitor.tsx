'use client'

import { useState, useEffect, useCallback } from 'react'
import { api, ApiJob, ApiTemplate } from '@/lib/api'

export interface Job {
  id: string
  type: 'PARSE' | 'CLASSIFY' | 'GENERATE'
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  templateName: string
  progress: number
  startedAt: string
  updatedAt: string
  error?: string
  // For GENERATE jobs, populated from result
  documentId?: string
  versionNumber?: number
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  
  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  return date.toLocaleDateString()
}

export function JobMonitor() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [filteredJobs, setFilteredJobs] = useState<Job[]>([])
  const [selectedFilter, setSelectedFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [downloadingJobId, setDownloadingJobId] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)

  const loadJobs = useCallback(async () => {
    try {
      setError(null)
      
      const [apiJobs, templates] = await Promise.all([
        api.getJobs(),
        api.getTemplates()
      ])
      
      // Create a map of template IDs to names
      const templateMap = new Map<string, string>()
      for (const template of templates) {
        templateMap.set(template.id, template.name)
        // Also try to get version info
        try {
          const versions = await api.getTemplateVersions(template.id)
          for (const version of versions) {
            templateMap.set(version.id, template.name)
          }
        } catch {
          // Ignore version fetch errors
        }
      }
      
      // Transform API jobs to component format
      const transformedJobs: Job[] = apiJobs.map((j: ApiJob) => {
        const templateVersionId = j.payload?.template_version_id as string | undefined
        const templateId = j.payload?.template_id as string | undefined
        
        // Calculate progress based on status
        let progress = 0
        if (j.status === 'COMPLETED') progress = 100
        else if (j.status === 'RUNNING') progress = 50
        else if (j.status === 'FAILED') progress = j.result ? 50 : 20

        // Extract document info from result for completed GENERATE jobs
        const documentId = (j.result?.document_id as string) || (j.payload?.document_id as string)
        const versionNumber = j.result?.version_number as number | undefined
        
        return {
          id: j.id,
          type: j.job_type as Job['type'],
          status: j.status,
          templateName: templateMap.get(templateVersionId || '') || 
                       templateMap.get(templateId || '') || 
                       'Unknown Template',
          progress,
          startedAt: j.started_at ? formatTimeAgo(j.started_at) : formatTimeAgo(j.created_at),
          updatedAt: formatTimeAgo(j.updated_at),
          error: j.error || undefined,
          documentId,
          versionNumber,
        }
      })

      setJobs(transformedJobs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadJobs()
    // Poll for updates every 5 seconds
    const interval = setInterval(loadJobs, 5000)
    return () => clearInterval(interval)
  }, [loadJobs])

  const handleDownload = async (job: Job) => {
    if (!job.documentId || !job.versionNumber) {
      setDownloadError(`Cannot download: missing document information for job ${job.id}`)
      return
    }

    setDownloadingJobId(job.id)
    setDownloadError(null)

    try {
      const blob = await api.downloadDocument(job.documentId, job.versionNumber)
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${job.templateName.replace(/[^a-zA-Z0-9]/g, '_')}_v${job.versionNumber}.docx`
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
      setDownloadingJobId(null)
    }
  }

  useEffect(() => {
    if (selectedFilter === 'all') {
      setFilteredJobs(jobs)
    } else {
      setFilteredJobs(jobs.filter((job) => job.status === selectedFilter))
    }
  }, [selectedFilter, jobs])

  const getStatusConfig = (status: Job['status']) => {
    const configs: Record<Job['status'], { label: string; color: string; bgColor: string }> = {
      PENDING: { label: 'Pending', color: 'text-yellow-400', bgColor: 'bg-yellow-400/20' },
      RUNNING: { label: 'Running', color: 'text-blue-400', bgColor: 'bg-blue-400/20' },
      COMPLETED: { label: 'Completed', color: 'text-green-400', bgColor: 'bg-green-400/20' },
      FAILED: { label: 'Failed', color: 'text-red-400', bgColor: 'bg-red-400/20' },
    }
    return configs[status]
  }

  const filters = ['all', 'RUNNING', 'COMPLETED', 'FAILED', 'PENDING']

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <span className="ml-3 text-muted-foreground">Loading jobs...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-6 text-center">
        <p className="text-red-400">{error}</p>
        <button
          onClick={loadJobs}
          className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
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
      <div className="flex gap-2 overflow-x-auto pb-2">
        {filters.map((filter) => (
          <button
            key={filter}
            onClick={() => setSelectedFilter(filter)}
            className={`px-4 py-2 rounded-lg font-medium whitespace-nowrap transition-all ${
              selectedFilter === filter
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-card text-foreground hover:bg-muted'
            }`}
          >
            {filter === 'all' ? 'All Jobs' : filter}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filteredJobs.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-8 text-center">
            <svg className="mx-auto h-12 w-12 text-muted-foreground opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            <h3 className="mt-4 text-lg font-semibold">No jobs found</h3>
            <p className="mt-2 text-muted-foreground">Upload a template to start a processing job</p>
          </div>
        ) : (
          filteredJobs.map((job) => {
            const statusConfig = getStatusConfig(job.status)
            return (
              <div key={job.id} className="rounded-lg border border-border bg-card p-4 hover:border-primary/50 transition-all">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-foreground truncate">{job.templateName}</h3>
                      <span className={`text-xs font-medium px-2 py-1 rounded flex-shrink-0 ${statusConfig.bgColor} ${statusConfig.color}`}>
                        {job.type}
                      </span>
                    </div>
                    <p className="text-xs sm:text-sm text-muted-foreground mt-1 truncate">Job ID: {job.id}</p>
                  </div>
                  <div className={`px-3 py-1 rounded-lg font-medium text-sm flex-shrink-0 self-start ${statusConfig.bgColor} ${statusConfig.color}`}>
                    {statusConfig.label}
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Progress</span>
                    <span className="font-medium text-foreground">{Math.round(job.progress)}%</span>
                  </div>
                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        job.status === 'COMPLETED'
                          ? 'bg-green-500'
                          : job.status === 'FAILED'
                            ? 'bg-red-500'
                            : 'bg-gradient-to-r from-primary to-accent'
                      }`}
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Started {job.startedAt}</span>
                  <span>Updated {job.updatedAt}</span>
                </div>

                {job.error && (
                  <div className="mt-3 rounded-lg bg-red-400/20 border border-red-400/50 p-2">
                    <p className="text-xs text-red-300">{job.error}</p>
                  </div>
                )}

                {/* View Details button for all jobs */}
                <div className="mt-3 flex flex-col sm:flex-row gap-2">
                  <button 
                    onClick={() => setSelectedJobId(selectedJobId === job.id ? null : job.id)}
                    className="flex-1 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-all"
                  >
                    {selectedJobId === job.id ? 'Hide Details' : 'View Details'}
                  </button>
                  {job.status === 'COMPLETED' && job.type === 'GENERATE' && job.documentId && job.versionNumber ? (
                      <button
                        onClick={() => handleDownload(job)}
                        disabled={downloadingJobId === job.id}
                        className="flex-1 rounded-lg bg-primary/20 text-primary px-3 py-2 text-sm font-medium hover:bg-primary/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {downloadingJobId === job.id ? 'Downloading...' : 'Download Output'}
                      </button>
                    ) : job.status === 'COMPLETED' && job.type === 'GENERATE' ? (
                      <button
                        disabled
                        className="flex-1 rounded-lg bg-muted text-muted-foreground px-3 py-2 text-sm font-medium cursor-not-allowed"
                        title="Document not available"
                      >
                        Download Output
                      </button>
                    ) : null}
                </div>

                {/* Job Details Panel */}
                {selectedJobId === job.id && (
                  <div className="mt-4 rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-4">
                    <div className="flex items-start justify-between gap-4">
                      <h4 className="font-semibold text-foreground">Job Details</h4>
                      <button
                        onClick={() => setSelectedJobId(null)}
                        className="text-muted-foreground hover:text-foreground transition-colors p-1"
                      >
                        ✕
                      </button>
                    </div>

                    <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
                      <div>
                        <label className="text-xs text-muted-foreground">Job ID</label>
                        <p className="text-sm font-mono text-foreground break-all">{job.id}</p>
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Job Type</label>
                        <p className="text-sm font-medium text-foreground">{job.type}</p>
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Template</label>
                        <p className="text-sm font-medium text-foreground">{job.templateName}</p>
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Status</label>
                        <p className={`text-sm font-medium ${getStatusConfig(job.status).color}`}>
                          {getStatusConfig(job.status).label}
                        </p>
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Started</label>
                        <p className="text-sm text-foreground">{job.startedAt}</p>
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground">Last Updated</label>
                        <p className="text-sm text-foreground">{job.updatedAt}</p>
                      </div>
                      {job.documentId && (
                        <div>
                          <label className="text-xs text-muted-foreground">Document ID</label>
                          <p className="text-sm font-mono text-foreground break-all">{job.documentId}</p>
                        </div>
                      )}
                      {job.versionNumber && (
                        <div>
                          <label className="text-xs text-muted-foreground">Version</label>
                          <p className="text-sm font-medium text-foreground">v{job.versionNumber}</p>
                        </div>
                      )}
                    </div>

                    {job.error && (
                      <div className="rounded-lg bg-red-400/20 border border-red-400/50 p-3">
                        <label className="text-xs text-red-300 font-medium">Error Message</label>
                        <p className="text-sm text-red-300 mt-1">{job.error}</p>
                      </div>
                    )}

                    <div className="pt-3 border-t border-border/50">
                      <div className="flex items-center justify-between text-sm mb-2">
                        <span className="text-muted-foreground">Progress</span>
                        <span className="font-medium text-foreground">{Math.round(job.progress)}%</span>
                      </div>
                      <div className="h-3 w-full bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-300 ${
                            job.status === 'COMPLETED'
                              ? 'bg-green-500'
                              : job.status === 'FAILED'
                                ? 'bg-red-500'
                                : 'bg-gradient-to-r from-primary to-accent'
                          }`}
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {jobs.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="font-semibold mb-3">Job Statistics</h3>
          <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Total Jobs</p>
              <p className="text-2xl font-bold text-foreground">{jobs.length}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Completed</p>
              <p className="text-2xl font-bold text-green-400">{jobs.filter((j) => j.status === 'COMPLETED').length}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Running</p>
              <p className="text-2xl font-bold text-blue-400">{jobs.filter((j) => j.status === 'RUNNING').length}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Failed</p>
              <p className="text-2xl font-bold text-red-400">{jobs.filter((j) => j.status === 'FAILED').length}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
