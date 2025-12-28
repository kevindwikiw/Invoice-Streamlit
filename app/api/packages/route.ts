import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/app/api/auth/[...nextauth]/route';
import { createPackage, listPackages } from '@/lib/packages';

export async function GET() {
  const packages = await listPackages();
  return NextResponse.json({ data: packages });
}

export async function POST(request: Request) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const body = await request.json();
  const { name, price, category, description } = body || {};
  if (!name || typeof price !== 'number') {
    return NextResponse.json({ error: 'Name and price are required' }, { status: 400 });
  }

  const created = await createPackage({
    name: String(name),
    price: Number(price),
    category: category ? String(category) : 'Utama',
    description: description ? String(description) : '',
  });

  return NextResponse.json({ data: created }, { status: 201 });
}
