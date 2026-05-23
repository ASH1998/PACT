import { NavLink, Outlet } from 'react-router-dom';
import { Shield, Play, Users, Zap } from 'lucide-react';

const nav = [
  { to: '/', icon: Shield, label: 'Overview' },
  { to: '/runs', icon: Play, label: 'Runs' },
  { to: '/agents', icon: Users, label: 'Agents' },
];

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-pact-surface border-r border-pact-border flex flex-col">
        {/* Brand */}
        <div className="h-14 flex items-center gap-2 px-4 border-b border-pact-border">
          <Zap className="w-5 h-5 text-pact-accent" />
          <span className="font-semibold text-sm tracking-wide">PACT SOC</span>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-3 space-y-0.5 px-2">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }: { isActive: boolean }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-pact-accent/15 text-pact-accent'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-pact-bg/60'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-pact-border text-[10px] text-gray-600 font-mono">
          PACT v0.1.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-pact-bg p-6">
        <Outlet />
      </main>
    </div>
  );
}
