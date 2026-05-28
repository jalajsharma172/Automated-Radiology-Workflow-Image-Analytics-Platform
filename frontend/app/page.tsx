'use client'

import React, { useState, useEffect, useRef } from 'react'
import { UploadCloud, CheckCircle2, AlertCircle, Loader2, RefreshCw, FileCode, Clock, ExternalLink } from 'lucide-react'

interface Scan {
  id: string
  original_filename: string
  file_size: number
  mime_type: string
  status: 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'
  uploaded_at: string
  file_url: string
}

export default function Home() {
  const [scans, setScans] = useState<Scan[]>([])
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragActive, setIsDragActive] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const backendUrl = 'http://localhost:8000'

  // Fetch scans list
  const fetchScans = async (quiet = false) => {
    if (!quiet) setIsRefreshing(true)
    try {
      const response = await fetch(`${backendUrl}/scans`)
      if (response.ok) {
        const data = await response.json()
        setScans(data)
      } else {
        console.error('Failed to fetch scans:', response.statusText)
      }
    } catch (error) {
      console.error('Error fetching scans:', error)
    } finally {
      if (!quiet) setIsRefreshing(false)
    }
  }

  // Load scans on initial mount
  useEffect(() => {
    fetchScans()
  }, [])

  // Poll scans list if any scan is queued or processing
  useEffect(() => {
    const hasActiveScans = scans.some(scan => scan.status === 'queued' || scan.status === 'processing')
    if (!hasActiveScans) return

    const interval = setInterval(() => {
      fetchScans(true)
    }, 2000)

    return () => clearInterval(interval)
  }, [scans])

  // Drag and Drop handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragActive(true)
    } else if (e.type === 'dragleave') {
      setIsDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const validateAndSetFile = (file: File) => {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
    const allowed = ['.dcm', '.png', '.jpg', '.jpeg']
    if (!allowed.includes(ext)) {
      setUploadMessage({
        type: 'error',
        text: `Unsupported extension. Please upload: ${allowed.join(', ')}`
      })
      setSelectedFile(null)
      return
    }
    setSelectedFile(file)
    setUploadMessage(null)
  }

  // Form submit handler
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) return

    setIsUploading(true)
    setUploadMessage(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${backendUrl}/scans/upload`, {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        setUploadMessage({
          type: 'success',
          text: 'Scan uploaded successfully! Enqueued in celery worker.'
        })
        setSelectedFile(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
        await fetchScans()
      } else {
        const errData = await response.json()
        setUploadMessage({
          type: 'error',
          text: errData.detail || 'Failed to upload scan.'
        })
      }
    } catch (error) {
      setUploadMessage({
        type: 'error',
        text: 'Connection to backend failed. Make sure API service is running.'
      })
    } finally {
      setIsUploading(false)
    }
  }

  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const dm = decimals < 0 ? 0 : decimals
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'uploaded':
        return <span className="badge badge-uploaded"><Clock style={{ width: '14px', height: '14px' }} /> Uploaded</span>
      case 'queued':
        return <span className="badge badge-queued"><Loader2 style={{ width: '14px', height: '14px' }} className="animate-spin" /> Queued</span>
      case 'processing':
        return <span className="badge badge-processing pulse-yellow"><Loader2 style={{ width: '14px', height: '14px' }} className="animate-spin" /> Processing</span>
      case 'completed':
        return <span className="badge badge-completed"><CheckCircle2 style={{ width: '14px', height: '14px' }} /> Completed</span>
      case 'failed':
        return <span className="badge badge-failed"><AlertCircle style={{ width: '14px', height: '14px' }} /> Failed</span>
      default:
        return <span className="badge badge-uploaded">{status}</span>
    }
  }

  return (
    <main style={{ minHeight: '100vh', padding: '2rem 1.5rem', width: '100%' }}>
      <div style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', marginBottom: '2rem' }}>
        <div className="status-badge">
          <span className="status-dot"></span>
          Pipeline Environment Active
        </div>
        <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>MedVision AI</h1>
        <p style={{ fontSize: '1.05rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
          Asynchronous Ingestion and Distributed Inference Pipeline Dashboard
        </p>
      </div>

      <div className="dashboard-container">
        {/* Left Column: Upload controls */}
        <div className="upload-card">
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem', color: '#fff' }}>Ingest Medical Scan</h2>
          <form onSubmit={handleUploadSubmit}>
            <div
              className={`dropzone ${isDragActive ? 'drag-active' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                style={{ display: 'none' }}
                onChange={handleFileChange}
                accept=".dcm,.png,.jpg,.jpeg"
              />
              <UploadCloud className="dropzone-icon" />
              <div>
                <p style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: 'var(--foreground)' }}>
                  Drag & Drop file here
                </p>
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  or click to select scan
                </p>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', width: '100%', paddingTop: '0.5rem' }}>
                Supports DICOM (.dcm), PNG, JPG, JPEG
              </div>
            </div>

            {selectedFile && (
              <div className="file-preview">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <FileCode style={{ color: 'var(--primary)', flexShrink: 0 }} />
                  <div>
                    <div className="file-preview-header">{selectedFile.name}</div>
                    <div className="file-preview-meta">{formatBytes(selectedFile.size)}</div>
                  </div>
                </div>
              </div>
            )}

            {uploadMessage && (
              <div style={{
                marginTop: '1rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                fontSize: '0.85rem',
                backgroundColor: uploadMessage.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${uploadMessage.type === 'success' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
                color: uploadMessage.type === 'success' ? '#6ee7b7' : '#fca5a5',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem'
              }}>
                {uploadMessage.type === 'success' ? <CheckCircle2 style={{ flexShrink: 0, marginTop: '2px', width: '16px', height: '16px' }} /> : <AlertCircle style={{ flexShrink: 0, marginTop: '2px', width: '16px', height: '16px' }} />}
                <span>{uploadMessage.text}</span>
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary"
              style={{ marginTop: '1.5rem' }}
              disabled={!selectedFile || isUploading}
            >
              {isUploading ? (
                <>
                  <Loader2 className="animate-spin w-4.5 h-4.5" />
                  <span>Uploading Scan...</span>
                </>
              ) : (
                <span>Upload & Ingest Scan</span>
              )}
            </button>
          </form>
        </div>

        {/* Right Column: Scan History List */}
        <div className="list-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#fff', margin: 0 }}>Recent Scan Logs</h2>
            <button
              onClick={() => fetchScans()}
              className="btn"
              style={{
                width: 'auto',
                padding: '0.4rem 0.8rem',
                backgroundColor: 'rgba(30, 41, 59, 0.8)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-color)',
                fontSize: '0.8rem',
              }}
              disabled={isRefreshing}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>

          <div className="scans-table-wrapper">
            {scans.length === 0 ? (
              <div className="empty-state">
                <UploadCloud className="w-12 h-12" style={{ margin: '0 auto 1rem auto', opacity: 0.3 }} />
                <p style={{ margin: 0 }}>No scan logs recorded yet</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>Use the form on the left to ingest DICOM/images</p>
              </div>
            ) : (
              <table className="scans-table">
                <thead>
                  <tr>
                    <th>Scan Details</th>
                    <th>File Size</th>
                    <th>Status</th>
                    <th>Timestamp</th>
                    <th>Storage</th>
                  </tr>
                </thead>
                <tbody>
                  {scans.map((scan) => (
                    <tr key={scan.id}>
                      <td>
                        <div style={{ fontWeight: 600, color: '#fff' }}>{scan.original_filename}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>ID: {scan.id}</div>
                      </td>
                      <td style={{ verticalAlign: 'middle' }}>{formatBytes(scan.file_size)}</td>
                      <td style={{ verticalAlign: 'middle' }}>{getStatusBadge(scan.status)}</td>
                      <td style={{ verticalAlign: 'middle', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(scan.uploaded_at).toLocaleString()}
                      </td>
                      <td style={{ verticalAlign: 'middle' }}>
                        <a
                          href={scan.file_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            color: 'var(--primary)',
                            textDecoration: 'none',
                            fontSize: '0.8rem',
                            fontWeight: 600
                          }}
                        >
                          MinIO Link <ExternalLink style={{ width: '12px', height: '12px' }} />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
