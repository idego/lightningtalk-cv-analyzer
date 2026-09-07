import assert from 'node:assert/strict';
import test from 'node:test';
import { researchErrorFields, researchErrorDescription, formatResearchError } from './research-error-details.js';

test('diagnostics retain known failure codes but never raw upstream text', () => {
  assert.deepEqual(researchErrorFields({detail:'company_research_invalid_response', error_reason:'subject_mismatch'}), {code:'company_research_invalid_response', reason:'subject_mismatch'});
  const fields = researchErrorFields({detail:'Private candidate text', error_reason:'private@example.test'});
  assert.deepEqual(fields, {code:'research_failed', reason:undefined});
});
test('copied diagnostics distinguish validation, timeout and network failures', () => {
  const details = {operation:'company_research', analysisId:'synthetic-analysis', occurredAt:'2026-09-07T12:00:00Z', code:'company_research_invalid_response', httpStatus:502, reason:'subject_mismatch'};
  assert.match(researchErrorDescription(details, 'en'), /did not match/);
  assert.match(researchErrorDescription({...details, httpStatus:504}, 'pl'), /limit czasu/);
  assert.match(researchErrorDescription({...details, code:'network_error', httpStatus:undefined, reason:undefined}, 'en'), /could not be reached/);
  assert.match(formatResearchError(details), /Reason: subject_mismatch/);
  assert.match(formatResearchError(details), /HTTP: 502/);
});
