#include "common/database.hpp"
#include <sqlite3.h>
#include <stdexcept>
#include <string>
#include <vector>
namespace media {
namespace {
struct Statement {
  sqlite3_stmt* s = nullptr;
  Statement(sqlite3* db, const char* sql) {
    if (sqlite3_prepare_v2(db, sql, -1, &s, nullptr) != SQLITE_OK)
      throw std::runtime_error(sqlite3_errmsg(db));
  }
  ~Statement() { sqlite3_finalize(s); }
  void text(int col, const std::string& val) { sqlite3_bind_text(s, col, val.c_str(), -1, SQLITE_TRANSIENT); }
  void integer(int col, std::int64_t val) { sqlite3_bind_int64(s, col, val); }
};
void exec(sqlite3* db, const char* sql) {
  char* err = nullptr; if (sqlite3_exec(db, sql, nullptr, nullptr, &err) != SQLITE_OK) {
    std::string message = err ? err : "SQLite error"; sqlite3_free(err);
    throw std::runtime_error(message);
  }
}
std::string cell(sqlite3_stmt* s, int i) {
  const auto* p = sqlite3_column_text(s, i);
  return p ? reinterpret_cast<const char*>(p) : "";
}
Video from_row(sqlite3_stmt* s) {
  Video v;
  v.id = cell(s, 0); v.upload_id = cell(s, 1); v.producer_id = cell(s, 2);
  v.original_filename = cell(s, 3); v.sha256 = cell(s, 4); v.state = cell(s, 5);
  v.error = cell(s, 6); v.temp_name = cell(s, 7);
  v.original_size = static_cast<std::uint64_t>(sqlite3_column_int64(s, 8));
  v.final_size = static_cast<std::uint64_t>(sqlite3_column_int64(s, 9));
  v.compressed = sqlite3_column_int(s, 10) != 0;
  v.created_at = cell(s, 11);
  return v;
}
constexpr const char* cols =
  "id,upload_id,producer_id,original_filename,sha256,state,error,temp_name,original_size,final_size,compressed,created_at";
}
Database::Database(const std::filesystem::path& file) {
  if (sqlite3_open_v2(file.c_str(), &db_, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX, nullptr) != SQLITE_OK) {
    std::string err = db_ ? sqlite3_errmsg(db_) : "database open failed";
    if (db_) sqlite3_close(db_);
    db_ = nullptr; throw std::runtime_error(err);
  }
  try {
    sqlite3_busy_timeout(db_, 5000);
    exec(db_, "PRAGMA foreign_keys=ON;");
    exec(db_, "CREATE TABLE IF NOT EXISTS videos("
        "id TEXT PRIMARY KEY, upload_id TEXT NOT NULL UNIQUE, producer_id TEXT NOT NULL,"
        "original_filename TEXT NOT NULL, sha256 TEXT NOT NULL,"
        "state TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', temp_name TEXT NOT NULL,"
        "original_size INTEGER NOT NULL, final_size INTEGER NOT NULL DEFAULT 0,"
        "compressed INTEGER NOT NULL DEFAULT 0,"
        "created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));");
    exec(db_, "CREATE INDEX IF NOT EXISTS idx_videos_ready ON videos(state,created_at DESC);");
    exec(db_, "CREATE UNIQUE INDEX IF NOT EXISTS idx_sha_active ON videos(sha256) WHERE state IN ('QUEUED','PROCESSING','READY');");
  } catch (...) { sqlite3_close(db_); db_ = nullptr; throw; }
}
Database::~Database() { if (db_) sqlite3_close(db_); }
std::optional<Video> Database::find_one_locked(const char* sql, const std::string& value) {
  Statement st(db_, sql); st.text(1, value);
  const int rc = sqlite3_step(st.s);
  if (rc == SQLITE_ROW) return from_row(st.s);
  if (rc != SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
  return std::nullopt;
}
std::optional<Video> Database::by_upload_id(const std::string& id) {
  std::lock_guard lock(mutex_);
  return find_one_locked("SELECT id,upload_id,producer_id,original_filename,sha256,state,error,temp_name,original_size,final_size,compressed,created_at FROM videos WHERE upload_id=?", id);
}
std::optional<Video> Database::by_hash(const std::string& hash) {
  std::lock_guard lock(mutex_);
  return find_one_locked("SELECT id,upload_id,producer_id,original_filename,sha256,state,error,temp_name,original_size,final_size,compressed,created_at FROM videos WHERE sha256=? AND state IN ('QUEUED','PROCESSING','READY')", hash);
}
std::optional<Video> Database::by_id(const std::string& id) {
  std::lock_guard lock(mutex_);
  return find_one_locked("SELECT id,upload_id,producer_id,original_filename,sha256,state,error,temp_name,original_size,final_size,compressed,created_at FROM videos WHERE id=?", id);
}
std::vector<Video> Database::ready_videos(int limit) {
  std::lock_guard lock(mutex_);
  Statement st(db_, "SELECT id,upload_id,producer_id,original_filename,sha256,state,error,temp_name,original_size,final_size,compressed,created_at FROM videos WHERE state='READY' ORDER BY created_at DESC, id DESC LIMIT ?");
  st.integer(1, limit);
  std::vector<Video> out;
  int rc;
  while ((rc = sqlite3_step(st.s)) == SQLITE_ROW) out.push_back(from_row(st.s));
  if (rc != SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
  return out;
}
std::vector<Video> Database::unfinished_videos() {
  std::lock_guard lock(mutex_);
  Statement st(db_, "SELECT id,upload_id,producer_id,original_filename,sha256,state,error,temp_name,original_size,final_size,compressed,created_at FROM videos WHERE state IN ('QUEUED','PROCESSING') ORDER BY created_at, id");
  std::vector<Video> out; int rc;
  while ((rc = sqlite3_step(st.s)) == SQLITE_ROW) out.push_back(from_row(st.s));
  if (rc != SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
  return out;
}
bool Database::insert_queued(const Video& v) {
  std::lock_guard lock(mutex_);
  Statement st(db_, "INSERT INTO videos (id,upload_id,producer_id,original_filename,sha256,state,error,temp_name,original_size) VALUES (?,?,?,?,?,'QUEUED','',?,?)");
  st.text(1,v.id); st.text(2,v.upload_id); st.text(3,v.producer_id);
  st.text(4,v.original_filename); st.text(5,v.sha256); st.text(6,v.temp_name);
  st.integer(7,static_cast<std::int64_t>(v.original_size));
  const int rc=sqlite3_step(st.s);
  if (rc == SQLITE_DONE) return true;
  if (rc == SQLITE_CONSTRAINT || rc == SQLITE_CONSTRAINT_UNIQUE || rc == SQLITE_CONSTRAINT_PRIMARYKEY) return false;
  throw std::runtime_error(sqlite3_errmsg(db_));
}
void Database::mark_processing(const std::string& id) {
  std::lock_guard lock(mutex_);
  Statement st(db_, "UPDATE videos SET state='PROCESSING' WHERE id=?"); st.text(1,id);
  if (sqlite3_step(st.s)!=SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
}
void Database::mark_ready(const std::string& id, std::uint64_t bytes, bool compressed) {
  std::lock_guard lock(mutex_);
  Statement st(db_, "UPDATE videos SET state='READY',error='',final_size=?,compressed=? WHERE id=?");
  st.integer(1,static_cast<std::int64_t>(bytes)); st.integer(2,compressed?1:0); st.text(3,id);
  if (sqlite3_step(st.s)!=SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
}
void Database::mark_failed(const std::string& id, const std::string& error) {
  std::lock_guard lock(mutex_);
  Statement st(db_, "UPDATE videos SET state='FAILED',error=? WHERE id=?"); st.text(1,error); st.text(2,id);
  if (sqlite3_step(st.s)!=SQLITE_DONE) throw std::runtime_error(sqlite3_errmsg(db_));
}
std::int64_t Database::count_state(const std::string& state) {
  std::lock_guard lock(mutex_);
  Statement st(db_, "SELECT COUNT(*) FROM videos WHERE state=?"); st.text(1,state);
  if (sqlite3_step(st.s)==SQLITE_ROW) return sqlite3_column_int64(st.s,0);
  throw std::runtime_error(sqlite3_errmsg(db_));
}
}
