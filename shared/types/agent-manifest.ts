/**
 * Agent Manifest v1 TypeScript Types
 * 
 * These types define the structure of an Agent Manifest for the
 * ResonantGenesis decentralized agent network.
 */

// =============================================================================
// DSID-P Identifiers
// =============================================================================

export type DSIDType = 'agent' | 'user' | 'org';
export type DSID = `dsid:resonant:${DSIDType}:${string}`;

// =============================================================================
// Agent Information
// =============================================================================

export type AgentCategory = 
  | 'assistant' 
  | 'analyst' 
  | 'coder' 
  | 'researcher' 
  | 'automator' 
  | 'moderator' 
  | 'custom';

export interface AgentInfo {
  /** DSID-P identifier (derived from manifest hash if not set) */
  id?: DSID;
  /** Human-readable name (3-64 chars) */
  name: string;
  /** Description (10-500 chars) */
  description: string;
  /** Agent version (semver) */
  version: string;
  /** Agent category */
  category: AgentCategory;
  /** Discovery tags (max 10) */
  tags?: string[];
  /** Icon URI (IPFS or data URI) */
  icon?: string;
}

// =============================================================================
// Code Descriptor
// =============================================================================

export type RuntimeType = 'resonant-v1' | 'langchain-v1' | 'autogen-v1' | 'custom';
export type SourceType = 'ipfs' | 'arweave' | 'https';

export interface SourceLocation {
  /** Source type */
  type: SourceType;
  /** Content URI */
  uri: string;
  /** Fallback URI */
  fallback?: string;
}

export interface Dependency {
  /** Dependency name */
  name: string;
  /** Version constraint */
  version: string;
}

export interface CodeDescriptor {
  /** Runtime identifier */
  runtime: RuntimeType;
  /** Main execution file */
  entrypoint: string;
  /** Where to fetch code */
  source: SourceLocation;
  /** SHA-256 of source bundle */
  checksum: `sha256:${string}`;
  /** Required dependencies */
  dependencies?: Dependency[];
}

// =============================================================================
// Capabilities
// =============================================================================

export type ToolType = 
  | 'filesystem'
  | 'network.http'
  | 'network.websocket'
  | 'database'
  | 'code.execute'
  | 'memory.read'
  | 'memory.write'
  | 'agent.spawn'
  | 'agent.communicate';

export type AccessLevel = 'read' | 'write' | 'execute';

export type ProviderType = 
  | 'openai' 
  | 'anthropic' 
  | 'google' 
  | 'mistral' 
  | 'groq' 
  | 'local' 
  | 'custom';

export type PersistenceLevel = 'none' | 'session' | 'permanent';

export interface ToolPermission {
  /** Tool identifier */
  tool: ToolType;
  /** Access level */
  access: AccessLevel;
  /** Scope restriction */
  scope?: string;
  /** Why this permission is needed */
  justification: string;
}

export interface MemoryConfig {
  /** Memory persistence level */
  persistence: PersistenceLevel;
  /** Max memory anchors */
  maxAnchors?: number;
  /** DSIDs with shared access */
  sharedWith?: DSID[];
}

export interface NetworkConfig {
  /** Whitelisted domains */
  allowedDomains?: string[];
  /** Blacklisted domains */
  blockedDomains?: string[];
  /** Max concurrent connections */
  maxConnections?: number;
}

export interface Capabilities {
  /** Required tool permissions */
  tools: ToolPermission[];
  /** AI providers used */
  providers: ProviderType[];
  /** Memory requirements */
  memory?: MemoryConfig;
  /** Network access */
  network?: NetworkConfig;
}

// =============================================================================
// Trust Configuration
// =============================================================================

export type TrustTier = 0 | 1 | 2 | 3 | 4;
export type AuditLevel = 'none' | 'basic' | 'full' | 'compliance';

export interface SandboxConfig {
  /** Run in isolation */
  isolated: boolean;
  /** Max execution seconds */
  maxExecutionTime?: number;
  /** Max memory MB */
  maxMemory?: number;
  /** Max tokens per execution */
  maxTokens?: number;
}

export interface TrustConfig {
  /** Starting trust tier (0-4) */
  initialTier: TrustTier;
  /** Sandbox restrictions */
  sandbox: SandboxConfig;
  /** Required audit level */
  auditLevel: AuditLevel;
  /** Require human approval */
  approvalRequired?: boolean;
}

// =============================================================================
// Ownership
// =============================================================================

