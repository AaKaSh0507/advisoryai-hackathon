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
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-foreground">{job.templateName}</h3>
                      <span className={`text-xs font-medium px-2 py-1 rounded ${statusConfig.bgColor} ${statusConfig.color}`}>
                        {job.type}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">Job ID: {job.id}</p>
                  </div>
                  <div className={`px-3 py-1 rounded-lg font-medium text-sm ${statusConfig.bgColor} ${statusConfig.color}`}>
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

                {job.status === 'COMPLETED' && (
                  <div className="mt-3 flex gap-2">
                    <button className="flex-1 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-all">
                      View Details
                    </button>
                    <button className="flex-1 rounded-lg bg-primary/20 text-primary px-3 py-2 text-sm font-medium hover:bg-primary/30 transition-all">
                      Download Output
                    </button>
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
          <div className="grid gap-4 md:grid-cols-4">
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
