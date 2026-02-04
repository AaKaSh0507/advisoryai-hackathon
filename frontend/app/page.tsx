'use client'

import { useState } from 'react'
import { Sidebar } from '@/components/sidebar'
import { UploadZone } from '@/components/upload-zone'
import { TemplateList } from '@/components/template-list'
import { DashboardHeader } from '@/components/dashboard-header'
import { JobMonitor } from '@/components/job-monitor'
import { DocumentList } from '@/components/document-list'

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('templates')
  const [showUpload, setShowUpload] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-background text-foreground overflow-x-hidden">
      <div className="flex relative">
        <Sidebar 
          activeTab={activeTab} 
          onTabChange={(tab) => {
            setActiveTab(tab)
            setSidebarOpen(false)
          }} 
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        
        <main className="flex-1 min-w-0 w-full">
          <DashboardHeader onMenuClick={() => setSidebarOpen(true)} />
          
          <div className="p-4 sm:p-6 lg:p-8">
            {activeTab === 'templates' && (
              <div className="space-y-4 sm:space-y-6">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold text-balance">Templates</h1>
                  <p className="mt-2 text-muted-foreground">Upload and manage Word document templates for AI-driven generation</p>
                </div>

                {showUpload ? (
                  <UploadZone onClose={() => setShowUpload(false)} />
                ) : (
                  <div className="flex justify-end">
                    <button
                      onClick={() => setShowUpload(true)}
                      className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground transition-all hover:opacity-90 active:scale-95"
                    >
                      <svg className="mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      Upload Template
                    </button>
                  </div>
                )}

                <TemplateList />
              </div>
            )}

            {activeTab === 'jobs' && (
              <div className="space-y-4 sm:space-y-6">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold text-balance">Processing Jobs</h1>
                  <p className="mt-2 text-sm sm:text-base text-muted-foreground">Monitor template parsing, classification, and document generation</p>
                </div>
                <JobMonitor />
              </div>
            )}

            {activeTab === 'documents' && (
              <div className="space-y-4 sm:space-y-6">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold text-balance">Generated Documents</h1>
                  <p className="mt-2 text-sm sm:text-base text-muted-foreground">View and download completed documents with all sections filled</p>
                </div>
                <DocumentList />
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="space-y-4 sm:space-y-6">
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold text-balance">Settings</h1>
                  <p className="mt-2 text-sm sm:text-base text-muted-foreground">Configure system preferences and integration settings</p>
                </div>
                <div className="rounded-lg border border-border bg-card p-6">
                  <h2 className="text-lg font-semibold mb-4">API Configuration</h2>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-1">API Endpoint</label>
                      <input
                        type="text"
                        placeholder="http://localhost:8000"
                        className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">S3 Bucket</label>
                      <input
                        type="text"
                        placeholder="s3://my-bucket"
                        className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                    </div>
                    <button className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground transition-all hover:opacity-90">
                      Save Settings
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
