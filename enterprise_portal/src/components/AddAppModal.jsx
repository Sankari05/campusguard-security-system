// src/components/AddAppModal.jsx
import React, { useState } from 'react';
import { X, Plus, Sparkles } from 'lucide-react';

export const AddAppModal = ({ isOpen, onClose, onAddApp }) => {
  const [formData, setFormData] = useState({
    name: '',
    shortName: '',
    category: 'Custom Utility',
    url: 'http://localhost:3000',
    devPort: '3000',
    color: '#8B5CF6',
    description: '',
    folder: 'custom-app',
  });

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name) return;

    const newApp = {
      id: 'app-' + Date.now(),
      name: formData.name,
      shortName: formData.shortName || formData.name,
      category: formData.category,
      url: formData.url,
      devPort: formData.devPort,
      color: formData.color,
      gradient: `linear-gradient(135deg, ${formData.color} 0%, #4338ca 100%)`,
      bgSoft: 'rgba(99, 102, 241, 0.12)',
      iconName: 'Rocket',
      status: 'active',
      description: formData.description || 'Custom registered project application.',
      folder: formData.folder,
      roles: ['Admin', 'Standard User'],
    };

    onAddApp(newApp);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
          <div>
            <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.35rem', fontWeight: 800, color: '#0f172a' }}>
              Add New Application
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Register a project into your enterprise launchpad
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: '#f1f5f9',
              border: 'none',
              borderRadius: '8px',
              padding: '0.4rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={18} color="#64748b" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Application Title *</label>
            <input
              type="text"
              required
              className="form-input"
              placeholder="e.g. Library Management System"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Category</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Utilities"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Local Port / URL</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. http://localhost:8085"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-input"
              rows={3}
              placeholder="Brief description of this project module..."
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Brand Color Theme</label>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.25rem' }}>
              {['#059669', '#D97706', '#E11D48', '#2563EB', '#8B5CF6', '#EC4899'].map((c) => (
                <div
                  key={c}
                  onClick={() => setFormData({ ...formData, color: c })}
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: c,
                    cursor: 'pointer',
                    border: formData.color === c ? '3px solid #0f172a' : 'none',
                    boxShadow: '0 2px 5px rgba(0,0,0,0.15)',
                  }}
                />
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.75rem' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '0.65rem 1.25rem',
                borderRadius: '10px',
                border: '1px solid #e2e8f0',
                background: 'white',
                color: '#475569',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="btn-primary-glow"
              style={{ padding: '0.65rem 1.4rem' }}
            >
              <Plus size={16} />
              Add to Launchpad
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
