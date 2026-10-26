import React, { useState, useEffect } from 'react';
import AppShell from './components/layout/AppShell';
import LoginCard from './components/auth/LoginCard';
import DashboardOverview from './components/dashboard/DashboardOverview';
import StudentManagement from './components/students/StudentManagement';
import AttendanceOverrides from './components/overrides/AttendanceOverrides';
import ReportsPage from './components/reports/ReportsPage';
import CameraFeed from './components/vision/CameraFeed';
import { authService } from './services/authService';

export default function App() {
  const [user, setUser] = useState(() => authService.getCurrentUser());
  const [currentPage, setCurrentPage] = useState('dashboard');

  useEffect(() => {
    // Listen for hash changes or initial URL routing
    const handleHash = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash && ['dashboard', 'hod-students', 'overrides', 'reports', 'camera'].includes(hash)) {
        setCurrentPage(hash);
      }
    };

    window.addEventListener('hashchange', handleHash);
    handleHash();

    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const handleLogout = () => {
    authService.logout();
    setUser(null);
  };

  if (!user) {
    return <LoginCard onLoginSuccess={(u) => setUser(u)} />;
  }

  const getPageTitle = () => {
    switch (currentPage) {
      case 'hod-students':
        return 'Student Management Roster';
      case 'overrides':
        return 'Attendance Overrides';
      case 'reports':
        return 'Reports & Analytics';
      case 'camera':
        return 'Biometric Vision Feed';
      default:
        return 'Administrative Command Center';
    }
  };

  return (
    <AppShell
      currentPage={currentPage}
      onNavigate={(page) => {
        setCurrentPage(page);
        window.location.hash = page;
      }}
      user={user}
      onLogout={handleLogout}
      pageTitle={getPageTitle()}
    >
      {currentPage === 'dashboard' && <DashboardOverview onNavigate={(p) => setCurrentPage(p)} />}
      {currentPage === 'hod-students' && <StudentManagement />}
      {currentPage === 'overrides' && <AttendanceOverrides />}
      {currentPage === 'reports' && <ReportsPage />}
      {currentPage === 'camera' && <CameraFeed />}
    </AppShell>
  );
}
