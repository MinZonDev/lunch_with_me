'use client';

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import AuthGuard from '@/components/AuthGuard';
import { ToastProvider } from '@/components/Toast';
import './globals.css';

const NO_SIDEBAR_PATHS = ['/login'];

export default function RootLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const showSidebar = !NO_SIDEBAR_PATHS.includes(pathname);

  return (
    <html lang="vi">
      <head>
        <title>Lunch With Me - Đặt Cơm Nhóm</title>
        <meta name="description" content="Hệ thống đặt cơm nhóm - Quản lý order, chia tiền, theo dõi deposit" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍱</text></svg>" />
      </head>
      <body>
        <ToastProvider>
          <AuthGuard>
            {showSidebar ? (
              <div className="app-layout">
                <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
                <main className="main-content">
                  <div className="mobile-header" style={{ display: 'none', marginBottom: '16px' }}>
                    <button
                      className="mobile-menu-btn"
                      onClick={() => setSidebarOpen(true)}
                      aria-label="Open menu"
                    >
                      ☰
                    </button>
                  </div>
                  {children}
                </main>
              </div>
            ) : (
              children
            )}
          </AuthGuard>
        </ToastProvider>
        <style jsx>{`
          @media (max-width: 768px) {
            .mobile-header {
              display: flex !important;
            }
          }
        `}</style>
      </body>
    </html>
  );
}
