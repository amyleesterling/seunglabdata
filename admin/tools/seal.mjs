#!/usr/bin/env node
/**
 * seal.mjs: encrypt the admin page's private content.
 *
 *   node admin/tools/seal.mjs
 *
 * Reads admin/private/content.json (the to do list and links) and the
 * password from admin/private/word, and writes admin/data.enc.json, which is
 * what the page decrypts in the browser (PBKDF2 SHA-256 -> AES-GCM 256).
 * admin/private/ is gitignored: the readable copy never goes to GitHub.
 *
 * The password is short, so this keeps the list out of plain view in a
 * public repo; it is not protection against a determined guesser. Never put
 * keys or tokens in content.json.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const admin = join(dirname(fileURLToPath(import.meta.url)), '..');
const content = JSON.parse(readFileSync(join(admin, 'private', 'content.json'), 'utf8'));
const word = readFileSync(join(admin, 'private', 'word'), 'utf8').trim().toLowerCase();
content.updated = new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC';

const { subtle } = globalThis.crypto;
const salt = globalThis.crypto.getRandomValues(new Uint8Array(16));
const iv = globalThis.crypto.getRandomValues(new Uint8Array(12));
const iterations = 250000;
const base = await subtle.importKey('raw', new TextEncoder().encode(word), 'PBKDF2', false, ['deriveKey']);
const key = await subtle.deriveKey({ name: 'PBKDF2', salt, iterations, hash: 'SHA-256' },
  base, { name: 'AES-GCM', length: 256 }, false, ['encrypt']);
const data = new Uint8Array(await subtle.encrypt({ name: 'AES-GCM', iv }, key,
  new TextEncoder().encode(JSON.stringify(content))));

const b64 = u => Buffer.from(u).toString('base64');
writeFileSync(join(admin, 'data.enc.json'),
  JSON.stringify({ v: 1, iterations, salt: b64(salt), iv: b64(iv), data: b64(data) }) + '\n');

// Prove the result opens with the word before anything is committed.
const dkey = await subtle.deriveKey({ name: 'PBKDF2', salt, iterations, hash: 'SHA-256' },
  base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
const back = JSON.parse(new TextDecoder().decode(await subtle.decrypt({ name: 'AES-GCM', iv }, dkey, data)));
const items = back.todo.reduce((n, g) => n + g.items.length, 0);
console.log(`sealed ${items} to do items in ${back.todo.length} groups, updated ${back.updated}`);
