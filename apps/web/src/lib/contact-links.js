/**
 * A literal CV link counts as a contact detail unless the analysis tagged it
 * as belonging to an employment, education, or certificate section.
 * Reports stored before section tagging existed have no `section` field and
 * are treated as contact links.
 *
 * @param {Record<string, unknown> | null | undefined} link
 */
export function isContactLink(link) {
  return link != null && (link.section === undefined || link.section === null);
}
