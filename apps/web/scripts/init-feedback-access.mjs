import fs from "node:fs";
import Database from "better-sqlite3";

const configPath = process.argv[2] ?? "/config/feedback-access.json";
const dbPath = process.env.BETTER_AUTH_DB_PATH ?? "/app/data/docling_luna_auth.db";
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
const owners = [...new Set((config.owners ?? []).map(email => String(email).trim().toLowerCase()))];

if (!owners.length || owners.some(email => !email.includes("@"))) {
  throw new Error("feedback access config must contain valid owner emails");
}

const db = new Database(dbPath);
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

const initialize = db.transaction(() => {
  const existing = db.prepare("SELECT COUNT(*) AS count FROM feedback_access_by_email").get().count;
  if (existing === 0) {
    const insert = db.prepare("INSERT INTO feedback_access_by_email(email,role,granted_by_email,created_at,revoked_at) VALUES(?,'owner',NULL,?,NULL)");
    const now = new Date().toISOString();
    for (const email of owners) insert.run(email, now);
  }
  if (process.env.LOCAL_DEV_AUTH_BYPASS === "true") {
    db.prepare(`INSERT INTO feedback_access_by_email(email,role,granted_by_email,created_at,revoked_at)
      VALUES('local-dev@localhost','owner',NULL,?,NULL)
      ON CONFLICT(email) DO UPDATE SET role='owner',revoked_at=NULL`).run(new Date().toISOString());
  }
  db.prepare(`INSERT OR IGNORE INTO feedback_settings(key,value,updated_at,updated_by_email)
    VALUES('collection_enabled','true',?,NULL)`).run(new Date().toISOString());
});

initialize();
db.close();
console.log("feedback access initialized");
