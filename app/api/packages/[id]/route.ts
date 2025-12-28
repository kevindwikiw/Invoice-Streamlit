import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/app/api/auth/[...nextauth]/route';
import { deletePackage, findPackage, updatePackage } from '@/lib/packages';

export async function PUT(request: Request, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const id = Number(params.id);
  if (Number.isNaN(id)) return NextResponse.json({ error: 'Invalid id' }, { status: 400 });

  const body = await request.json();
  const { name, price, category, description } = body || {};
  if (!name || typeof price !== 'number') {
    return NextResponse.json({ error: 'Name and price are required' }, { status: 400 });
  }

  const updated = await updatePackage(id, {
    name: String(name),
    price: Number(price),
    category: category ? String(category) : 'Utama',
    description: description ? String(description) : '',
  });

  return NextResponse.json({ data: updated });
}

export async function DELETE(_request: Request, { params }: { params: { id: string } }) {
  const session = await getServerSession(authOptions);
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const id = Number(params.id);
  if (Number.isNaN(id)) return NextResponse.json({ error: 'Invalid id' }, { status: 400 });

  const found = await findPackage(id);
  if (!found) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  await deletePackage(id);
  return NextResponse.json({ success: true });
}
