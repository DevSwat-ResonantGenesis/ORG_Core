/**
 * Agent Manifest Validator
 * 
 * Validates Agent Manifests against the v1 specification,
 * computes manifest hashes, and verifies signatures.
 */

import { createHash } from 'node:crypto';
import {
  AgentManifest,
  UnsignedManifest,
  ValidationResult,
  ValidationError,
  ManifestHash,
  MANIFEST_VERSION,
  MANIFEST_CONTEXT,
  TrustTier,
  ToolType,
  TOOL_RISK_LEVELS,
} from '../types/agent-manifest';

// =============================================================================
// Canonicalization
// =============================================================================

/**
 * Canonicalize a JSON object for consistent hashing
 * - Sorts keys alphabetically
 * - Removes whitespace
 * - Handles nested objects recursively
 */
export function canonicalize(obj: unknown): string {
  if (obj === null || obj === undefined) {
    return 'null';
  }
  
  if (typeof obj === 'string') {
    return JSON.stringify(obj);
  }
  
  if (typeof obj === 'number' || typeof obj === 'boolean') {
    return String(obj);
  }
  
  if (Array.isArray(obj)) {
    return '[' + obj.map(canonicalize).join(',') + ']';
  }
  
  if (typeof obj === 'object') {
    const sortedKeys = Object.keys(obj).sort();
    const pairs = sortedKeys.map(key => {
      const value = (obj as Record<string, unknown>)[key];
      if (value === undefined) return null;
      return JSON.stringify(key) + ':' + canonicalize(value);
    }).filter(Boolean);
    return '{' + pairs.join(',') + '}';
  }
  
  return String(obj);
}

// =============================================================================
// Hash Computation
// =============================================================================

/**
 * Compute the manifest hash (Agent ID)
 * Hash = SHA-256(canonicalize(manifest - signature))
 */
export function computeManifestHash(manifest: AgentManifest | UnsignedManifest): ManifestHash {
  // Remove signature if present
  const { signature, ...manifestWithoutSignature } = manifest as AgentManifest;
  
  // Canonicalize and hash
  const canonical = canonicalize(manifestWithoutSignature);
  const hash = createHash('sha256').update(canonical).digest('hex');
  
  return `0x${hash}` as ManifestHash;
}

/**
 * Verify that a checksum matches content
 */
export function verifyChecksum(content: Buffer | string, expectedChecksum: string): boolean {
  const data = typeof content === 'string' ? Buffer.from(content) : content;
  const hash = createHash('sha256').update(data).digest('hex');
  const expected = expectedChecksum.replace('sha256:', '');
  return hash === expected;
}

// =============================================================================
// Schema Validation
// =============================================================================

const SEMVER_REGEX = /^\d+\.\d+\.\d+$/;
const DSID_REGEX = /^dsid:resonant:(agent|user|org):[a-f0-9]{32,64}$/;
const HEX_HASH_REGEX = /^0x[a-f0-9]{64}$/;
const CHECKSUM_REGEX = /^sha256:[a-f0-9]{64}$/;

/**
 * Validate manifest against the v1 specification
 */
