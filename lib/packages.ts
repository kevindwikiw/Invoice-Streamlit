import { prisma } from './db';

export type PackagePayload = {
  name: string;
  price: number;
  category?: string;
  description?: string;
};

export async function listPackages() {
  return prisma.packages.findMany({ orderBy: { id: 'desc' } });
}

export async function countPackages() {
  return prisma.packages.count();
}

export async function createPackage(payload: PackagePayload) {
  return prisma.packages.create({ data: payload });
}

export async function updatePackage(id: number, payload: PackagePayload) {
  return prisma.packages.update({ where: { id }, data: payload });
}

export async function deletePackage(id: number) {
  return prisma.packages.delete({ where: { id } });
}

export async function deleteAllPackages() {
  await prisma.$executeRawUnsafe('DELETE FROM packages');
}

export async function findPackage(id: number) {
  return prisma.packages.findUnique({ where: { id } });
}
