import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Sidebar } from './components/Sidebar';
import { Navbar } from './components/Navbar';
import { Login } from './pages/Login';
import { LandingPage } from './pages/LandingPage';
import { SuperAdminPortal } from './pages/SuperAdminPortal';
import { TenantAdminPortal } from './pages/TenantAdminPortal';
import { WatchmanAdaptiveWorkspace } from './pages/WatchmanAdaptiveWorkspace';
import { Dashboard } from './pages/Dashboard';
import { GateKiosk } from './pages/GateKiosk';
import { OutPassManager } from './pages/OutPassManager';
import { VisitorPassManager } from './pages/VisitorPassManager';
import { ParcelManager } from './pages/ParcelManager';
import { VehiclesManager } from './pages/VehiclesManager';
import { EmergencySOS } from './pages/EmergencySOS';
import { ShiftHandoverManager } from './pages/ShiftHandoverManager';
import { PublicGateQrPortal } from './pages/PublicGateQrPortal';
import { AdminDashboard } from './pages/AdminDashboard';
import { MaintenanceManager } from './pages/MaintenanceManager';
import { ParkingManager } from './pages/ParkingManager';
import { PatrolManager } from './pages/PatrolManager';
import { LostFoundManager } from './pages/LostFoundManager';
import { DutyLogManager } from './pages/DutyLogManager';
import { CampusZoneRiskManager } from './pages/CampusZoneRiskManager';
import { GuardCoPilot } from './pages/GuardCoPilot';

const checkCurrentRoute = () => {
  const path = window.location.pathname.toLowerCase();
  const hash = window.location.hash.toLowerCase();
  const search = window.location.search.toLowerCase();

  if (
    path.includes('self-pass') ||
    path.includes('qr-pass') ||
    path.includes('gate-qr') ||
    path.includes('visitor-qr') ||
    hash.includes('self-pass') ||
    hash.includes('qr-pass') ||
    hash.includes('gate-qr') ||
    search.includes('self-pass') ||
    search.includes('qr-pass')
  ) {
    return 'QR';
  }

  if (path.includes('super-admin') || hash.includes('super-admin')) {
    return 'SUPER_ADMIN';
  }

  if (path.includes('tenant') || hash.includes('tenant')) {
    return 'TENANT_ADMIN';
  }

  if (path.includes('admin') || hash.includes('admin')) {
    return 'ADMIN';
  }

  if (path.includes('login') || hash.includes('login')) {
    return 'LOGIN';
  }

  return 'HOME';
};

const resolveTabFromUrl = (isAdmin = false) => {
  if (isAdmin) {
    const hash = window.location.hash.toLowerCase().replace('#', '').trim();
    if (hash.includes('compliance') || hash.includes('late')) return 'admin-compliance';
    if (hash.includes('overdue') || hash.includes('curfew')) return 'admin-overdues';
    if (hash.includes('shift')) return 'admin-shifts';
    return 'admin-dashboard';
  }

  const rawHash = decodeURIComponent(window.location.hash || '').toLowerCase().replace('#', '').trim();
  const rawPath = decodeURIComponent(window.location.pathname || '').toLowerCase().replace(/^\/+|\/+$/g, '').trim();
  const search = decodeURIComponent(window.location.search || '').toLowerCase().trim();

  let target = rawHash;
  if (!target && rawPath && rawPath !== 'home' && rawPath !== '') {
    target = rawPath;
  }
  if (!target && search.includes('tab=')) {
    target = search.split('tab=')[1].split('&')[0];
  }

  if (!target) return 'vehicles';

  if (
    target.includes('copilot') ||
    target.includes('smartguard') ||
    target.includes('co-pilot') ||
    target.includes('ai-guard') ||
    target.includes('smartguard ai co pilot')
  ) {
    return 'copilot';
  }

  if (target.includes('parking') || target.includes('bay')) return 'parking';
  if (target.includes('vehicle') || target.includes('anpr') || target.includes('car')) return 'vehicles';
  if (target.includes('visitor')) return 'visitors';
  if (target.includes('patrol') || target.includes('checkpoint')) return 'patrol';
  if (target.includes('maintenance') || target.includes('defect')) return 'maintenance';
  if (target.includes('lost') || target.includes('found')) return 'lost-found';
  if (target.includes('zone') || target.includes('weather') || target.includes('risk')) return 'zone-risk';
  if (target.includes('duty') || target.includes('attendance') || target.includes('clock')) return 'duty';
  if (target.includes('handover') || target.includes('shift')) return 'handover';
  if (target.includes('parcel') || target.includes('courier')) return 'parcels';
  if (target.includes('emergency') || target.includes('sos')) return 'emergency';
  if (target.includes('workspace') || target.includes('facility') || target.includes('guardmate')) return 'guardmate-workspace';
  if (target.includes('gate-kiosk') || target.includes('kiosk') || target === 'gate') return 'gate-kiosk';
  if (target.includes('out-pass') || target.includes('outpass')) return 'out-pass';
  if (target.includes('dashboard') || target.includes('overview') || target.includes('analytic')) return 'dashboard';

  return 'vehicles';
};