export function validateManifest(manifest: unknown): ValidationResult {
  const errors: ValidationError[] = [];
  
  // Type guard
  if (!manifest || typeof manifest !== 'object') {
    return {
      valid: false,
      errors: [{ path: '', message: 'Manifest must be an object', code: 'INVALID_TYPE' }],
    };
  }
  
  const m = manifest as Record<string, unknown>;
  
  // Context and type
  if (m['@context'] !== MANIFEST_CONTEXT) {
    errors.push({
      path: '@context',
      message: `Must be "${MANIFEST_CONTEXT}"`,
      code: 'INVALID_CONTEXT',
    });
  }
  
  if (m['@type'] !== 'AgentManifest') {
    errors.push({
      path: '@type',
      message: 'Must be "AgentManifest"',
      code: 'INVALID_TYPE',
    });
  }
  
  // Version
  if (!m.version || !SEMVER_REGEX.test(m.version as string)) {
    errors.push({
      path: 'version',
      message: 'Must be valid semver (X.Y.Z)',
      code: 'INVALID_VERSION',
    });
  }
  
  // Agent info
  errors.push(...validateAgentInfo(m.agent, 'agent'));
  
  // Code
  errors.push(...validateCode(m.code, 'code'));
  
  // Capabilities
  errors.push(...validateCapabilities(m.capabilities, 'capabilities'));
  
  // Trust
  errors.push(...validateTrust(m.trust, 'trust'));
  
  // Ownership
  errors.push(...validateOwnership(m.ownership, 'ownership'));
  
  // Lineage (optional)
  if (m.lineage) {
    errors.push(...validateLineage(m.lineage, 'lineage'));
  }
  
  // Signature
  errors.push(...validateSignature(m.signature, 'signature'));
  
  // Compute hash if valid
  let manifestHash: ManifestHash | undefined;
  if (errors.length === 0) {
    manifestHash = computeManifestHash(m as AgentManifest);
  }
  
  return {
    valid: errors.length === 0,
    errors,
    manifestHash,
  };
}

function validateAgentInfo(agent: unknown, path: string): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (!agent || typeof agent !== 'object') {
    return [{ path, message: 'Agent info is required', code: 'MISSING_AGENT' }];
  }
  
  const a = agent as Record<string, unknown>;
  
  // Name
  if (!a.name || typeof a.name !== 'string') {
    errors.push({ path: `${path}.name`, message: 'Name is required', code: 'MISSING_NAME' });
  } else if (a.name.length < 3 || a.name.length > 64) {
    errors.push({ path: `${path}.name`, message: 'Name must be 3-64 characters', code: 'INVALID_NAME' });
  }
  
  // Description
  if (!a.description || typeof a.description !== 'string') {
    errors.push({ path: `${path}.description`, message: 'Description is required', code: 'MISSING_DESCRIPTION' });
  } else if (a.description.length < 10 || a.description.length > 500) {
    errors.push({ path: `${path}.description`, message: 'Description must be 10-500 characters', code: 'INVALID_DESCRIPTION' });
  }
  
  // Version
  if (!a.version || !SEMVER_REGEX.test(a.version as string)) {
    errors.push({ path: `${path}.version`, message: 'Version must be valid semver', code: 'INVALID_VERSION' });
  }
  
  // Category
  const validCategories = ['assistant', 'analyst', 'coder', 'researcher', 'automator', 'moderator', 'custom'];
  if (!a.category || !validCategories.includes(a.category as string)) {
    errors.push({ path: `${path}.category`, message: `Category must be one of: ${validCategories.join(', ')}`, code: 'INVALID_CATEGORY' });
  }
  
  // Tags (optional)
  if (a.tags) {
    if (!Array.isArray(a.tags)) {
      errors.push({ path: `${path}.tags`, message: 'Tags must be an array', code: 'INVALID_TAGS' });
    } else if (a.tags.length > 10) {
      errors.push({ path: `${path}.tags`, message: 'Max 10 tags allowed', code: 'TOO_MANY_TAGS' });
    }
  }
  
  // ID (optional, validated if present)
  if (a.id && !DSID_REGEX.test(a.id as string)) {
    errors.push({ path: `${path}.id`, message: 'Invalid DSID-P format', code: 'INVALID_DSID' });
  }
  
  return errors;
}

