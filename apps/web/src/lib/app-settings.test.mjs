import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SETTINGS,
  LEGACY_SETTINGS_STORAGE_KEY,
  SETTINGS_SCHEMA_VERSION,
  SETTINGS_STORAGE_KEY,
  loadStoredAppSettings,
  persistMigratedAppSettings,
  resolveStoredAppSettings,
} from "./app-settings.ts";

test("fresh users default AI and all automatic research kinds on", () => {
  assert.deepEqual(resolveStoredAppSettings(null, null), DEFAULT_SETTINGS);
  assert.equal(DEFAULT_SETTINGS.aiEnabled, true);
  assert.equal(DEFAULT_SETTINGS.autoResearchEnabled, true);
  assert.equal(DEFAULT_SETTINGS.autoCompanyResearch, true);
  assert.equal(DEFAULT_SETTINGS.autoEducationResearch, true);
  assert.equal(DEFAULT_SETTINGS.autoLinkedinDiscovery, true);
});

test("v1 migration preserves explicit research opt-outs and mixed preferences", () => {
  const legacy = JSON.stringify({
    uiLanguage: "pl", reportLanguage: "pl", aiEnabled: true,
    autoResearchEnabled: false, autoCompanyResearch: false,
    autoEducationResearch: true, autoLinkedinDiscovery: false,
    previewFindingsOnHover: true, expandSectionsByDefault: true,
  });
  const migrated = resolveStoredAppSettings(null, legacy);
  assert.equal(migrated.uiLanguage, "pl");
  assert.equal(migrated.reportLanguage, "pl");
  assert.equal(migrated.previewFindingsOnHover, true);
  assert.equal(migrated.expandSectionsByDefault, true);
  assert.deepEqual(
    [migrated.autoResearchEnabled, migrated.autoCompanyResearch, migrated.autoEducationResearch, migrated.autoLinkedinDiscovery],
    [false, false, true, false],
  );
  const values = new Map([[LEGACY_SETTINGS_STORAGE_KEY, legacy]]);
  const persisted = loadStoredAppSettings({ getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) });
  assert.deepEqual(persisted, migrated);
  assert.equal(values.has(SETTINGS_STORAGE_KEY), false, "snapshot reads must not persist");
  persistMigratedAppSettings({ getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) });
  const v2 = JSON.parse(values.get(SETTINGS_STORAGE_KEY));
  assert.equal(v2.version, SETTINGS_SCHEMA_VERSION);
  assert.equal(v2.uiLanguage, "pl");
  assert.equal(v2.previewFindingsOnHover, true);
  assert.equal(v2.autoCompanyResearch, false);
});

test("migration and reads survive unavailable or quota-limited storage", () => {
  const legacy = JSON.stringify({ uiLanguage: "pl", autoCompanyResearch: false });
  const storage = { getItem: (key) => key === LEGACY_SETTINGS_STORAGE_KEY ? legacy : null, setItem: () => { throw new Error("quota"); } };
  assert.equal(loadStoredAppSettings(storage).uiLanguage, "pl");
  assert.doesNotThrow(() => persistMigratedAppSettings(storage));
  assert.deepEqual(loadStoredAppSettings({ getItem: () => { throw new Error("blocked"); }, setItem: () => {} }), DEFAULT_SETTINGS);
});

test("persisted v2 opt-outs remain explicit after reload", () => {
  const stored = JSON.stringify({
    version: SETTINGS_SCHEMA_VERSION,
    uiLanguage: "en", reportLanguage: "pl", aiEnabled: true,
    autoResearchEnabled: true, autoCompanyResearch: false,
    autoEducationResearch: true, autoLinkedinDiscovery: false,
    previewFindingsOnHover: false, expandSectionsByDefault: false,
  });
  const settings = resolveStoredAppSettings(stored, null);
  assert.equal(settings.reportLanguage, "pl");
  assert.equal(settings.autoCompanyResearch, false);
  assert.equal(settings.autoEducationResearch, true);
  assert.equal(settings.autoLinkedinDiscovery, false);
});
