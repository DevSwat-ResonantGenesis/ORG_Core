/**
 * ResonantGenesis SDK
 * Main entry point for chain interaction and crypto utilities
 */

// Chain client
export {
  ChainClient,
  ChainConfig,
  CHAIN_CONFIGS,
  IdentityType,
  IdentityStatus,
  AgentStatus,
  MemoryType,
  Identity,
  Agent,
  MemoryAnchor
} from './chain-client';

// Crypto utilities
export {
  generateKeypair,
  deriveDsid,
  parseDsid,
  validateDsid,
  canonicalize,
  sign,
  signObject,
  computeManifestHash,
  hashToBytes32,
  randomBytes32,
  createKeyRotation,
  ZERO_BYTES32,
  Keypair,
  SignedMessage,
  DsidComponents,
  KeyRotationRecord
} from './crypto';

// Re-export ethers utilities
export { ethers } from 'ethers';
