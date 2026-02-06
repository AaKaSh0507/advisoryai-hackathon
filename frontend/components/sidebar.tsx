'use client';

import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
  isOpen?: boolean
  onClose?: () => void
}

export function Sidebar({ activeTab, onTabChange, isOpen = false, onClose }: SidebarProps) {
  const [templateCount, setTemplateCount] = useState<number | null>(null)
  const [pendingJobsCount, setPendingJobsCount] = useState<number | null>(null)

  const loadStats = useCallback(async () => {
    try {
      const [templates, jobs] = await Promise.all([
        api.getTemplates(),
        api.getJobs()
      ])
      setTemplateCount(templates.length)
      setPendingJobsCount(jobs.filter(j => j.status === 'PENDING' || j.status === 'RUNNING').length)
    } catch {
      // Silently fail - stats are not critical
    }
  }, [])

  useEffect(() => {
    loadStats()
    // Refresh stats every 10 seconds
    const interval = setInterval(loadStats, 10000)
    return () => clearInterval(interval)
  }, [loadStats])

  const tabs = [
    { id: 'templates', label: 'Templates', icon: '📋' },
    { id: 'jobs', label: 'Jobs', icon: '⚙️' },
    { id: 'documents', label: 'Documents', icon: '📄' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ]

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden" 
          onClick={onClose}
        />
      )}
      
      <aside className={`
        fixed md:static inset-y-0 left-0 z-50
        w-64 border-r border-border bg-sidebar flex flex-col
        transform transition-transform duration-200 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
      `}>
      <div className="p-6 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
            <span className="text-lg font-bold text-primary-foreground">T</span>
          </div>
          <div>
            <h1 className="font-bold text-sidebar-foreground">Template Engine</h1>
            <p className="text-xs text-sidebar-foreground/60">AdvisoryAI</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`w-full text-left px-4 py-3 rounded-lg font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-sidebar-primary/20 text-primary'
                : 'text-sidebar-foreground hover:bg-sidebar-accent'
            }`}
          >
            <span className="mr-3">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-4 space-y-2">
        <div className="rounded-lg bg-sidebar-accent/20 p-4">
          <p className="text-xs font-semibold text-sidebar-foreground/80 uppercase">Quick Stats</p>
          <div className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-sidebar-foreground/60">Active Templates</span>
              <span className="font-semibold text-sidebar-foreground">
                {templateCount !== null ? templateCount : '...'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sidebar-foreground/60">Pending Jobs</span>
              <span className="font-semibold text-sidebar-foreground">
                {pendingJobsCount !== null ? pendingJobsCount : '...'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
    </>
  )
}
