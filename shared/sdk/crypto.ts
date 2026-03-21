/**
 * ResonantGenesis DSID-P Cryptographic Utilities
 * Ed25519 key generation, signing, and verification
 */

import { createHash, randomBytes } from 'node:crypto';

// Types
export interface Keypair {
  publicKey: Uint8Array;
  privateKey: Uint8Array;
}

export interface SignedMessage {
  message: string;
  signature: string;
  publicKey: string;
  timestamp: number;
}

export interface DsidComponents {
  prefix: string;
  type: 'user' | 'org' | 'agent';
  publicKeyFingerprint: string;
  checksum: string;
}

/**
 * Generate Ed25519 keypair
 * Note: In production, use a proper Ed25519 library like @noble/ed25519
 */
export async function generateKeypair(): Promise<Keypair> {
  // For demo purposes - in production use @noble/ed25519
  const privateKey = randomBytes(32);
  const publicKey = sha256(privateKey); // Simplified - real Ed25519 is different
  
  return {
    publicKey,
    privateKey
  };
}

/**
 * Derive DSID-P from public key
 */
export function deriveDsid(
  publicKey: Uint8Array,
  type: 'user' | 'org' | 'agent'
): string {
  const prefix = type === 'user' ? 'dsid-u' :
                 type === 'org' ? 'dsid-o' : 'dsid-a';
  
  // Get fingerprint (first 8 bytes of SHA256)
  const hash = sha256(publicKey);
  const fingerprint = Buffer.from(hash).toString('hex').slice(0, 16);
  
  // Compute checksum (last 4 chars of SHA256 of prefix + fingerprint)
  const checksumInput = `${prefix}-${fingerprint}`;
  const checksumHash = sha256(Buffer.from(checksumInput));
  const checksum = Buffer.from(checksumHash).toString('hex').slice(0, 4);
  
  return `${prefix}-${fingerprint}-${checksum}`;
}

/**
 * Parse DSID into components
 */
export function parseDsid(dsid: string): DsidComponents | null {
  const regex = /^(dsid)-(u|o|a)-([a-f0-9]{16})-([a-f0-9]{4})$/;
  const match = dsid.match(regex);
  
  if (!match) return null;
  
  const typeMap: Record<string, 'user' | 'org' | 'agent'> = {
    'u': 'user',
    'o': 'org',
    'a': 'agent'
  };
  
  return {
    prefix: match[1],
    type: typeMap[match[2]],
    publicKeyFingerprint: match[3],
    checksum: match[4]
  };
}

/**
 * Validate DSID checksum
 */
export function validateDsid(dsid: string): boolean {
  const components = parseDsid(dsid);
  if (!components) return false;
  
  const typeChar = components.type === 'user' ? 'u' :
                   components.type === 'org' ? 'o' : 'a';
  
  const checksumInput = `dsid-${typeChar}-${components.publicKeyFingerprint}`;
  const checksumHash = sha256(Buffer.from(checksumInput));
  const expectedChecksum = Buffer.from(checksumHash).toString('hex').slice(0, 4);
  
  return components.checksum === expectedChecksum;
}

/**
 * Canonicalize object for signing (deterministic JSON)
 */
export function canonicalize(obj: unknown): string {
  return JSON.stringify(obj, Object.keys(obj as object).sort());
}

/**
 * Sign a message
 * Note: Simplified - in production use proper Ed25519 signing
 */
export function sign(
  message: string,
  privateKey: Uint8Array
): string {
  const messageBytes = Buffer.from(message);
  const combined = Buffer.concat([messageBytes, privateKey]);
  const signature = sha256(combined);
  return Buffer.from(signature).toString('hex');
}

/**
 * Sign an object (canonicalizes first)
 */
export function signObject(
  obj: unknown,
  privateKey: Uint8Array
): SignedMessage {
  const canonical = canonicalize(obj);
  const signature = sign(canonical, privateKey);
  const publicKey = Buffer.from(sha256(privateKey)).toString('hex');
  
  return {
    message: canonical,
    signature,
    publicKey,
    timestamp: Date.now()
  };
}

/**
 * Compute manifest hash (content-addressable ID)
 */
export function computeManifestHash(manifest: unknown): string {
  // Remove signature field if present
  const manifestCopy = { ...(manifest as object) };
  delete (manifestCopy as Record<string, unknown>)['signature'];
  
  const canonical = canonicalize(manifestCopy);
  const hash = sha256(Buffer.from(canonical));
  return '0x' + Buffer.from(hash).toString('hex');
}

/**
 * Hash content to bytes32 format
 */
export function hashToBytes32(content: string | Uint8Array): string {
  const hash = sha256(typeof content === 'string' ? Buffer.from(content) : content);
  return '0x' + Buffer.from(hash).toString('hex');
}

/**
 * Generate random bytes32
 */
export function randomBytes32(): string {
  return '0x' + randomBytes(32).toString('hex');
}

// Helper: SHA256
function sha256(data: Uint8Array | Buffer): Uint8Array {
  return createHash('sha256').update(data).digest();
}

// Export constants
export const ZERO_BYTES32 = '0x' + '0'.repeat(64);

/**
 * Key rotation helper
 */
export interface KeyRotationRecord {
  oldPublicKey: string;
  newPublicKey: string;
  rotatedAt: number;
  reason: string;
  signature: string;
}

export function createKeyRotation(
  oldKeypair: Keypair,
  newKeypair: Keypair,
  reason: string
): KeyRotationRecord {
  const record = {
    oldPublicKey: Buffer.from(oldKeypair.publicKey).toString('hex'),
    newPublicKey: Buffer.from(newKeypair.publicKey).toString('hex'),
    rotatedAt: Date.now(),
    reason
  };
  
  const signature = sign(canonicalize(record), oldKeypair.privateKey);
  
  return {
    ...record,
    signature
  };
}
