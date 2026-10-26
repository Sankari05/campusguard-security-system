import React, { createContext, useContext, useState, useEffect } from 'react';
import { translations } from '../translations';
import { initialMockState, api } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  // Presets for Guard and Admin personas
  const guardProfile = {
    id: 1,
    username: 'watchman1',
    fullName: 'Ramasamy (Main Gate Security)',
    role: 'WATCHMAN',
    department: 'Campus Security & Gate 1',
    email: 'gate1@college.edu',
  };

  const adminProfile = {
    id: 99,
    username: 'admin',
    fullName: 'Dr. K. Sundararajan (Campus Director / Admin)',
    role: 'ADMIN',
    department: 'Campus Administration & Executive Governance',
    email: 'principal@college.edu',
  };

  // Active dashboard view: 'SECURITY' (Guard Kiosk) vs 'ADMIN' (Campus Admin Dashboard)
  const isInitialUrlAdmin = () => {
    const path = window.location.pathname.toLowerCase();
    const hash = window.location.hash.toLowerCase();
    return path.includes('admin') || hash.includes('admin');
  };

  const [activeDashboard, setActiveDashboardState] = useState(() => {
    if (isInitialUrlAdmin()) return 'ADMIN';
    return localStorage.getItem('campusguard_active_dashboard') || 'SECURITY';
  });

  // Dedicated User state: null if logged out, or stored session
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('campusguard_user');
    if (!saved || saved === 'LOGGED_OUT' || saved === 'null') {
      return null;
    }
    try {
      return JSON.parse(saved);
    } catch {
      return null;
    }
  });

  const setActiveDashboard = (mode) => {
    const nextMode = mode === 'ADMIN' ? 'ADMIN' : 'SECURITY';
    setActiveDashboardState(nextMode);
    localStorage.setItem('campusguard_active_dashboard', nextMode);
    const nextUser = nextMode === 'ADMIN' ? adminProfile : guardProfile;
    setUser(nextUser);
    localStorage.setItem('campusguard_user', JSON.stringify(nextUser));

    const targetUrl = nextMode === 'ADMIN' ? '/admin' : '/';
    if (window.location.pathname !== targetUrl) {
      window.history.pushState({}, '', targetUrl);
      window.dispatchEvent(new Event('popstate'));
    }
  };

  // Language state (default 'en', can be 'ta')
  const [language, setLanguage] = useState(() => {
    return localStorage.getItem('campusguard_lang') || 'en';
  });

  // Global live lists (starts empty - no hardcoded mock logs)
  const [gateLogs, setGateLogs] = useState(() => {
    try {
      const saved = localStorage.getItem('campusguard_gatelogs');
      if (saved) return JSON.parse(saved);
    } catch (e) {
      console.warn('Error reading gate logs from localStorage:', e);
    }
    return [];
  });
  const [outPasses, setOutPasses] = useState(initialMockState.outPasses);
  const [visitors, setVisitors] = useState(initialMockState.visitors);
  const [parcels, setParcels] = useState(initialMockState.parcels);
  const [stats, setStats] = useState(initialMockState.stats);
  const [activeSos, setActiveSos] = useState(null);

  // Live Alerts
  const [notifications, setNotifications] = useState([
    { id: 1, textEn: 'Out-Pass approved for Karthik (22CS101) by HOD CSE', textTa: 'கார்த்திக் (22CS101) மாணவருக்கு HOD அவுட்-பாஸ் அனுமதித்தார்', time: '10m ago', unread: true },
    { id: 2, textEn: 'Amazon Delivery arrived at Main Gate Desk', textTa: 'அமேசான் பார்சல் மெயின் கேட் மேசைக்கு வந்துள்ளது', time: '25m ago', unread: true },
    { id: 3, textEn: 'Late entry alert: 23ME045 checked in after 09:00 AM', textTa: 'தாமத வருகை: 23ME045 காலை 09:00 மணிக்கு பின் வந்தார்', time: '1h ago', unread: false }
  ]);

  useEffect(() => {
    if (user) {
      localStorage.setItem('campusguard_user', JSON.stringify(user));
    }
  }, [user]);

  useEffect(() => {
    localStorage.setItem('campusguard_lang', language);
  }, [language]);

  const t = translations[language] || translations.en;

  const toggleLanguage = () => {
    setLanguage((prev) => (prev === 'en' ? 'ta' : 'en'));
  };

  const changeLanguage = (newLang) => {
    setLanguage(newLang);
  };

  const login = async (usernameOrEmail, password) => {
    const isAdmin = usernameOrEmail.toLowerCase().includes('admin');
    const assignedRole = isAdmin ? 'ADMIN' : 'WATCHMAN';
    const data = await api.login({ usernameOrEmail, password, role: assignedRole });

    let resolvedUser;
    if (data && (data.role || data.username)) {
      const roleUpper = (data.role || (isAdmin ? 'ADMIN' : 'WATCHMAN')).toUpperCase();
      resolvedUser = {
        id: data.id || (isAdmin ? 99 : 1),
        username: data.username || usernameOrEmail,
        fullName: data.full_name || data.fullName || (roleUpper.includes('ADMIN') ? 'Enterprise Admin' : 'Security Officer'),
        role: roleUpper,
        department: data.department || (roleUpper.includes('ADMIN') ? 'Executive Administration' : 'Campus Security'),
        email: data.email || `${usernameOrEmail}@campus.edu`,
        assigned_gate: data.assigned_gate || 'Main Gate',
        assigned_shift: data.assigned_shift || 'General Shift',
        organization_id: data.organization_id || null,
        token: data.token || null
      };
    } else {
      resolvedUser = isAdmin ? adminProfile : guardProfile;
    }

    setUser(resolvedUser);
    const nextMode = resolvedUser.role === 'SUPER_ADMIN' ? 'SUPER_ADMIN'
                   : resolvedUser.role === 'ORG_ADMIN' ? 'TENANT_ADMIN'
                   : resolvedUser.role === 'ADMIN' ? 'ADMIN'
                   : 'SECURITY';
    setActiveDashboardState(nextMode);
    localStorage.setItem('campusguard_active_dashboard', nextMode);
    localStorage.setItem('campusguard_user', JSON.stringify(resolvedUser));

    let targetUrl = '/';
    if (resolvedUser.role === 'SUPER_ADMIN') {
      targetUrl = '/super-admin';
    } else if (resolvedUser.role === 'ORG_ADMIN') {
      targetUrl = '/tenant';
    } else if (resolvedUser.role === 'ADMIN') {
      targetUrl = '/admin';
    }

    if (window.location.pathname !== targetUrl) {
      window.history.pushState({}, '', targetUrl);
      window.dispatchEvent(new Event('popstate'));
    }
    return resolvedUser;
  };

  const logout = () => {
    try {
      api.logout();
    } catch {}
    setUser(null);
    localStorage.setItem('campusguard_user', 'LOGGED_OUT');
    localStorage.removeItem('campusguard_token');
    if (window.location.pathname !== '/') {
      window.history.pushState({}, '', '/');
      window.dispatchEvent(new Event('popstate'));
    }
  };

  // Helper actions for Watchman
  const addGateLog = (newLog) => {
    setGateLogs((prev) => {
      const updated = [newLog, ...prev];
      try {
        localStorage.setItem('campusguard_gatelogs', JSON.stringify(updated));
      } catch (e) {
        console.warn('Error saving gate logs to localStorage:', e);
      }
      return updated;
    });
    setStats((prev) => ({
      ...prev,
      entriesToday: newLog.direction === 'IN' ? prev.entriesToday + 1 : prev.entriesToday,
      exitsToday: newLog.direction === 'OUT' ? prev.exitsToday + 1 : prev.exitsToday,
      totalOnCampus: newLog.direction === 'IN' ? prev.totalOnCampus + 1 : prev.totalOnCampus - 1,
    }));
  };

  const clearGateLogs = () => {
    setGateLogs([]);
    try {
      localStorage.removeItem('campusguard_gatelogs');
    } catch {}
  };

  const deleteGateLog = (id) => {
    setGateLogs((prev) => {
      const updated = prev.filter((l) => l.id !== id);
      try {
        localStorage.setItem('campusguard_gatelogs', JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  const addVisitor = (visitor) => {
    setVisitors((prev) => [visitor, ...prev]);
    setStats((prev) => ({ ...prev, activeVisitors: prev.activeVisitors + 1 }));
  };

  const checkoutVisitor = (id) => {
    setVisitors((prev) =>
      prev.map((v) => (v.id === id ? { ...v, status: 'CHECKED_OUT' } : v))
    );
    setStats((prev) => ({ ...prev, activeVisitors: Math.max(0, prev.activeVisitors - 1) }));
  };

  const addParcel = (parcel) => {
    setParcels((prev) => [parcel, ...prev]);
    setStats((prev) => ({ ...prev, parcelsAtGate: prev.parcelsAtGate + 1 }));
  };

  const handoverParcel = (id) => {
    setParcels((prev) =>
      prev.map((p) => (p.id === id ? { ...p, status: 'DELIVERED' } : p))
    );
    setStats((prev) => ({ ...prev, parcelsAtGate: Math.max(0, prev.parcelsAtGate - 1) }));
  };

  const triggerSos = (reason) => {
    const alert = {
      id: Date.now(),
      reason: reason || 'Urgent Security Alert at Main Gate',
      time: new Date().toLocaleTimeString(),
      reportedBy: user?.fullName || 'Main Gate Watchman',
    };
    setActiveSos(alert);
  };

  const resolveSos = () => {
    setActiveSos(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role || (activeDashboard === 'ADMIN' ? 'ADMIN' : 'WATCHMAN'),
        activeDashboard,
        setActiveDashboard,
        language,
        t,
        toggleLanguage,
        changeLanguage,
        login,
        logout,
        gateLogs,
        addGateLog,
        clearGateLogs,
        deleteGateLog,
        outPasses,
        visitors,
        addVisitor,
        checkoutVisitor,
        parcels,
        addParcel,
        handoverParcel,
        stats,
        activeSos,
        triggerSos,
        resolveSos,
        notifications,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
