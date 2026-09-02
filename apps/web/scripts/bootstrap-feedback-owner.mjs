import Database from "better-sqlite3";

const email = process.argv[2]?.trim().toLowerCase();
if (!email) throw new Error("usage: pnpm feedback:bootstrap-owner user@example.com");
const db = new Database(process.env.BETTER_AUTH_DB_PATH ?? "./data/auth.db");
db.exec(`CREATE TABLE IF NOT EXISTS feedback_access (user_id TEXT PRIMARY KEY,role TEXT NOT NULL CHECK(role IN ('owner','reviewer')),granted_by_user_id TEXT,created_at TEXT NOT NULL,revoked_at TEXT)`);
const user = db.prepare("SELECT id FROM user WHERE lower(email)=? AND emailVerified=1").get(email);
if (!user) throw new Error("verified_user_not_found");
db.prepare(`INSERT INTO feedback_access VALUES(?,'owner',?,?,NULL) ON CONFLICT(user_id) DO UPDATE SET role='owner',revoked_at=NULL`).run(user.id,user.id,new Date().toISOString());
db.close();
console.log("feedback owner bootstrapped");
