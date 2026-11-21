#pragma once
#include <cstdint>
#include <filesystem>
#include <mutex>
#include <optional>
#include <string>
#include <vector>
struct sqlite3;
namespace media {
struct Video {
  std::string id, upload_id, producer_id, original_filename, sha256, state;
  std::string error, temp_name, created_at;
  std::uint64_t original_size = 0, final_size = 0;
  bool compressed = false;
};
class Database {
 public:
  explicit Database(const std::filesystem::path& db_file);
  ~Database();
  Database(const Database&) = delete;
  Database& operator=(const Database&) = delete;
  std::optional<Video> by_upload_id(const std::string& upload_id);
  std::optional<Video> by_hash(const std::string& hash);
  std::optional<Video> by_id(const std::string& id);
  std::vector<Video> ready_videos(int limit = 200);
  std::vector<Video> unfinished_videos();
  // Returns false for UNIQUE constraints only; throws for other DB errors.
  bool insert_queued(const Video& video);
  void mark_processing(const std::string& id);
  void mark_ready(const std::string& id, std::uint64_t final_size, bool compressed);
  void mark_failed(const std::string& id, const std::string& error);
  std::int64_t count_state(const std::string& state);
 private:
  std::optional<Video> find_one_locked(const char* sql, const std::string& value);
  sqlite3* db_ = nullptr;
  std::mutex mutex_;
};
}
