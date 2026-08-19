/**
 * Rules for creating a product, mirrored from the backend.
 *
 * `product_id` is an identifier, not a label: it goes into ChromaDB metadata,
 * scopes retrieval, and gets referenced from eval fixtures. The old free-text
 * field is how the corpus ended up with "klob mobile" and "learning hub
 * mobile" — ids with spaces that no filter can address. These lock the client
 * side of that gate; `doc_validation.PRODUCT_ID_PATTERN` is the server side.
 */

import { describe, expect, it } from 'vitest';
import { isProductChoiceValid, PRODUCT_ID_PATTERN, slugifyProductId } from './ProductCombobox';
import type { Product } from '@/lib/chat';

const PRODUCTS: Product[] = [
  { id: 'klob', name: 'Klob.id' },
  { id: 'klob-mobile', name: 'Klob Mobile' },
];

describe('slugifyProductId', () => {
  it('derives a kebab-case id from a display name', () => {
    expect(slugifyProductId('Klob Mobile')).toBe('klob-mobile');
    expect(slugifyProductId('DASH Admin SaaS')).toBe('dash-admin-saas');
  });

  it('collapses runs of punctuation instead of emitting double hyphens', () => {
    // A double hyphen fails PRODUCT_ID_PATTERN, so slugify must not produce one.
    expect(slugifyProductId('Klob -- Mobile')).toBe('klob-mobile');
    expect(slugifyProductId('Acelents (tep-web)')).toBe('acelents-tep-web');
  });

  it('drops leading and trailing separators', () => {
    expect(slugifyProductId('  Klob!  ')).toBe('klob');
  });

  it('produces something the pattern accepts for ordinary names', () => {
    for (const name of ['Klob Mobile', 'TEP CMS', 'Learning Hub Mobile', 'Engauge']) {
      expect(PRODUCT_ID_PATTERN.test(slugifyProductId(name))).toBe(true);
    }
  });

  it('returns an empty string when there is nothing to slugify', () => {
    // Empty is invalid, and the caller surfaces that rather than inventing an id.
    expect(slugifyProductId('!!!')).toBe('');
    expect(PRODUCT_ID_PATTERN.test('')).toBe(false);
  });
});

describe('isProductChoiceValid', () => {
  it('rejects nothing chosen', () => {
    expect(isProductChoiceValid(null, PRODUCTS)).toBe(false);
  });

  it('accepts any existing product without re-checking its id', () => {
    // Existing ids are whatever is already indexed; the form must not refuse to
    // let someone add a document to a product that already exists.
    expect(isProductChoiceValid({ id: 'klob', name: 'Klob.id', isNew: false }, PRODUCTS)).toBe(
      true,
    );
  });

  it('accepts a well-formed new product', () => {
    expect(
      isProductChoiceValid({ id: 'engauge-cms', name: 'Engauge CMS', isNew: true }, PRODUCTS),
    ).toBe(true);
  });

  it('rejects a new product whose id is malformed', () => {
    for (const id of ['klob mobile', 'Klob', 'klob_mobile', 'klob--mobile', '-klob', '']) {
      expect(isProductChoiceValid({ id, name: 'X', isNew: true }, PRODUCTS)).toBe(false);
    }
  });

  it('rejects a new product that collides with an existing id', () => {
    // Two routes to the same product is how duplicates get made.
    expect(isProductChoiceValid({ id: 'klob', name: 'Klob lagi', isNew: true }, PRODUCTS)).toBe(
      false,
    );
  });
});
