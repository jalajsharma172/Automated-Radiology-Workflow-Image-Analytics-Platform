'use client'

import React, { useState, useEffect, useRef } from 'react'
import { UploadCloud, CheckCircle2, AlertCircle, Loader2, RefreshCw, Folder, Layers, Eye, EyeOff, Activity, ChevronRight, CornerDownRight } from 'lucide-react'

interface Scan {
  id: string
  scan_type: 'CT' | 'PET' | 'SEG'
  status: string
  uploaded_at: string
}

interface Study {
  id: string
  patient_id: string
  study_date: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  status: 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'
  created_at: string
  scans: Scan[]
}

interface Lesion {
  id: number
  volume: number
  max_suv: number
  mean_suv: number
  z_center: number
}

interface Slice {
  z: number
  ct_key: string
  pet_key: string | null
  seg_frame: number | null
}

interface StudyMetadata {
  slices: Slice[]
  lesions: Lesion[]
}

export default function Home() {
  const [studies, setStudies] = useState<Study[]>([])
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const backendUrl = 'http://localhost:8000'

  // Viewport states
  const [selectedStudy, setSelectedStudy] = useState<Study | null>(null)
  const [studyMetadata, setStudyMetadata] = useState<StudyMetadata | null>(null)
  const [currentZ, setCurrentZ] = useState<number>(0)
  const [petOpacity, setPetOpacity] = useState<number>(0.6)
  const [showPet, setShowPet] = useState<boolean>(true)
  const [showSeg, setShowSeg] = useState<boolean>(true)
  const [isLoadingMetadata, setIsLoadingMetadata] = useState<boolean>(false)

  // Fetch all studies
  const fetchStudies = async (quiet = false) => {
    if (!quiet) setIsRefreshing(true)
    try {
      const response = await fetch(`${backendUrl}/studies`)
      if (response.ok) {
        const data = await response.json()
        setStudies(data)
      } else {
        console.error('Failed to fetch studies:', response.statusText)
      }
    } catch (error) {
      console.error('Error fetching studies:', error)
    } finally {
      if (!quiet) setIsRefreshing(false)
    }
  }

  // Load studies on mount
  useEffect(() => {
    fetchStudies()
  }, [])

  // Poll for queued/processing studies
  useEffect(() => {
    const hasActiveStudies = studies.some(s => s.status === 'queued' || s.status === 'processing')
    if (!hasActiveStudies) return

    const interval = setInterval(() => {
      fetchStudies(true)
    }, 2000)

    return () => clearInterval(interval)
  }, [studies])

  // Fetch slices and analytics for viewport
  const fetchStudyMetadata = async (studyId: string) => {
    setIsLoadingMetadata(true)
    setStudyMetadata(null)
    try {
      const response = await fetch(`${backendUrl}/studies/${studyId}/slices`)
      if (response.ok) {
        const data = await response.json()
        setStudyMetadata(data)
        // Set initial Z coordinate to the middle slice
        if (data.slices && data.slices.length > 0) {
          const midIndex = Math.floor(data.slices.length / 2)
          setCurrentZ(data.slices[midIndex].z)
        }
      } else {
        console.error('Failed to fetch alignment metadata')
      }
    } catch (err) {
      console.error('Error fetching study metadata:', err)
    } finally {
      setIsLoadingMetadata(false)
    }
  }

  const handleRowClick = (study: Study) => {
    if (study.status !== 'completed') return
    setSelectedStudy(study)
    fetchStudyMetadata(study.id)
  }

  // File Upload Handlers
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFiles(e.target.files)
      setUploadMessage(null)
    }
  }

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFiles || selectedFiles.length === 0) return

    setIsUploading(true)
    setUploadMessage(null)

    const formData = new FormData()
    // Append folder files with their relative paths so backend can group them
    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i]
      const relativePath = file.webkitRelativePath || file.name
      formData.append('files', file, relativePath)
    }

    try {
      const response = await fetch(`${backendUrl}/studies/upload`, {
        method: 'POST',
        body: formData,
      })

      if (response.ok) {
        const resData = await response.json()
        setUploadMessage({
          type: 'success',
          text: `Study uploaded successfully! ID: ${resData.study_id}. Enqueued in Celery queue.`
        })
        setSelectedFiles(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
        await fetchStudies()
      } else {
        const errData = await response.json()
        setUploadMessage({
          type: 'error',
          text: errData.detail || 'Failed to upload study folder.'
        })
      }
    } catch (error) {
      setUploadMessage({
        type: 'error',
        text: 'Backend connection failed. Verify FastAPI is online.'
      })
    } finally {
      setIsUploading(false)
    }
  }

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'HIGH':
        return <span className="badge badge-failed">High Priority</span>
      case 'MEDIUM':
        return <span className="badge badge-processing">Medium Priority</span>
      case 'LOW':
        return <span className="badge badge-completed">Low Priority</span>
      default:
        return <span className="badge badge-uploaded">{priority}</span>
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'uploaded':
        return <span className="badge badge-uploaded">Uploaded</span>
      case 'queued':
        return <span className="badge badge-queued"><Loader2 style={{ width: '12px', height: '12px' }} className="animate-spin" /> Queued</span>
      case 'processing':
        return <span className="badge badge-processing pulse-yellow"><Loader2 style={{ width: '12px', height: '12px' }} className="animate-spin" /> Processing</span>
      case 'completed':
        return <span className="badge badge-completed"><CheckCircle2 style={{ width: '12px', height: '12px' }} /> Completed</span>
      case 'failed':
        return <span className="badge badge-failed"><AlertCircle style={{ width: '12px', height: '12px' }} /> Failed</span>
      default:
        return <span className="badge badge-uploaded">{status}</span>
    }
  }

  // Find Z slice index in list
  const getZIndex = () => {
    if (!studyMetadata || !studyMetadata.slices) return 0
    const idx = studyMetadata.slices.findIndex(s => s.z === currentZ)
    return idx >= 0 ? idx : 0
  }

  return (
    <main style={{ minHeight: '100vh', padding: '2rem 1.5rem', width: '100%' }}>
      <div style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', marginBottom: '2rem' }}>
        <div className="status-badge">
          <span className="status-dot"></span>
          Siemens-Aligned Radiology Pipeline Active
        </div>
        <h1 style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>MedVision AI Dashboard</h1>
        <p style={{ fontSize: '1.05rem', color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
          Automated Preprocessing, Multi-Modality Overlay Stacking, and Lesion Analytics Viewport
        </p>
      </div>

      <div className="dashboard-container">
        {/* Left Column: Folder Ingest */}
        <div className="upload-card">
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem', color: '#fff' }}>Ingest Patient Study</h2>
          <form onSubmit={handleUploadSubmit}>
            <div
              className="dropzone"
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                style={{ display: 'none' }}
                onChange={handleFileChange}
                multiple
                {...({ webkitdirectory: "", directory: "" } as any)}
              />
              <UploadCloud className="dropzone-icon" />
              <div>
                <p style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: 'var(--foreground)' }}>
                  Click to select study folder
                </p>
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Select folder containing CT/PET/SEG slices
                </p>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', width: '100%', paddingTop: '0.5rem' }}>
                Folder Upload mode (requires DICOMs)
              </div>
            </div>

            {selectedFiles && (
              <div className="file-preview">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <Folder style={{ color: 'var(--primary)', flexShrink: 0 }} />
                  <div>
                    <div className="file-preview-header">
                      {selectedFiles[0]?.webkitRelativePath.split('/')[0] || "Selected Folder"}
                    </div>
                    <div className="file-preview-meta">
                      {selectedFiles.length} files detected inside folder
                    </div>
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
              disabled={!selectedFiles || isUploading}
            >
              {isUploading ? (
                <>
                  <Loader2 className="animate-spin" style={{ width: '18px', height: '18px' }} />
                  <span>Uploading Folder...</span>
                </>
              ) : (
                <span>Upload & Ingest Folder</span>
              )}
            </button>
          </form>
        </div>

        {/* Right Column: Studies Queue */}
        <div className="list-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#fff', margin: 0 }}>Imaging Study Queue</h2>
            <button
              onClick={() => fetchStudies()}
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
              <RefreshCw className={isRefreshing ? 'animate-spin' : ''} style={{ width: '14px', height: '14px' }} />
              <span>Refresh</span>
            </button>
          </div>

          <div className="scans-table-wrapper">
            {studies.length === 0 ? (
              <div className="empty-state">
                <Folder className="w-12 h-12" style={{ margin: '0 auto 1rem auto', opacity: 0.3, width: '48px', height: '48px' }} />
                <p style={{ margin: 0 }}>No studies uploaded yet</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>Upload a folder containing patient DICOMs to begin.</p>
              </div>
            ) : (
              <table className="scans-table">
                <thead>
                  <tr>
                    <th>Patient ID / Study ID</th>
                    <th>Modalities Ingested</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Ingestion Date</th>
                  </tr>
                </thead>
                <tbody>
                  {studies.map((study) => (
                    <tr
                      key={study.id}
                      onClick={() => handleRowClick(study)}
                      className={study.status === 'completed' ? 'clickable-row' : ''}
                      style={{ opacity: study.status === 'failed' ? 0.6 : 1 }}
                      title={study.status === 'completed' ? 'Click to open overlaid viewport' : 'Processing...'}
                    >
                      <td>
                        <div style={{ fontWeight: 600, color: '#fff' }}>Patient ID: {study.patient_id}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>Study ID: {study.id}</div>
                      </td>
                      <td style={{ verticalAlign: 'middle' }}>
                        <div style={{ display: 'flex', gap: '0.25rem' }}>
                          {study.scans.map(s => (
                            <span key={s.id} className="badge badge-uploaded" style={{ fontSize: '0.7rem' }}>
                              {s.scan_type}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td style={{ verticalAlign: 'middle' }}>{getPriorityBadge(study.priority)}</td>
                      <td style={{ verticalAlign: 'middle' }}>{getStatusBadge(study.status)}</td>
                      <td style={{ verticalAlign: 'middle', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(study.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Layered Co-registered Viewport Modal */}
      {selectedStudy && studyMetadata && (
        <div className="modal-overlay" onClick={() => { setSelectedStudy(null); setStudyMetadata(null); }}>
          <div className="modal-container" style={{ maxWidth: '1000px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 600, color: '#fff', margin: 0 }}>
                  Siemens-Aligned Viewport: Co-registered Overlays
                </h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Patient ID: {selectedStudy.patient_id} | Study: {selectedStudy.id}
                </span>
              </div>
              <button className="close-btn" onClick={() => { setSelectedStudy(null); setStudyMetadata(null); }}>
                <svg style={{ width: '20px', height: '20px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="modal-body-two-col">
              {/* Left Column: Viewport Stack and Z Slider */}
              <div className="viewer-left-col">
                <div className="viewer-viewport" style={{ height: '460px' }}>
                  {isLoadingMetadata ? (
                    <div className="viewer-image-fallback">
                      <Loader2 className="animate-spin w-8 h-8" />
                      <span>Syncing Slices...</span>
                    </div>
                  ) : (
                    <div className="viewer-layers-container">
                      {/* Layer 1: CT base scan */}
                      <img
                        className="viewer-layer-img"
                        style={{ zIndex: 10 }}
                        src={`${backendUrl}/studies/${selectedStudy.id}/render?modality=CT&z=${currentZ}`}
                        alt="CT Grid base"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                        }}
                      />

                      {/* Layer 2: Resampled PET heatmap with blend screen */}
                      {showPet && (
                        <img
                          className="viewer-layer-img"
                          style={{ zIndex: 20, opacity: petOpacity, mixBlendMode: 'screen' }}
                          src={`${backendUrl}/studies/${selectedStudy.id}/render?modality=PET&z=${currentZ}`}
                          alt="PET metabolic map"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      )}

                      {/* Layer 3: SEG labels mask overlay */}
                      {showSeg && (
                        <img
                          className="viewer-layer-img"
                          style={{ zIndex: 30, mixBlendMode: 'screen' }}
                          src={`${backendUrl}/studies/${selectedStudy.id}/render?modality=SEG&z=${currentZ}`}
                          alt="SEG tumor labels"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      )}

                      {/* Overlays in corners */}
                      <div className="viewer-info-overlay">
                        Modality: CT + PET + SEG<br />
                        Z Depth: {currentZ.toFixed(1)} mm
                      </div>
                      
                      <div className="viewer-info-overlay-right">
                        Resolution: 512 x 512<br />
                        Slice Thickness: 3.0 mm<br />
                        Aligned Frame: {getZIndex() + 1} / {studyMetadata.slices.length}
                      </div>
                    </div>
                  )}
                </div>

                {/* Slices Slider controls */}
                <div className="viewer-controls">
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#fff' }}>
                    <span style={{ fontWeight: 600 }}>Depth Scrolling (Z axis)</span>
                    <span style={{ color: 'var(--primary)', fontWeight: 600 }}>
                      Slice {getZIndex() + 1} of {studyMetadata.slices.length} ({currentZ.toFixed(1)} mm)
                    </span>
                  </div>
                  <div className="slider-wrapper">
                    <input
                      type="range"
                      min={0}
                      max={studyMetadata.slices.length - 1}
                      value={getZIndex()}
                      onChange={(e) => {
                        const index = parseInt(e.target.value)
                        const targetSlice = studyMetadata.slices[index]
                        if (targetSlice) setCurrentZ(targetSlice.z)
                      }}
                      className="viewer-slider"
                    />
                  </div>
                </div>
              </div>

              {/* Right Column: Layer controls and Lesion Analytics */}
              <div className="viewer-right-col">
                <div className="viewer-controls">
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
                    <Layers style={{ width: '16px', height: '16px', color: 'var(--primary)' }} />
                    <span>Layer Compositor</span>
                  </h4>
                  <div className="control-group">
                    <div className="control-row">
                      <span style={{ color: 'var(--text-muted)' }}>CT Grid Base (Structural)</span>
                      <span className="badge badge-uploaded" style={{ fontSize: '0.7rem' }}>Grayscale</span>
                    </div>

                    <div style={{ borderTop: '1px solid var(--border-color)', margin: '0.25rem 0' }}></div>

                    <div className="control-row">
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={showPet}
                          onChange={(e) => setShowPet(e.target.checked)}
                          style={{ cursor: 'pointer' }}
                        />
                        <span>PET Overlay (Metabolic)</span>
                      </label>
                      <button 
                        onClick={() => setShowPet(!showPet)} 
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                      >
                        {showPet ? <Eye style={{ width: '14px', height: '14px' }} /> : <EyeOff style={{ width: '14px', height: '14px' }} />}
                      </button>
                    </div>
                    {showPet && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', paddingLeft: '1.25rem' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', width: '40px' }}>Opacity</span>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.1}
                          value={petOpacity}
                          onChange={(e) => setPetOpacity(parseFloat(e.target.value))}
                          className="viewer-slider"
                          style={{ height: '4px' }}
                        />
                        <span style={{ fontSize: '0.75rem', color: 'var(--primary)', width: '30px', fontWeight: 600 }}>
                          {Math.round(petOpacity * 100)}%
                        </span>
                      </div>
                    )}

                    <div style={{ borderTop: '1px solid var(--border-color)', margin: '0.25rem 0' }}></div>

                    <div className="control-row">
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={showSeg}
                          onChange={(e) => setShowSeg(e.target.checked)}
                          style={{ cursor: 'pointer' }}
                        />
                        <span>SEG Mask (Lesions)</span>
                      </label>
                      <button 
                        onClick={() => setShowSeg(!showSeg)} 
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                      >
                        {showSeg ? <Eye style={{ width: '14px', height: '14px' }} /> : <EyeOff style={{ width: '14px', height: '14px' }} />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Lesion Analytics Details */}
                <div className="viewer-controls" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#fff', display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0 0 0.5rem 0' }}>
                    <Activity style={{ width: '16px', height: '16px', color: '#fca5a5' }} />
                    <span>Suspicious Lesions ({studyMetadata.lesions.length})</span>
                  </h4>
                  
                  <div className="lesions-container" style={{ flex: 1 }}>
                    {studyMetadata.lesions.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                        No suspicious lesions detected
                      </div>
                    ) : (
                      studyMetadata.lesions.map((lesion) => (
                        <div
                          key={lesion.id}
                          className="lesion-card"
                          onClick={() => setCurrentZ(lesion.z_center)}
                          style={{ cursor: 'pointer', borderLeft: lesion.volume > 2.0 ? '4px solid #ef4444' : '4px solid var(--primary)' }}
                          title="Click to jump Z-slider directly to this lesion center"
                        >
                          <div className="lesion-card-header">
                            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                              Lesion #{lesion.id}
                              {lesion.volume > 2.0 && <span className="priority-high-text" style={{ fontSize: '0.7rem' }}>(Critical)</span>}
                            </span>
                            <span className="priority-high-text" style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
                              SUV max: {lesion.max_suv.toFixed(1)}
                            </span>
                          </div>
                          <div className="lesion-card-body">
                            <div>Volume: <b>{lesion.volume.toFixed(2)} cm³</b></div>
                            <div>Location: <b>{lesion.z_center.toFixed(0)} mm</b></div>
                            <div style={{ gridColumn: 'span 2', display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.25rem', color: 'var(--primary)', fontSize: '0.75rem', fontWeight: 600 }}>
                              <CornerDownRight style={{ width: '12px', height: '12px' }} /> Click to slice jump
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="btn"
                style={{
                  width: 'auto',
                  padding: '0.5rem 1.5rem',
                  backgroundColor: 'rgba(30, 41, 59, 0.8)',
                  color: '#fff',
                  border: '1px solid var(--border-color)',
                }}
                onClick={() => { setSelectedStudy(null); setStudyMetadata(null); }}
              >
                Close Viewport
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}