export interface Ownership {
  /** Owner DSID-P */
  owner: DSID;
  /** Publisher DSID-P (if different) */
  publisher?: DSID;
  /** SPDX license identifier */
  license: string;
  /** Can ownership transfer */
  transferable?: boolean;
  /** Royalty percentage (0-100) */
  royalty?: number;
}

// =============================================================================
// Lineage
// =============================================================================

export type ManifestHash = `0x${string}`;

export interface Lineage {
  /** Parent manifest hash */
  parent?: ManifestHash | null;
  /** Full ancestor chain */
  ancestors?: ManifestHash[];
  /** ISO 8601 timestamp */
  createdAt: string;
  /** Version changelog */
  changelog?: string;
}

// =============================================================================
// Signature
// =============================================================================

export type SignatureAlgorithm = 'ed25519' | 'secp256k1';

export interface Signature {
  /** Signature algorithm */
  algorithm: SignatureAlgorithm;
  /** Hex-encoded public key */
  publicKey: `0x${string}`;
  /** Hex-encoded signature */
  value: `0x${string}`;
}

// =============================================================================
// Complete Agent Manifest
// =============================================================================

export interface AgentManifest {
  /** JSON-LD context URL */
  '@context': 'https://resonantgenesis.ai/schemas/agent-manifest/v1';
  /** Type identifier */
  '@type': 'AgentManifest';
  /** Manifest spec version */
  version: string;
  /** Agent metadata */
  agent: AgentInfo;
  /** Code location and verification */
  code: CodeDescriptor;
  /** Permission requirements */
  capabilities: Capabilities;
  /** Trust and sandbox settings */
  trust: TrustConfig;
  /** Ownership information */
  ownership: Ownership;
  /** Version history */
  lineage?: Lineage;
  /** Cryptographic signature */
  signature: Signature;
}

// =============================================================================
// On-Chain Record (minimal storage)
// =============================================================================

export interface AgentChainRecord {
  /** Primary key - manifest hash */
  manifestHash: ManifestHash;
  /** Code checksum for verification */
  codeChecksum: string;
  /** Content location */
  sourceUri: string;
  /** Owner address */
  owner: string;
  /** Initial trust tier */
  trustTier: TrustTier;
  /** Timestamp */
  createdAt: number;
  /** For lineage tracking */
  parentHash?: ManifestHash;
  /** Revocation flag */
  active: boolean;
}

// =============================================================================
// Manifest without signature (for signing)
// =============================================================================

export type UnsignedManifest = Omit<AgentManifest, 'signature'>;

// =============================================================================
// Validation Result
// =============================================================================

export interface ValidationError {
  path: string;
  message: string;
  code: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  manifestHash?: ManifestHash;
}

// =============================================================================
// Builder Types (for creating manifests)
// =============================================================================

export interface ManifestBuilder {
  setAgent(info: AgentInfo): ManifestBuilder;
  setCode(code: CodeDescriptor): ManifestBuilder;
  setCapabilities(capabilities: Capabilities): ManifestBuilder;
  setTrust(trust: TrustConfig): ManifestBuilder;
  setOwnership(ownership: Ownership): ManifestBuilder;
  setLineage(lineage: Lineage): ManifestBuilder;
  build(): UnsignedManifest;
  sign(privateKey: string): Promise<AgentManifest>;
}

// =============================================================================
// Constants
// =============================================================================

export const MANIFEST_VERSION = '1.0.0';
export const MANIFEST_CONTEXT = 'https://resonantgenesis.ai/schemas/agent-manifest/v1';

export const TRUST_TIER_NAMES: Record<TrustTier, string> = {
  0: 'Untrusted',
  1: 'Basic',
  2: 'Standard',
  3: 'Elevated',
  4: 'Full',
};

export const AUDIT_LEVEL_DESCRIPTIONS: Record<AuditLevel, string> = {
  none: 'No audit logging',
  basic: 'Action summaries only',
  full: 'Complete action logs',
  compliance: 'Full logs + compliance attestations',
};

export const TOOL_RISK_LEVELS: Record<ToolType, 'low' | 'medium' | 'high'> = {
  'memory.read': 'low',
  'memory.write': 'medium',
  'network.http': 'medium',
  'network.websocket': 'medium',
  'filesystem': 'high',
  'database': 'high',
  'code.execute': 'high',
  'agent.spawn': 'high',
  'agent.communicate': 'medium',
};