function validateCode(code: unknown, path: string): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (!code || typeof code !== 'object') {
    return [{ path, message: 'Code descriptor is required', code: 'MISSING_CODE' }];
  }
  
  const c = code as Record<string, unknown>;
  
  // Runtime
  const validRuntimes = ['resonant-v1', 'langchain-v1', 'autogen-v1', 'custom'];
  if (!c.runtime || !validRuntimes.includes(c.runtime as string)) {
    errors.push({ path: `${path}.runtime`, message: `Runtime must be one of: ${validRuntimes.join(', ')}`, code: 'INVALID_RUNTIME' });
  }
  
  // Entrypoint
  if (!c.entrypoint || typeof c.entrypoint !== 'string') {
    errors.push({ path: `${path}.entrypoint`, message: 'Entrypoint is required', code: 'MISSING_ENTRYPOINT' });
  }
  
  // Source
  if (!c.source || typeof c.source !== 'object') {
    errors.push({ path: `${path}.source`, message: 'Source is required', code: 'MISSING_SOURCE' });
  } else {
    const s = c.source as Record<string, unknown>;
    const validSourceTypes = ['ipfs', 'arweave', 'https'];
    if (!s.type || !validSourceTypes.includes(s.type as string)) {
      errors.push({ path: `${path}.source.type`, message: `Source type must be one of: ${validSourceTypes.join(', ')}`, code: 'INVALID_SOURCE_TYPE' });
    }
    if (!s.uri || typeof s.uri !== 'string') {
      errors.push({ path: `${path}.source.uri`, message: 'Source URI is required', code: 'MISSING_URI' });
    }
  }
  
  // Checksum
  if (!c.checksum || !CHECKSUM_REGEX.test(c.checksum as string)) {
    errors.push({ path: `${path}.checksum`, message: 'Checksum must be sha256:<64-char-hex>', code: 'INVALID_CHECKSUM' });
  }
  
  return errors;
}

function validateCapabilities(capabilities: unknown, path: string): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (!capabilities || typeof capabilities !== 'object') {
    return [{ path, message: 'Capabilities is required', code: 'MISSING_CAPABILITIES' }];
  }
  
  const cap = capabilities as Record<string, unknown>;
  
  // Tools
  if (!cap.tools || !Array.isArray(cap.tools)) {
    errors.push({ path: `${path}.tools`, message: 'Tools array is required', code: 'MISSING_TOOLS' });
  } else {
    const validTools: ToolType[] = [
      'filesystem', 'network.http', 'network.websocket', 'database',
      'code.execute', 'memory.read', 'memory.write', 'agent.spawn', 'agent.communicate'
    ];
    const validAccess = ['read', 'write', 'execute'];
    
    cap.tools.forEach((tool, i) => {
      const t = tool as Record<string, unknown>;
      if (!t.tool || !validTools.includes(t.tool as ToolType)) {
        errors.push({ path: `${path}.tools[${i}].tool`, message: 'Invalid tool type', code: 'INVALID_TOOL' });
      }
      if (!t.access || !validAccess.includes(t.access as string)) {
        errors.push({ path: `${path}.tools[${i}].access`, message: 'Access must be read/write/execute', code: 'INVALID_ACCESS' });
      }
      if (!t.justification || typeof t.justification !== 'string' || (t.justification as string).length < 10) {
        errors.push({ path: `${path}.tools[${i}].justification`, message: 'Justification required (min 10 chars)', code: 'MISSING_JUSTIFICATION' });
      }
    });
  }
  
  // Providers
  if (!cap.providers || !Array.isArray(cap.providers)) {
    errors.push({ path: `${path}.providers`, message: 'Providers array is required', code: 'MISSING_PROVIDERS' });
  } else {
    const validProviders = ['openai', 'anthropic', 'google', 'mistral', 'groq', 'local', 'custom'];
    cap.providers.forEach((p, i) => {
      if (!validProviders.includes(p as string)) {
        errors.push({ path: `${path}.providers[${i}]`, message: 'Invalid provider', code: 'INVALID_PROVIDER' });
      }
    });
  }
  
  return errors;
}

