import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  const count = await prisma.packages.count();
  if (count > 0) {
    console.log('Packages already exist, skipping seed.');
    return;
  }

  await prisma.packages.createMany({
    data: [
      {
        name: 'Wedding Silver',
        price: 5000000,
        category: 'Utama',
        description: '1 Photographer\n1 Videographer\nAlbum 20 Pages',
      },
      {
        name: 'Wedding Gold',
        price: 8500000,
        category: 'Utama',
        description: '2 Photographers\n2 Videographers\nDrone Footage',
      },
      {
        name: 'Photo Booth Add-on',
        price: 1500000,
        category: 'Bonus',
        description: 'Instant print station\nProps & backdrop',
      },
    ],
  });

  console.log('Seed completed');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => prisma.$disconnect());