const navigateTo = (url) => {
  window.history.pushState({}, '', url);
  window.dispatchEvent(new Event('popstate'));
};

const AppContent = ({ currentRoute }) => {
  const { user, login, logout, activeDashboard, setActiveDashboard } = useAuth();
  const isAdminPath = currentRoute === 'ADMIN';

  const [activeTab, setActiveTabState] = useState(() => {
    return resolveTabFromUrl(isAdminPath);
  });

  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    setSidebarOpen(false);
  }, [activeTab, currentRoute]);

  const setActiveTab = (tab) => {
    setActiveTabState(tab);
    try {
      const prefix = isAdminPath ? '/admin#' : '/#';
      if (window.location.hash !== `#${tab}`) {
        window.history.replaceState(null, '', `${prefix}${tab}`);
      }
    } catch {
      // safe fallback
    }
  };

  useEffect(() => {
    const handleUrlChange = () => {
      const targetTab = resolveTabFromUrl(isAdminPath);
      setActiveTabState(targetTab);
    };

    window.addEventListener('hashchange', handleUrlChange);
    window.addEventListener('popstate', handleUrlChange);
    return () => {
      window.removeEventListener('hashchange', handleUrlChange);
      window.removeEventListener('popstate', handleUrlChange);
    };
  }, [isAdminPath]);

  useEffect(() => {
    if (isAdminPath && activeDashboard !== 'ADMIN') {
      setActiveDashboard('ADMIN');
    } else if (!isAdminPath && activeDashboard === 'ADMIN') {
      setActiveDashboard('SECURITY');
    }
  }, [isAdminPath]);

  // SCENARIO 1: Super Admin Portal (/super-admin)
  if (currentRoute === 'SUPER_ADMIN') {
    return (
      <SuperAdminPortal
        onBackToLanding={() => navigateTo('/')}
        onLoginAsAdmin={async () => {
          await login('superadmin', 'pass123');
        }}
      />
    );
  }

  // SCENARIO 2: Tenant Admin Portal (/tenant or user is ORG_ADMIN)
  if (currentRoute === 'TENANT_ADMIN' || user?.role === 'ORG_ADMIN') {
    if (!user) {
      return <Login initialRole="ADMIN" />;
    }
    return (
      <TenantAdminPortal
        onBackToLanding={() => navigateTo('/')}
      />
    );
  }

  // SCENARIO 3: College Admin Dashboard (/admin)
  if (isAdminPath) {
    if (!user) {
      return <Login initialRole="ADMIN" />;
    }

    // STRICT RBAC: Watchman cannot access Admin Dashboard!
    if (user.role === 'WATCHMAN') {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#FFFFFF',
          backgroundImage: `
            radial-gradient(circle at 10% 15%, rgba(153, 246, 228, 0.40) 0%, rgba(186, 230, 253, 0.25) 30%, transparent 60%),
            radial-gradient(circle at 50% 38%, rgba(254, 215, 170, 0.45) 0%, rgba(254, 243, 199, 0.25) 32%, transparent 65%),
            radial-gradient(circle at 85% 80%, rgba(199, 210, 254, 0.45) 0%, rgba(224, 231, 255, 0.30) 35%, transparent 65%),
            linear-gradient(to right, rgba(14, 165, 233, 0.08) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(14, 165, 233, 0.08) 1px, transparent 1px)
          `,
          backgroundSize: '100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px',
          color: '#0F172A',
          padding: '2rem',
          textAlign: 'center',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
        }}>
          <div style={{
            maxWidth: '500px',
            backgroundColor: '#FFFFFF',
            borderRadius: '24px',
            padding: '2.5rem 2rem',
            border: '2px solid #FECACA',
            boxShadow: '0 25px 50px -12px rgba(220, 38, 38, 0.15)'
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: '#FEF2F2',
              border: '2px solid #EF4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 1.25rem',
              fontSize: '1.8rem'
            }}>
              ⛔
            </div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 900, color: '#DC2626', margin: '0 0 0.5rem 0' }}>
              அணுகல் மறுக்கப்பட்டது (Access Denied)
            </h2>
            <p style={{ fontSize: '0.9rem', color: '#475569', lineHeight: 1.6, marginBottom: '1.75rem' }}>
              நீங்கள் <strong>வாட்ச்மேனாக ({user.fullName || user.username})</strong> உள்நுழைந்துள்ளீர்கள்.<br />
              வாட்ச்மேனுக்கு கல்லூரி நிர்வாக தளம் (Admin Dashboard) பார்க்க அனுமதி இல்லை.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button
                type="button"
                onClick={() => navigateTo('/')}
                className="btn btn-primary"
                style={{ fontWeight: 800, padding: '0.65rem 1.25rem' }}
              >
                ← Return to Gate Kiosk (/)
              </button>
              <button
                type="button"
                onClick={logout}
                className="btn btn-secondary"
                style={{ fontWeight: 800, padding: '0.65rem 1.25rem' }}
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      );
    }

    // Authenticated Admin on /admin:
    return (
      <div className="app-container">
        <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="main-content">
          <Navbar onOpenSosModal={() => setActiveTab('emergency')} onToggleSidebar={() => setSidebarOpen((prev) => !prev)} />
          <main className="page-body">
            <AdminDashboard setActiveTab={setActiveTab} />
          </main>
        </div>
      </div>
    );
  }

  // SCENARIO 4: Explicit /login path
  if (currentRoute === 'LOGIN') {
    return <Login initialRole="WATCHMAN" />;
  }

  // SCENARIO 5: Unauthenticated visitor on / -> GuardMate SaaS Landing Page
  if (!user) {
    return (
      <LandingPage
        onNavigateToLogin={(role) => navigateTo('/login')}
        onDirectLogin={async (uname, pwd) => {
          await login(uname, pwd);
        }}
      />
    );
  }

  // SCENARIO 6: Logged-in Super Admin on /
  if (user.role === 'SUPER_ADMIN') {
    return (
      <SuperAdminPortal
        onBackToLanding={() => navigateTo('/')}
      />
    );
  }

  // SCENARIO 7: Logged-in Admin on /
  if (user.role === 'ADMIN') {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#F8FAFC',
        color: '#0F172A',
        padding: '2rem',
        textAlign: 'center'
      }}>
        <div style={{
          maxWidth: '500px',
          backgroundColor: '#FFFFFF',
          borderRadius: '24px',
          padding: '2.5rem 2rem',
          border: '2px solid #2563EB',
          boxShadow: '0 25px 50px -12px rgba(37, 99, 235, 0.2)'
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: '#EFF6FF',
            border: '2px solid #2563EB',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.25rem',
            fontSize: '1.8rem'
          }}>
            🏛️
          </div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 900, color: '#1E293B', margin: '0 0 0.5rem 0' }}>
            நிர்வாக கணக்கு கண்டறியப்பட்டது
          </h2>
          <p style={{ fontSize: '0.88rem', color: '#64748B', lineHeight: 1.6, marginBottom: '1.75rem' }}>
            நீங்கள் <strong>கல்லூரி நிர்வாகியாக ({user.fullName || 'Admin'})</strong> உள்நுழைந்துள்ளீர்கள்.<br />
            நிர்வாகிகளுக்கு மெயின் கேட் வாட்ச்மேன் Kiosk இயக்க அனுமதி இல்லை.
          </p>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={() => navigateTo('/admin')}
              className="btn btn-primary"
              style={{ fontWeight: 800, padding: '0.65rem 1.25rem' }}
            >
              Go to Admin Dashboard (/admin) &rarr;
            </button>
            <button
              type="button"
              onClick={logout}
              className="btn btn-secondary"
              style={{ fontWeight: 800, padding: '0.65rem 1.25rem' }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    );
  }

  // SCENARIO 8: Dedicated Watchman Security Route on /
  const renderWatchmanScreen = () => {
    switch (activeTab) {
      case 'guardmate-workspace':
        return <WatchmanAdaptiveWorkspace onNavigateToModule={(mod) => setActiveTab(mod)} />;
      case 'dashboard':
        return <Dashboard setActiveTab={setActiveTab} />;
      case 'gate-kiosk':
        return <GateKiosk setAppTab={setActiveTab} />;
      case 'out-pass':
        return <OutPassManager setAppTab={setActiveTab} />;
      case 'visitors':
        return <VisitorPassManager />;
      case 'handover':
        return <ShiftHandoverManager />;
      case 'parcels':
        return <ParcelManager />;
      case 'vehicles':
        return <VehiclesManager />;
      case 'emergency':
        return <EmergencySOS />;
      case 'maintenance':
        return <MaintenanceManager />;
      case 'parking':
        return <ParkingManager />;
      case 'patrol':
        return <PatrolManager />;
      case 'lost-found':
        return <LostFoundManager />;
      case 'duty':
        return <DutyLogManager />;
      case 'zone-risk':
        return <CampusZoneRiskManager />;
      case 'copilot':
        return <GuardCoPilot />;
      default:
        return <VehiclesManager />;
    }
  };

  return (
    <div className="app-container">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="main-content">
        <Navbar onOpenSosModal={() => setActiveTab('emergency')} onToggleSidebar={() => setSidebarOpen((prev) => !prev)} />
        <main className="page-body">
          {renderWatchmanScreen()}
        </main>
      </div>
    </div>
  );
};

export default function App() {
  const [currentRoute, setCurrentRoute] = useState(checkCurrentRoute);

  useEffect(() => {
    const handleLocationChange = () => {
      setCurrentRoute(checkCurrentRoute());
    };
    window.addEventListener('popstate', handleLocationChange);
    window.addEventListener('hashchange', handleLocationChange);
    return () => {
      window.removeEventListener('popstate', handleLocationChange);
      window.removeEventListener('hashchange', handleLocationChange);
    };
  }, []);

  if (currentRoute === 'QR') {
    return <PublicGateQrPortal />;
  }

  return (
    <AuthProvider>
      <AppContent currentRoute={currentRoute} />
    </AuthProvider>
  );
}