function validateTrust(trust: unknown, path: string): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (!trust || typeof trust !== 'object') {
    return [{ path, message: 'Trust config is required', code: 'MISSING_TRUST' }];
  }
  
  const t = trust as Record<string, unknown>;
  
  // Initial tier
  if (typeof t.initialTier !== 'number' || t.initialTier < 0 || t.initialTier > 4) {
    errors.push({ path: `${path}.initialTier`, message: 'Initial tier must be 0-4', code: 'INVALID_TIER' });
  }
  
  // Sandbox
  if (!t.sandbox || typeof t.sandbox !== 'object') {
    errors.push({ path: `${path}.sandbox`, message: 'Sandbox config is required', code: 'MISSING_SANDBOX' });
  } else {
    const s = t.sandbox as Record<string, unknown>;
    if (typeof s.isolated !== 'boolean') {
      errors.push({ path: `${path}.sandbox.isolated`, message: 'Isolated must be boolean', code: 'INVALID_ISOLATED' });
    }
  }
  
  // Audit level
  const validAuditLevels = ['none', 'basic', 'full', 'compliance'];
  if (!t.auditLevel || !validAuditLevels.includes(t.auditLevel as string)) {
    errors.push({ path: `${path}.auditLevel`, message: `Audit level must be one of: ${validAuditLevels.join(', ')}`, code: 'INVALID_AUDIT_LEVEL' });
  }
  
  return errors;
}

function validateOwnership(ownership: unknown, path: string): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (!ownership || typeof ownership !== 'object') {
    return [{ path, message: 'Ownership is required', code: 'MISSING_OWNERSHIP' }];
  }
  
  const o = ownership as Record<string, unknown>;
  
  // Owner
  if (!o.owner || !DSID_REGEX.test(o.owner as string)) {
    errors.push({ path: `${path}.owner`, message: 'Valid owner DSID-P is required', code: 'INVALID_OWNER' });
  }
  
  // Publisher (optional)
  if (o.publisher && !DSID_REGEX.test(o.publisher as string)) {
    errors.push({ path: `${path}.publisher`, message: 'Invalid publisher DSID-P', code: 'INVALID_PUBLISHER' });
  }
  
  // License
  if (!o.license || typeof o.license !== 'string') {
    errors.push({ path: `${path}.license`, message: 'License is required', code: 'MISSING_LICENSE' });
  }
  
  // Royalty (optional)
  if (o.royalty !== undefined) {
    if (typeof o.royalty !== 'number' || o.royalty < 0 || o.royalty > 100) {
      errors.push({ path: `${path}.royalty`, message: 'Royalty must be 0-100', code: 'INVALID_ROYALTY' });
    }
  }
  
  return errors;
}

function validateLineage(lineage: unknown, path: string): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (typeof lineage !== 'object') {
    return [{ path, message: 'Lineage must be an object', code: 'INVALID_LINEAGE' }];
  }
  
  const l = lineage as Record<string, unknown>;
  
  // Parent (optional)
  if (l.parent && !HEX_HASH_REGEX.test(l.parent as string)) {
    errors.push({ path: `${path}.parent`, message: 'Invalid parent hash format', code: 'INVALID_PARENT_HASH' });
  }
  
  // Ancestors (optional)
  if (l.ancestors) {
    if (!Array.isArray(l.ancestors)) {
      errors.push({ path: `${path}.ancestors`, message: 'Ancestors must be an array', code: 'INVALID_ANCESTORS' });
    } else {
      l.ancestors.forEach((a, i) => {
        if (!HEX_HASH_REGEX.test(a as string)) {
          errors.push({ path: `${path}.ancestors[${i}]`, message: 'Invalid ancestor hash', code: 'INVALID_ANCESTOR_HASH' });
        }
      });
    }
  }
  
  // Created at
  if (!l.createdAt || typeof l.createdAt !== 'string') {
    errors.push({ path: `${path}.createdAt`, message: 'createdAt is required', code: 'MISSING_CREATED_AT' });
  } else {
    const date = new Date(l.createdAt as string);
    if (isNaN(date.getTime())) {
      errors.push({ path: `${path}.createdAt`, message: 'Invalid ISO 8601 date', code: 'INVALID_DATE' });
    }
  }
  
  return errors;
}

