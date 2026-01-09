export type StorageResult = { success: boolean; url?: string; message: string };

export async function uploadInvoicePlaceholder(_bytes: Buffer, filename: string): Promise<StorageResult> {
  return {
    success: false,
    url: undefined,
    message: `Upload for ${filename} is not yet wired to Drive. Implement provider in lib/storage.ts`,
  };
}
