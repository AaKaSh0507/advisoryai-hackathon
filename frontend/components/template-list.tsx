'use client'

import { useState, useEffect } from 'react'
import { TemplateCard } from './template-card'
import { api, ApiTemplate, ApiSection, ApiJob } from '@/lib/api'

export interface Template {
  id: string
  name: string
  uploadedAt: string
  status: 'pending' | 'analyzing' | 'ready' | 'error'
  sections: number
  staticSections: number
  dynamicSections: number
  version: number
  fileSize: string
}

export function TemplateList() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [selectedSections, setSelectedSections] = useState<ApiSection[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const statusConfig = {
    pending: { label: 'Pending', icon: '⏳', color: 'text-yellow-400' },
    analyzing: { label: 'Analyzing', icon: '🔄', color: 'text-blue-400' },
    ready: { label: 'Ready', icon: '✅', color: 'text-green-400' },
    error: { label: 'Error', icon: '❌', color: 'text-red-400' },
  }

  useEffect(() => {
    loadTemplates()
  }, [])

  useEffect(() => {
    if (selectedTemplate) {
      loadSections(selectedTemplate)
    } else {
      setSelectedSections([])
    }
  }, [selectedTemplate])

  const loadTemplates = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const [apiTemplates, jobs] = await Promise.all([
        api.getTemplates(),
        api.getJobs()
      ])
      
      // Transform API templates to component format
      const transformedTemplates: Template[] = await Promise.all(
        apiTemplates.map(async (t: ApiTemplate) => {
          // Get template versions to determine status
          let status: Template['status'] = 'pending'
          let sections = 0
          let staticSections = 0
          let dynamicSections = 0
          let version = 1

          try {
            const versions = await api.getTemplateVersions(t.id)
            if (versions.length > 0) {
              const latestVersion = versions[versions.length - 1]
              version = latestVersion.version_number

              // Determine status based on parsing status and jobs
              const templateJobs = jobs.filter(
                (j: ApiJob) => j.payload?.template_version_id === latestVersion.id
              )
              
              const hasFailedJob = templateJobs.some((j: ApiJob) => j.status === 'FAILED')
              const hasRunningJob = templateJobs.some((j: ApiJob) => j.status === 'RUNNING')
              const allCompleted = templateJobs.length > 0 && templateJobs.every((j: ApiJob) => j.status === 'COMPLETED')
              
              if (hasFailedJob) {
                status = 'error'
              } else if (hasRunningJob) {
                status = 'analyzing'
              } else if (allCompleted || latestVersion.parsing_status === 'COMPLETED') {
                status = 'ready'
              } else if (latestVersion.parsing_status === 'IN_PROGRESS') {
                status = 'analyzing'
              }

              // Get sections for this version
              try {
                const sectionData = await api.getSectionsByTemplateVersion(latestVersion.id)
                sections = sectionData.length
                staticSections = sectionData.filter((s: ApiSection) => s.section_type === 'STATIC').length
                dynamicSections = sectionData.filter((s: ApiSection) => s.section_type === 'DYNAMIC').length
              } catch {
                // Sections may not exist yet
              }
            }
          } catch {
            // Versions may not exist yet
          }

          return {
            id: t.id,
            name: t.name,
            uploadedAt: new Date(t.created_at).toLocaleDateString('en-US', { 
              month: 'short', 
              day: 'numeric', 
              year: 'numeric' 
            }),
            status,
            sections,
            staticSections,
            dynamicSections,
            version,
            fileSize: '-',
          }
        })
      )

      setTemplates(transformedTemplates)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates')
    } finally {
      setLoading(false)
    }
  }

  const loadSections = async (templateId: string) => {
    try {
      // Find the latest version for this template
      const versions = await api.getTemplateVersions(templateId)
      if (versions.length > 0) {
        const latestVersion = versions[versions.length - 1]
        const sections = await api.getSectionsByTemplateVersion(latestVersion.id)
        setSelectedSections(sections)
      }
    } catch {
      setSelectedSections([])
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <span className="ml-3 text-muted-foreground">Loading templates...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-6 text-center">
        <p className="text-red-400">{error}</p>
        <button
          onClick={loadTemplates}
          className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Retry
        </button>
      </div>
    )
  }

  if (templates.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center">
        <svg className="mx-auto h-12 w-12 text-muted-foreground opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <h3 className="mt-4 text-lg font-semibold">No templates yet</h3>
        <p className="mt-2 text-muted-foreground">Upload a template to get started</p>
      </div>
    )
  }

  const selectedTemplateData = templates.find((t) => t.id === selectedTemplate)

  return (
    <div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => (
          <TemplateCard
            key={template.id}
            template={template}
            isSelected={selectedTemplate === template.id}
            onSelect={setSelectedTemplate}
            statusConfig={statusConfig[template.status]}
          />
        ))}
      </div>

      {selectedTemplate && selectedTemplateData && (
        <div className="mt-6 rounded-lg border border-border bg-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Template Details</h3>
            <button
              onClick={() => setSelectedTemplate(null)}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-sm text-muted-foreground">Sections</label>
                <p className="text-xl font-semibold text-foreground">
                  {selectedTemplateData.sections}
                </p>
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Dynamic Sections</label>
                <p className="text-xl font-semibold text-foreground">
                  {selectedTemplateData.dynamicSections}
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-border">
              <h4 className="font-semibold mb-3">Section Breakdown</h4>
              <div className="space-y-2">
                {selectedSections.length > 0 ? (
                  selectedSections.map((section) => (
                    <div key={section.id} className="flex items-center justify-between rounded-lg bg-muted/30 p-3">
                      <span className="text-sm text-foreground">{section.structural_path}</span>
                      <span className={`text-xs rounded-full px-2 py-1 ${
                        section.section_type === 'DYNAMIC' 
                          ? 'bg-primary/20 text-primary' 
                          : 'bg-muted text-muted-foreground'
                      }`}>
                        {section.section_type}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No sections available</p>
                )}
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <button className="flex-1 rounded-lg border border-border px-4 py-2 font-medium text-foreground hover:bg-muted transition-all">
                Download Template
              </button>
              <button className="flex-1 rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground hover:opacity-90 transition-all">
                Generate Document
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