function validateSignature(signature: unknown, path: string): ValidationError[] {
  const errors: ValidationError[] = [];
  
  if (!signature || typeof signature !== 'object') {
    return [{ path, message: 'Signature is required', code: 'MISSING_SIGNATURE' }];
  }
  
  const s = signature as Record<string, unknown>;
  
  // Algorithm
  const validAlgorithms = ['ed25519', 'secp256k1'];
  if (!s.algorithm || !validAlgorithms.includes(s.algorithm as string)) {
    errors.push({ path: `${path}.algorithm`, message: `Algorithm must be one of: ${validAlgorithms.join(', ')}`, code: 'INVALID_ALGORITHM' });
  }
  
  // Public key
  if (!s.publicKey || !HEX_HASH_REGEX.test(s.publicKey as string)) {
    errors.push({ path: `${path}.publicKey`, message: 'Invalid public key format (0x + 64 hex chars)', code: 'INVALID_PUBLIC_KEY' });
  }
  
  // Value
  if (!s.value || typeof s.value !== 'string' || !s.value.startsWith('0x')) {
    errors.push({ path: `${path}.value`, message: 'Invalid signature value', code: 'INVALID_SIGNATURE_VALUE' });
  }
  
  return errors;
}

// =============================================================================
// Risk Assessment
// =============================================================================

export interface RiskAssessment {
  level: 'low' | 'medium' | 'high' | 'critical';
  score: number;
  factors: string[];
  recommendations: string[];
}

/**
 * Assess the risk level of an agent based on its capabilities
 */
export function assessRisk(manifest: AgentManifest): RiskAssessment {
  const factors: string[] = [];
  const recommendations: string[] = [];
  let score = 0;
  
  // Check tool permissions
  for (const tool of manifest.capabilities.tools) {
    const riskLevel = TOOL_RISK_LEVELS[tool.tool];
    if (riskLevel === 'high') {
      score += 30;
      factors.push(`High-risk tool: ${tool.tool}`);
    } else if (riskLevel === 'medium') {
      score += 15;
      factors.push(`Medium-risk tool: ${tool.tool}`);
    } else {
      score += 5;
    }
    
    // Write access increases risk
    if (tool.access === 'write' || tool.access === 'execute') {
      score += 10;
      factors.push(`Write/execute access on ${tool.tool}`);
    }
  }
  
  // Check trust tier vs capabilities
  const tier = manifest.trust.initialTier as TrustTier;
  if (tier < 2 && score > 50) {
    factors.push('Low trust tier with high-risk capabilities');
    recommendations.push('Consider requiring higher initial trust tier');
  }
  
  // Check sandbox config
  if (!manifest.trust.sandbox.isolated) {
    score += 20;
    factors.push('Not running in isolation');
    recommendations.push('Enable sandbox isolation');
  }
  
  // Check audit level
  if (manifest.trust.auditLevel === 'none') {
    score += 15;
    factors.push('No audit logging');
    recommendations.push('Enable at least basic audit logging');
  }
  
  // Network access
  if (manifest.capabilities.network?.allowedDomains?.includes('*')) {
    score += 25;
    factors.push('Unrestricted network access');
    recommendations.push('Restrict network to specific domains');
  }
  
  // Determine level
  let level: 'low' | 'medium' | 'high' | 'critical';
  if (score < 30) {
    level = 'low';
  } else if (score < 60) {
    level = 'medium';
  } else if (score < 90) {
    level = 'high';
  } else {
    level = 'critical';
  }
  
  return { level, score, factors, recommendations };
}

// =============================================================================
// Exports
// =============================================================================

export default {
  validateManifest,
  computeManifestHash,
  verifyChecksum,
  canonicalize,
  assessRisk,
};
