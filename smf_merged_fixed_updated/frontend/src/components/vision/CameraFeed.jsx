import React, { useRef, useState, useEffect } from 'react';
import { Shield, Eye } from 'lucide-react';

export default function CameraFeed() {
  const videoRef = useRef(null);
  const [streamActive, setStreamActive] = useState(false);

  useEffect(() => {
    let currentStream = null;

    async function initCamera() {
      try {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' },
          });
          currentStream = stream;
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
            setStreamActive(true);
          }
        }
      } catch (err) {
        console.warn('WebRTC camera not accessible directly; fallback to server stream:', err);
      }
    }

    initCamera();

    return () => {
      if (currentStream) {
        currentStream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  return (
    <div
      className="animate-fade-in"
      style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2
            style={{
              fontSize: '1.25rem',
              fontWeight: 800,
              color: 'var(--text-main)',
              letterSpacing: '-0.02em',
            }}
          >
            Live Face Recognition Camera Feed
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Real-time biometric attendance capture with ArcFace 512D + FAISS vector search
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span className="badge badge-present">
            <Shield size={12} /> Liveness Active
          </span>
          <span className="badge badge-od">
            <Eye size={12} /> ArcFace 512D
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
        {/* Camera Surface */}
        <div
          className="glass-panel"
          style={{
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <div
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '640px',
              aspectRatio: '4/3',
              background: '#000000',
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
              border: '2px solid var(--border-subtle)',
              boxShadow: '0 0 30px rgba(0,0,0,0.6)',
            }}
          >
            {streamActive ? (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <img
                src="/video_feed"
                alt="Live Camera Feed"
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            )}

            {/* Bounding Box HUD Overlay */}
            <div
              style={{
                position: 'absolute',
                top: '25%',
                left: '30%',
                width: '40%',
                height: '50%',
                border: '2px dashed var(--accent-cyan)',
                borderRadius: 'var(--radius-sm)',
                boxShadow: '0 0 15px rgba(6, 182, 212, 0.4)',
                pointerEvents: 'none',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                padding: '6px',
              }}
            >
              <span
                style={{
                  fontSize: '0.7rem',
                  color: 'var(--accent-cyan)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                TRACKING: FACE_01
              </span>
              <span
                style={{
                  fontSize: '0.7rem',
                  color: 'var(--accent-emerald)',
                  fontFamily: 'var(--font-mono)',
                  textAlign: 'right',
                }}
              >
                MATCH: 99.4%
              </span>
            </div>
          </div>
        </div>

        {/* Live Matching Log */}
        <div
          className="glass-panel"
          style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}
        >
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Real-Time Detections
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                borderRadius: 'var(--radius-md)',
                padding: '12px',
              }}
            >
              <div
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.875rem' }}>
                  John Doe
                </span>
                <span
                  style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 600 }}
                >
                  Verified
                </span>
              </div>
              <div
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-dim)',
                  marginTop: '4px',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                91762114001 • CSE III-A • 09:02:14 AM
              </div>
            </div>

            <div
              style={{
                background: 'rgba(6, 182, 212, 0.1)',
                border: '1px solid rgba(6, 182, 212, 0.25)',
                borderRadius: 'var(--radius-md)',
                padding: '12px',
              }}
            >
              <div
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <span style={{ fontWeight: 600, color: 'var(--text-main)', fontSize: '0.875rem' }}>
                  Jane Smith
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                  Verified
                </span>
              </div>
              <div
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-dim)',
                  marginTop: '4px',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                91762114002 • CSE III-A • 09:02:18 AM
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
