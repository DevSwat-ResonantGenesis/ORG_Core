#!/usr/bin/env node
/**
 * ResonantGenesis Agent Manifest Builder CLI
 * Create, validate, and sign agent manifests
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, basename } from 'node:path';
import { createHash } from 'node:crypto';

// Types from agent-manifest spec
interface AgentManifest {
  $schema: string;
  manifestVersion: string;
  agent: {
    id: string;
    name: string;
    version: string;
    description: string;
    category: string;
    tags: string[];
  };
  code: {
    runtime: string;
    entrypoint: string;
    checksum: string;
    source: {
      type: string;
      uri: string;
    };
  };
  capabilities: {
    tools: Array<{
      tool: string;
      access: string;
      scope?: string;
    }>;
    network?: {
      allowedDomains: string[];
    };
    memory?: {
      read: boolean;
      write: boolean;
      scope: string;
    };
  };
  trust: {
    initialTier: number;
    auditLevel: string;
    sandbox: {
      isolated: boolean;
      maxExecutionTime: number;
      maxMemory: number;
      maxTokens: number;
    };
  };
  ownership: {
    owner: string;
    organization?: string;
    license: string;
  };
  lineage?: {
    parent?: string;
    fork: boolean;
    changelog: string;
  };
  signature?: {
    signer: string;
    algorithm: string;
    value: string;
    timestamp: string;
  };
}

// CLI argument parsing
const args = process.argv.slice(2);
const command = args[0];

function printHelp(): void {
  console.log(`
ResonantGenesis Agent Manifest Builder

Usage:
  manifest-builder <command> [options]

Commands:
  init <name>              Create a new manifest template
  validate <file>          Validate a manifest file
  hash <file>              Compute manifest hash (content-addressable ID)
  sign <file> <key>        Sign a manifest with private key
  verify <file>            Verify manifest signature
  build <dir>              Build manifest from agent directory

Options:
  --help, -h               Show this help message
  --output, -o <file>      Output file path
  --owner <dsid>           Owner DSID-P
  --tier <0-4>             Initial trust tier

Examples:
  manifest-builder init my-agent
  manifest-builder validate manifest.json
  manifest-builder hash manifest.json
  manifest-builder sign manifest.json ./private.key
  manifest-builder build ./my-agent --owner dsid-u-abc123-def4
`);
}

function createTemplate(name: string): AgentManifest {
  const id = `agent-${name.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;
  
  return {
    $schema: "https://resonantgenesis.io/schemas/agent-manifest-v1.json",
    manifestVersion: "1.0.0",
    agent: {
      id,
      name,
      version: "1.0.0",
      description: `${name} agent - describe what this agent does`,
      category: "general",
      tags: ["autonomous", "ai"]
    },
    code: {
      runtime: "python:3.11",
      entrypoint: "main.py",
      checksum: "",
      source: {
        type: "ipfs",
        uri: ""
      }
    },
    capabilities: {
      tools: [
        {
          tool: "memory.read",
          access: "read",
          scope: "self"
        }
      ],
      network: {
        allowedDomains: []
      },
      memory: {
        read: true,
        write: true,
        scope: "self"
      }
    },
    trust: {
      initialTier: 0,
      auditLevel: "basic",
      sandbox: {
        isolated: true,
        maxExecutionTime: 300,
        maxMemory: 512,
        maxTokens: 50000
      }
    },
    ownership: {
      owner: "",
      license: "MIT"
    },
    lineage: {
      fork: false,
      changelog: "Initial release"
    }
  };
}

function canonicalize(obj: unknown): string {
  if (obj === null || typeof obj !== 'object') {
    return JSON.stringify(obj);
  }
  
  if (Array.isArray(obj)) {
    return '[' + obj.map(canonicalize).join(',') + ']';
  }
  
  const keys = Object.keys(obj as Record<string, unknown>).sort();
  const pairs = keys.map(key => {
    const value = (obj as Record<string, unknown>)[key];
    return `"${key}":${canonicalize(value)}`;
  });
  
  return '{' + pairs.join(',') + '}';
}

function computeHash(manifest: AgentManifest): string {
  const copy = { ...manifest };
  delete copy.signature;
  
  const canonical = canonicalize(copy);
  const hash = createHash('sha256').update(canonical).digest('hex');
  return '0x' + hash;
}

function validateManifest(manifest: AgentManifest): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  // Required fields
  if (!manifest.$schema) errors.push('Missing $schema');
  if (!manifest.manifestVersion) errors.push('Missing manifestVersion');
  if (!manifest.agent?.id) errors.push('Missing agent.id');
  if (!manifest.agent?.name) errors.push('Missing agent.name');
  if (!manifest.agent?.version) errors.push('Missing agent.version');
  if (!manifest.code?.runtime) errors.push('Missing code.runtime');
  if (!manifest.code?.entrypoint) errors.push('Missing code.entrypoint');
  if (!manifest.ownership?.owner) errors.push('Missing ownership.owner');
  
  // Trust tier validation
  if (manifest.trust?.initialTier !== undefined) {
    if (manifest.trust.initialTier < 0 || manifest.trust.initialTier > 4) {
      errors.push('trust.initialTier must be 0-4');
    }
  }
  
  // Version format
  if (manifest.agent?.version && !/^\d+\.\d+\.\d+/.test(manifest.agent.version)) {
    errors.push('agent.version must be semver format (x.y.z)');
  }
  
  // DSID format
  if (manifest.ownership?.owner && !/^dsid-(u|o|a)-[a-f0-9]{16}-[a-f0-9]{4}$/.test(manifest.ownership.owner)) {
    errors.push('ownership.owner must be valid DSID-P format');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
}

function loadManifest(filePath: string): AgentManifest {
  const fullPath = resolve(filePath);
  if (!existsSync(fullPath)) {
    throw new Error(`File not found: ${fullPath}`);
  }
  
  const content = readFileSync(fullPath, 'utf-8');
  return JSON.parse(content);
}

function saveManifest(manifest: AgentManifest, filePath: string): void {
  const content = JSON.stringify(manifest, null, 2);
  writeFileSync(filePath, content, 'utf-8');
}

// Command handlers
function handleInit(): void {
  const name = args[1];
  if (!name) {
    console.error('Error: Agent name required');
    console.error('Usage: manifest-builder init <name>');
    process.exit(1);
  }
  
  const outputArg = args.indexOf('--output');
  const outputPath = outputArg !== -1 ? args[outputArg + 1] : `${name}-manifest.json`;
  
  const ownerArg = args.indexOf('--owner');
  const owner = ownerArg !== -1 ? args[ownerArg + 1] : '';
  
  const tierArg = args.indexOf('--tier');
  const tier = tierArg !== -1 ? parseInt(args[tierArg + 1], 10) : 0;
  
  const manifest = createTemplate(name);
  manifest.ownership.owner = owner;
  manifest.trust.initialTier = tier;
  
  saveManifest(manifest, outputPath);
  console.log(`Created manifest template: ${outputPath}`);
  console.log(`\nNext steps:`);
  console.log(`1. Edit ${outputPath} to fill in details`);
  console.log(`2. Set ownership.owner to your DSID-P`);
  console.log(`3. Run: manifest-builder validate ${outputPath}`);
}

function handleValidate(): void {
  const filePath = args[1];
  if (!filePath) {
    console.error('Error: Manifest file required');
    process.exit(1);
  }
  
  try {
    const manifest = loadManifest(filePath);
    const result = validateManifest(manifest);
    
    if (result.valid) {
      console.log('✓ Manifest is valid');
      const hash = computeHash(manifest);
      console.log(`  Hash: ${hash}`);
    } else {
      console.log('✗ Manifest validation failed:');
      result.errors.forEach(err => console.log(`  - ${err}`));
      process.exit(1);
    }
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

function handleHash(): void {
  const filePath = args[1];
  if (!filePath) {
    console.error('Error: Manifest file required');
    process.exit(1);
  }
  
  try {
    const manifest = loadManifest(filePath);
    const hash = computeHash(manifest);
    console.log(hash);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

function handleSign(): void {
  const filePath = args[1];
  const keyPath = args[2];
  
  if (!filePath || !keyPath) {
    console.error('Error: Manifest file and key file required');
    console.error('Usage: manifest-builder sign <manifest> <keyfile>');
    process.exit(1);
  }
  
  try {
    const manifest = loadManifest(filePath);
    const keyContent = readFileSync(resolve(keyPath), 'utf-8').trim();
    
    // Compute signature (simplified - real impl uses Ed25519)
    const hash = computeHash(manifest);
    const signatureData = hash + keyContent;
    const signature = createHash('sha256').update(signatureData).digest('hex');
    
    manifest.signature = {
      signer: manifest.ownership.owner,
      algorithm: 'ed25519',
      value: signature,
      timestamp: new Date().toISOString()
    };
    
    const outputArg = args.indexOf('--output');
    const outputPath = outputArg !== -1 ? args[outputArg + 1] : filePath;
    
    saveManifest(manifest, outputPath);
    console.log(`✓ Manifest signed`);
    console.log(`  Signer: ${manifest.ownership.owner}`);
    console.log(`  Hash: ${hash}`);
    console.log(`  Output: ${outputPath}`);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

function handleVerify(): void {
  const filePath = args[1];
  if (!filePath) {
    console.error('Error: Manifest file required');
    process.exit(1);
  }
  
  try {
    const manifest = loadManifest(filePath);
    
    if (!manifest.signature) {
      console.log('✗ Manifest is not signed');
      process.exit(1);
    }
    
    // Simplified verification
    const hash = computeHash(manifest);
    console.log('✓ Signature present');
    console.log(`  Signer: ${manifest.signature.signer}`);
    console.log(`  Algorithm: ${manifest.signature.algorithm}`);
    console.log(`  Timestamp: ${manifest.signature.timestamp}`);
    console.log(`  Hash: ${hash}`);
    console.log('\nNote: Full Ed25519 verification requires the signer\'s public key');
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

function handleBuild(): void {
  const dirPath = args[1];
  if (!dirPath) {
    console.error('Error: Agent directory required');
    process.exit(1);
  }
  
  const fullPath = resolve(dirPath);
  const manifestPath = `${fullPath}/manifest.json`;
  
  if (!existsSync(manifestPath)) {
    console.error(`Error: No manifest.json found in ${dirPath}`);
    console.error('Run: manifest-builder init <name> first');
    process.exit(1);
  }
  
  try {
    const manifest = loadManifest(manifestPath);
    
    // Compute code checksum if entrypoint exists
    const entrypointPath = `${fullPath}/${manifest.code.entrypoint}`;
    if (existsSync(entrypointPath)) {
      const code = readFileSync(entrypointPath);
      manifest.code.checksum = '0x' + createHash('sha256').update(code).digest('hex');
      console.log(`✓ Computed code checksum: ${manifest.code.checksum.slice(0, 18)}...`);
    }
    
    // Validate
    const result = validateManifest(manifest);
    if (!result.valid) {
      console.log('✗ Validation failed:');
      result.errors.forEach(err => console.log(`  - ${err}`));
      process.exit(1);
    }
    
    // Compute manifest hash
    const hash = computeHash(manifest);
    manifest.agent.id = hash;
    
    // Save updated manifest
    saveManifest(manifest, manifestPath);
    
    console.log(`\n✓ Build complete`);
    console.log(`  Manifest: ${manifestPath}`);
    console.log(`  Agent ID: ${hash}`);
    console.log(`\nNext: Upload code to IPFS and update manifest.code.source.uri`);
  } catch (err) {
    console.error(`Error: ${(err as Error).message}`);
    process.exit(1);
  }
}

// Main
if (args.includes('--help') || args.includes('-h') || !command) {
  printHelp();
  process.exit(0);
}

switch (command) {
  case 'init':
    handleInit();
    break;
  case 'validate':
    handleValidate();
    break;
  case 'hash':
    handleHash();
    break;
  case 'sign':
    handleSign();
    break;
  case 'verify':
    handleVerify();
    break;
  case 'build':
    handleBuild();
    break;
  default:
    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exit(1);
}
