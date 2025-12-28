import crypto from 'crypto';

export type AuthConfig = {
  username: string;
  passwordHash?: string;
  password?: string;
  idleTimeoutMinutes: number;
};

export function loadAuthConfig(): AuthConfig {
  return {
    username: process.env.AUTH_USERNAME || 'admin',
    passwordHash: process.env.AUTH_PASSWORD_HASH,
    password: process.env.AUTH_PASSWORD,
    idleTimeoutMinutes: Number(process.env.AUTH_IDLE_TIMEOUT_MIN || '30'),
  };
}

function hashPw(password: string, salt: string, iterations: number): string {
  const dk = crypto.pbkdf2Sync(password, salt, iterations, 32, 'sha256');
  return base64UrlEncode(dk);
}

function base64UrlEncode(buf: Buffer) {
  return buf
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

export function verifyPassword(password: string, stored?: string, fallbackPlain?: string): boolean {
  if (!stored) {
    return password === fallbackPlain;
  }
  const parts = stored.split('$');
  if (parts.length !== 4) return false;
  const [, iterStr, salt, digest] = parts;
  const iterations = Number(iterStr);
  if (!iterations || !salt || !digest) return false;
  const computed = hashPw(password, salt, iterations);
  return crypto.timingSafeEqual(Buffer.from(computed), Buffer.from(digest));
}

export function formatDisplayName(name?: string) {
  if (!name) return 'Admin';
  return name;
}
