// Single source of truth for the user's Traveler identity.
//
// Lives entirely in localStorage on the user's browser. Never sent to the
// backend, never tracked. The Discord bot doesn't see it. Backend doesn't
// see it. It's a frontend-only convenience for pre-filling submission
// forms and personalizing the reward card link.
//
// Schema is versioned in the storage key so we can migrate cleanly later.

const STORAGE_KEY = 'nms10_traveler_identity_v1'

// Order matches DreamingFox's GRS card-generator parameter values for `r`.
// DO NOT REORDER — would break existing card URLs and stored identities.
export const RACES = [
  'Gek',
  'Vykeen',
  'Korvax',
  'Autophage',
  'Anomaly',
  'Traveller',
]

// Same — order matches the `p` parameter of the GRS generator.
export const PLATFORMS = [
  'Steam',
  'GOG',
  'Xbox',
  'Switch',
  'PlayStation',
]

// Sigils available in DreamingFox's GRS card generator. Index === `s=` value.
// Source: extracted from the GRS bundle (https://grs.dreamingfox.dev/main.*.js).
// DO NOT REORDER — values are positional and would break existing card URLs.
//
// As of extraction (2026-05-07) DreamingFox has not uploaded an NMS10 sigil.
// "The Voyager's Haven" (28) is closest to what we'd ship as default. Default
// to 0 (None) so users have to choose; cards without a sigil still render.
export const SIGILS = [
  'None',
  'FoxTech',
  'Traveller',
  'Galactic Hub',
  'Alliance of Galactic Travellers',
  'United Federation of Travelers',
  'United Nations 42',
  'Qitanian Empire',
  'Intergalactic Mexican Empire',
  'The Pirate Syndicate',
  'Aculon Empire',
  'Galactic Fleet',
  'The Norn Federation',
  'NMS Brasil',
  'Exploradores do Universo',
  'The Helghan Empire',
  'Star Wars Galactic Project',
  'The Indominus Legion',
  'PanGalatic Star Cabs',
  'Nexus Travelers',
  'Phantom Corsairs',
  'The Circle of Yggdrasil',
  'Aurelis Prime',
  'Aurelis Prime Grand Military',
  'Everion Empire',
  'Aurelis DOM',
  'NMS France',
  'Black Edge Syndicate',
  "The Voyager's Haven",
  'Corvettes & Coffee',
  'The Industrial Empire',
  'The Nicean Empire',
  'The Buddies',
  'The Iron Covenant',
  'The Neoterra Collective',
  'Gek Banking',
  'The Imperial Enclave',
]

const DEFAULT_RACE = 5      // Traveller — fits the anniversary theme
const DEFAULT_PLATFORM = 0  // Steam — most common
const DEFAULT_SIGIL = 0     // None — user picks; card renders fine without

function _validate(obj) {
  if (!obj || typeof obj !== 'object') return null
  const name = typeof obj.name === 'string' ? obj.name.trim().slice(0, 50) : ''
  const affiliation = typeof obj.affiliation === 'string' ? obj.affiliation.trim().slice(0, 60) : ''
  let race = Number(obj.race)
  if (!Number.isInteger(race) || race < 0 || race >= RACES.length) race = DEFAULT_RACE
  let platform = Number(obj.platform)
  if (!Number.isInteger(platform) || platform < 0 || platform >= PLATFORMS.length) platform = DEFAULT_PLATFORM
  let sigil = Number(obj.sigil)
  if (!Number.isInteger(sigil) || sigil < 0 || sigil >= SIGILS.length) sigil = DEFAULT_SIGIL
  return { name, race, affiliation, platform, sigil }
}

export function getIdentity() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    const validated = _validate(parsed)
    // Treat empty-name records as "not yet set" — header empty state still shows
    if (!validated || !validated.name) return null
    return validated
  } catch {
    return null
  }
}

export function saveIdentity(obj) {
  const validated = _validate(obj)
  if (!validated) throw new Error('invalid identity payload')
  if (!validated.name) throw new Error('name is required')
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(validated))
  } catch (err) {
    // Storage unavailable (private mode in some browsers) — surface the issue
    throw new Error(`could not save identity: ${err.message}`)
  }
  return validated
}

export function hasIdentity() {
  return !!getIdentity()
}

export function clearIdentity() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

// Build a draft pre-fill for forms when the user hasn't set anything yet.
// Useful for the modal's initial state.
export function blankDraft() {
  return {
    name: '',
    race: DEFAULT_RACE,
    affiliation: '',
    platform: DEFAULT_PLATFORM,
    sigil: DEFAULT_SIGIL,
  }
}
