import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { deleteAllPackages } from '@/lib/packages';
import { authOptions } from '@/app/api/auth/[...nextauth]/route';

export async function DELETE() {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  await deleteAllPackages();
  return NextResponse.json({ success: true });
}
