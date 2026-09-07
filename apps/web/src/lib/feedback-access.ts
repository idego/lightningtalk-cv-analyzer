import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";

export type FeedbackRole = "owner" | "reviewer";

const dbPath = process.env.BETTER_AUTH_DB_PATH ?? "./data/auth.db";
let databaseInstance: InstanceType<typeof Database> | undefined;

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function allowedEmail(email: string) {
  const domain = email.split("@")[1];
  const allowedDomains = (process.env.ALLOWED_EMAIL_DOMAINS ?? "idego.io")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);
  return Boolean(domain && allowedDomains.includes(domain));
}

function database() {
  if (databaseInstance) return databaseInstance;
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  const db = new Database(dbPath);
  db.pragma("foreign_keys = ON");
  db.exec(`
    CREATE TABLE IF NOT EXISTS feedback_access_by_email (
      email TEXT PRIMARY KEY COLLATE NOCASE,
      role TEXT NOT NULL CHECK(role IN ('owner','reviewer')),
      granted_by_email TEXT,
      created_at TEXT NOT NULL,
      revoked_at TEXT
    );
    CREATE INDEX IF NOT EXISTS feedback_access_email_active_role
      ON feedback_access_by_email(revoked_at, role);
    CREATE TABLE IF NOT EXISTS feedback_settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      updated_by_email TEXT
    );
  `);
  databaseInstance = db;
  return db;
}

export function feedbackRole(email: string): FeedbackRole | null {
  const row = database()
    .prepare(
      "SELECT role FROM feedback_access_by_email WHERE email=? AND revoked_at IS NULL",
    )
    .get(normalizeEmail(email)) as { role: FeedbackRole } | undefined;
  return row?.role ?? null;
}

export function listFeedbackMembers() {
  return database()
    .prepare(`SELECT email,role,created_at AS createdAt
      FROM feedback_access_by_email
      WHERE revoked_at IS NULL
      ORDER BY role,email`)
    .all();
}

export function grantFeedbackAccess(
  email: string,
  role: FeedbackRole,
  grantedBy: string,
) {
  const normalized = normalizeEmail(email);
  if (!allowedEmail(normalized)) throw new Error("email_domain_not_allowed");
  const db = database();
  db.transaction(() => {
    const current = db
      .prepare(
        "SELECT role FROM feedback_access_by_email WHERE email=? AND revoked_at IS NULL",
      )
      .get(normalized) as { role: FeedbackRole } | undefined;
    if (current?.role === "owner" && role !== "owner") {
      const { count } = db
        .prepare(
          "SELECT COUNT(*) count FROM feedback_access_by_email WHERE role='owner' AND revoked_at IS NULL",
        )
        .get() as { count: number };
      if (count <= 1) throw new Error("last_owner_protected");
    }
    db.prepare(`INSERT INTO feedback_access_by_email(
        email,role,granted_by_email,created_at,revoked_at
      ) VALUES(?,?,?,?,NULL)
      ON CONFLICT(email) DO UPDATE SET
        role=excluded.role,
        granted_by_email=excluded.granted_by_email,
        revoked_at=NULL`)
      .run(
        normalized,
        role,
        normalizeEmail(grantedBy),
        new Date().toISOString(),
      );
  }).immediate();
  return normalized;
}

export function revokeFeedbackAccess(email: string) {
  const db = database();
  return db.transaction(() => {
    const normalized = normalizeEmail(email);
    const member = db
      .prepare(
        "SELECT role FROM feedback_access_by_email WHERE email=? AND revoked_at IS NULL",
      )
      .get(normalized) as { role: FeedbackRole } | undefined;
    if (!member) return false;
    if (member.role === "owner") {
      const count = (
        db.prepare(
          "SELECT COUNT(*) count FROM feedback_access_by_email WHERE role='owner' AND revoked_at IS NULL",
        ).get() as { count: number }
      ).count;
      if (count <= 1) throw new Error("last_owner_protected");
    }
    db.prepare(
      "UPDATE feedback_access_by_email SET revoked_at=? WHERE email=?",
    ).run(new Date().toISOString(), normalized);
    return true;
  }).immediate();
}

export function feedbackCollectionEnabled() {
  const row = database()
    .prepare("SELECT value FROM feedback_settings WHERE key='collection_enabled'")
    .get() as { value: string } | undefined;
  return row?.value !== "false";
}

export function setFeedbackCollectionEnabled(
  enabled: boolean,
  updatedBy: string,
) {
  database()
    .prepare(`INSERT INTO feedback_settings(
        key,value,updated_at,updated_by_email
      ) VALUES('collection_enabled',?,?,?)
      ON CONFLICT(key) DO UPDATE SET
        value=excluded.value,
        updated_at=excluded.updated_at,
        updated_by_email=excluded.updated_by_email`)
    .run(String(enabled), new Date().toISOString(), normalizeEmail(updatedBy));
  return enabled;
}
