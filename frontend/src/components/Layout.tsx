import React from 'react';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div style={{ minHeight: '100vh', background: '#f7f7f7' }}>
      <header style={{ background: '#222', color: '#fff', padding: '1rem 2rem', fontSize: 24 }}>
        Runner App
      </header>
      <main style={{ padding: '2rem 0' }}>
        {children}
      </main>
      <footer style={{ background: '#222', color: '#fff', padding: '0.5rem 2rem', fontSize: 14, textAlign: 'right' }}>
        &copy; 2025 Runner Project
      </footer>
    </div>
  );
};

export default Layout;
