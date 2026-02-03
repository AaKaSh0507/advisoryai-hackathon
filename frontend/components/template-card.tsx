'use client'

import type { Template } from './template-list'

interface TemplateCardProps {
  template: Template
  isSelected: boolean
  onSelect: (id: string) => void
  statusConfig: {
    label: string
    icon: string
    color: string
  }
}

export function TemplateCard({ template, isSelected, onSelect, statusConfig }: TemplateCardProps) {
  return (
    <button
      onClick={() => onSelect(isSelected ? '' : template.id)}
      className={`rounded-lg border-2 p-4 text-left transition-all ${
        isSelected ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50 bg-card hover:bg-card/80'
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-semibold text-foreground line-clamp-1">{template.name}</h3>
          <p className="text-xs text-muted-foreground mt-1">v{template.version}</p>
        </div>
        <span className={`text-lg ${statusConfig.color}`}>{statusConfig.icon}</span>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Status</span>
          <span className="font-medium text-foreground">{statusConfig.label}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Sections</span>
          <span className="font-medium text-foreground">{template.sections}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Dynamic</span>
          <span className="font-medium text-foreground">{template.dynamicSections}</span>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-border/50">
        <p className="text-xs text-muted-foreground">Uploaded {template.uploadedAt}</p>
      </div>

      {isSelected && (
        <div className="mt-4 pt-4 border-t border-primary/20">
          <div className="flex gap-2">
            <button className="flex-1 rounded px-2 py-1.5 text-xs font-medium bg-primary/20 text-primary hover:bg-primary/30 transition-all">
              Edit
            </button>
            <button className="flex-1 rounded px-2 py-1.5 text-xs font-medium bg-muted text-foreground hover:bg-muted/80 transition-all">
              Generate
            </button>
          </div>
        </div>
      )}
    </button>
  )
}
