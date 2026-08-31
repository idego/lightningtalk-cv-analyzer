import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SETTINGS,
  LEGACY_SETTINGS_STORAGE_KEY,
  SETTINGS_SCHEMA_VERSION,
  SETTINGS_STORAGE_KEY,
  loadStoredAppSettings,
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

test("v1 migration preserves preferences and adopts the v2 research defaults", () => {
  const legacy = JSON.stringify({
    uiLanguage: "pl", reportLanguage: "pl", aiEnabled: true,
    autoResearchEnabled: false, autoCompanyResearch: false,
    autoEducationResearch: false, autoLinkedinDiscovery: false,
    previewFindingsOnHover: true, expandSectionsByDefault: true,
  });
  const migrated = resolveStoredAppSettings(null, legacy);
  assert.equal(migrated.uiLanguage, "pl");
  assert.equal(migrated.reportLanguage, "pl");
  assert.equal(migrated.previewFindingsOnHover, true);
  assert.equal(migrated.expandSectionsByDefault, true);
  assert.deepEqual(
    [migrated.autoResearchEnabled, migrated.autoCompanyResearch, migrated.autoEducationResearch, migrated.autoLinkedinDiscovery],
    [true, true, true, true],
  );
  const values = new Map([[LEGACY_SETTINGS_STORAGE_KEY, legacy]]);
  const persisted = loadStoredAppSettings({ getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) });
  assert.deepEqual(persisted, migrated);
  const v2 = JSON.parse(values.get(SETTINGS_STORAGE_KEY));
  assert.equal(v2.version, SETTINGS_SCHEMA_VERSION);
  assert.equal(v2.uiLanguage, "pl");
  assert.equal(v2.previewFindingsOnHover, true);
  assert.equal(v2.autoCompanyResearch, true);
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
