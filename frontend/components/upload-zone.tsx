'use client'

import React from "react"

import { useState } from 'react'
import { api } from '@/lib/api'

interface UploadZoneProps {
  onClose: () => void
}

export function UploadZone({ onClose }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleFiles = async (files: FileList) => {
    if (files.length === 0) return
    
    const file = files[0]
    if (!file.name.endsWith('.docx') && !file.name.endsWith('.doc')) {
      setErrorMessage('Please upload a .docx or .doc file')
      setUploadStatus('error')
      return
    }

    setIsUploading(true)
    setUploadStatus('uploading')
    setUploadProgress(10)
    setErrorMessage(null)

    try {
      // Create template first
      const templateName = file.name.replace(/\.(docx|doc)$/i, '')
      setUploadProgress(30)
      
      const template = await api.createTemplate(templateName)
      setUploadProgress(50)
      
      // Upload the file as a new version
      await api.uploadTemplateVersion(template.id, file)
      setUploadProgress(90)
      
      setUploadProgress(100)
      setUploadStatus('success')
      
      setTimeout(() => {
        onClose()
        // Trigger page reload to show new template
        window.location.reload()
      }, 1000)
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : 'Upload failed')
      setUploadStatus('error')
      setIsUploading(false)
    }
  }

  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/30 p-4 sm:p-8 lg:p-12">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`text-center transition-all ${isDragging ? 'bg-muted/50 scale-105' : ''}`}
      >
        {uploadStatus === 'error' && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/50">
            <p className="text-sm text-red-400">{errorMessage}</p>
          </div>
        )}
        
        {!isUploading ? (
          <>
            <div className="flex justify-center mb-4">
              <div className="rounded-full bg-primary/10 p-3 sm:p-4">
                <svg className="h-6 w-6 sm:h-8 sm:w-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
            </div>
            <h3 className="text-base sm:text-lg font-semibold text-foreground">Drop your Word template here</h3>
            <p className="mt-2 text-sm text-muted-foreground">or</p>
            <label className="mt-4 inline-block">
              <span className="text-primary font-medium cursor-pointer hover:underline">browse your computer</span>
              <input type="file" accept=".docx,.doc" className="hidden" onChange={(e) => e.target.files && handleFiles(e.target.files)} />
            </label>
            <p className="mt-4 text-sm text-muted-foreground">Supported formats: .docx, .doc</p>
          </>
        ) : (
          <div className="space-y-4">
            <div className="flex justify-center">
              <div className={`rounded-full p-4 ${uploadStatus === 'success' ? 'bg-green-500/20' : 'bg-primary/20 animate-pulse'}`}>
                <svg className={`h-8 w-8 ${uploadStatus === 'success' ? 'text-green-500' : 'text-primary'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-foreground">
                {uploadStatus === 'success' ? 'Upload complete!' : 'Uploading template...'}
              </h3>
              <div className="mt-4 w-full max-w-xs mx-auto">
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${uploadStatus === 'success' ? 'bg-green-500' : 'bg-gradient-to-r from-primary to-accent'}`}
                    style={{ width: `${Math.min(uploadProgress, 100)}%` }}
                  />
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{Math.min(Math.round(uploadProgress), 100)}%</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {!isUploading && (
        <div className="mt-6 pt-6 border-t border-border flex flex-col-reverse sm:flex-row justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg font-medium text-foreground border border-border hover:bg-muted transition-all w-full sm:w-auto"
          >
            Cancel
          </button>
          <label className="px-4 py-2 rounded-lg font-medium text-primary-foreground bg-primary cursor-pointer hover:opacity-90 transition-all text-center w-full sm:w-auto">
            Select File
            <input type="file" accept=".docx,.doc" className="hidden" onChange={(e) => e.target.files && handleFiles(e.target.files)} />
          </label>
        </div>
      )}
    </div>
  )
}
