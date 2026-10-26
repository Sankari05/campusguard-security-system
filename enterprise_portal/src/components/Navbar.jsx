// src/components/Navbar.jsx
import React from 'react';
import { Layers, Rocket, Shield, Globe } from 'lucide-react';

export const Navbar = ({ currentView, setCurrentView, appsCount = 4 }) => {
  return (
    <header className="portal-navbar">
      <div className="nav-brand" onClick={() => setCurrentView('landing')}>
        <div className="brand-icon-box">
          <span>G</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <span className="brand-text">Gavi</span>
            <span className="brand-badge">Technologies</span>
          </div>
        </div>
      </div>

      <nav>
        <ul className="nav-links">
          <li>
            <a
              className={`nav-item ${currentView === 'landing' ? 'active' : ''}`}
              onClick={() => setCurrentView('landing')}
            >
              HOME
            </a>
          </li>
          <li>
            <a
              className={`nav-item ${currentView === 'launchpad' ? 'active' : ''}`}
              onClick={() => setCurrentView('launchpad')}
            >
              APPS
            </a>
          </li>
          <li>
            <a className="nav-item" href="#services">
              SERVICES
            </a>
          </li>
          <li>
            <a className="nav-item" href="#about">
              ABOUT
            </a>
          </li>
          <li>
            <a className="nav-item" href="#contact">
              CONTACT US
            </a>
          </li>
        </ul>
      </nav>

      <div className="nav-actions">
        <button
          id="btn-nav-my-apps"
          className={`btn-my-apps ${currentView === 'launchpad' ? 'active' : ''}`}
          onClick={() => setCurrentView('launchpad')}
        >
          <Rocket size={16} />
          My Apps
        </button>

        <button
          className="btn-primary-glow"
          onClick={() => setCurrentView('launchpad')}
          style={{ padding: '0.55rem 1.25rem', fontSize: '0.88rem' }}
        >
          Get In Touch
        </button>
      </div>
    </header>
  );
};
