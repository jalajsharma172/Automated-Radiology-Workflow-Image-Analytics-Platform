import React from 'react'

export default function Home() {
  return (
    <main>
      <div className="card">
        <div className="status-badge">
          <span className="status-dot"></span>
          Frontend Online
        </div>
        <h1>MedVision AI</h1>
        <p>
          Welcome to the MedVision AI Platform. The environment is successfully
          orchestrated via Docker, and communication with the backend APIs is configured.
        </p>
      </div>
    </main>
  )
}
