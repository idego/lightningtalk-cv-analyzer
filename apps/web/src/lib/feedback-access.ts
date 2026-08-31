import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";

export type FeedbackRole = "owner" | "reviewer";
const dbPath = process.env.BETTER_AUTH_DB_PATH ?? "./data/auth.db";

function database() {
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  const db = new Database(dbPath);
  db.exec(`CREATE TABLE IF NOT EXISTS feedback_access (
    user_id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('owner','reviewer')),
    granted_by_user_id TEXT, created_at TEXT NOT NULL, revoked_at TEXT,
    FOREIGN KEY(user_id) REFERENCES user(id), FOREIGN KEY(granted_by_user_id) REFERENCES user(id)
  ); CREATE INDEX IF NOT EXISTS feedback_access_active_role ON feedback_access(revoked_at, role);`);
  return db;
}

export function feedbackRole(userId: string): FeedbackRole | null {
  const db = database();
  try {
    const row = db.prepare("SELECT role FROM feedback_access WHERE user_id=? AND revoked_at IS NULL").get(userId) as { role: FeedbackRole } | undefined;
    return row?.role ?? null;
  } finally { db.close(); }
}

export function listFeedbackMembers() {
  const db = database();
  try {
    return db.prepare(`SELECT a.user_id AS userId,a.role,u.email,u.name,a.created_at AS createdAt
      FROM feedback_access a JOIN user u ON u.id=a.user_id WHERE a.revoked_at IS NULL ORDER BY a.role,u.email`).all();
  } finally { db.close(); }
}

export function grantFeedbackAccess(email: string, role: FeedbackRole, grantedBy: string) {
  const normalized = email.trim().toLowerCase();
  const db = database();
  try {
    const user = db.prepare("SELECT id FROM user WHERE lower(email)=? AND emailVerified=1").get(normalized) as { id: string } | undefined;
    if (!user) throw new Error("verified_user_not_found");
    db.prepare(`INSERT INTO feedback_access(user_id,role,granted_by_user_id,created_at,revoked_at) VALUES(?,?,?,?,NULL)
      ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,granted_by_user_id=excluded.granted_by_user_id,revoked_at=NULL`).run(user.id, role, grantedBy, new Date().toISOString());
    return user.id;
  } finally { db.close(); }
}

export function revokeFeedbackAccess(userId: string) {
  const db = database();
  try {
    const member = db.prepare("SELECT role FROM feedback_access WHERE user_id=? AND revoked_at IS NULL").get(userId) as { role: FeedbackRole } | undefined;
    if (!member) return false;
    if (member.role === "owner") {
      const count = (db.prepare("SELECT COUNT(*) count FROM feedback_access WHERE role='owner' AND revoked_at IS NULL").get() as { count: number }).count;
      if (count <= 1) throw new Error("last_owner_protected");
    }
    db.prepare("UPDATE feedback_access SET revoked_at=? WHERE user_id=?").run(new Date().toISOString(), userId);
    return true;
  } finally { db.close(); }
}

export function bootstrapFeedbackOwner(email: string) {
  const db = database();
  try {
    const user = db.prepare("SELECT id FROM user WHERE lower(email)=? AND emailVerified=1").get(email.trim().toLowerCase()) as { id: string } | undefined;
    if (!user) throw new Error("verified_user_not_found");
    db.prepare(`INSERT INTO feedback_access(user_id,role,granted_by_user_id,created_at,revoked_at) VALUES(?,'owner',?, ?,NULL)
      ON CONFLICT(user_id) DO UPDATE SET role='owner',revoked_at=NULL`).run(user.id, user.id, new Date().toISOString());
  } finally { db.close(); }
}
