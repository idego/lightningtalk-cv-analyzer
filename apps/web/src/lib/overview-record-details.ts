import type { DisplayRecord } from "./understanding-selectors";

const join = (values: Array<string | null | undefined>) => values.filter(Boolean).join(" · ");

export function educationOverviewDetail(record: Partial<DisplayRecord>) {
  return join([record.program, record.degree, record.study_dates]);
}

export function employmentOverviewDetail(record: Partial<DisplayRecord>) {
  const locationAlreadyShown = record.location && record.organization
    ? record.organization.toLocaleLowerCase().includes(record.location.toLocaleLowerCase())
    : false;
  return join([record.employment_dates, record.organization, locationAlreadyShown ? null : record.location]);
}
