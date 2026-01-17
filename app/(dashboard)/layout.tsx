import { ReactNode } from 'react';
import { getServerSession } from 'next-auth';
import { Sidebar } from '@/components/layout/Sidebar';
import { countPackages } from '@/lib/packages';
import { authOptions } from '@/app/api/auth/[...nextauth]/route';
import { formatDisplayName } from '@/lib/auth';

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const session = await getServerSession(authOptions);
  const packageCount = await countPackages();
  const username = formatDisplayName(session?.user?.name || 'Admin');

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', minHeight: '100vh' }}>
      <Sidebar username={username} packageCount={packageCount} />
      <div style={{ padding: '20px 22px' }}>{children}</div>
    </div>
  );
}
