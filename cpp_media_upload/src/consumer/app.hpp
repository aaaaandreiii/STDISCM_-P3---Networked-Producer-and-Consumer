#pragma once
#include "common/database.hpp"
#include "common/queue.hpp"
#include <atomic>
#include <cstddef>
#include <filesystem>
#include <mutex>
#include <semaphore>
#include <string>
#include <thread>
#include <vector>
namespace media {
struct ConsumerConfig {
  std::string grpc_bind = "0.0.0.0:50051";
  std::string http_host = "0.0.0.0";
  int http_port = 8080;
  std::filesystem::path data_root = "./data";
  std::filesystem::path web_root = "./web";
  std::size_t consumers = 2, queue_capacity = 5;
  int max_inflight = 8;
  std::uint64_t max_file_bytes = 512ULL * 1024 * 1024;
  bool compress = true;
  int ffmpeg_timeout = 240;
  int demo_worker_delay_ms = 0; // test/demo-only overload simulation
};
struct Metrics {
  std::atomic<int> active_uploads{0};
  std::atomic<int> active_workers{0};
  std::atomic<std::uint64_t> dropped{0};
  std::atomic<std::uint64_t> duplicates{0};
  std::atomic<std::uint64_t> accepted{0};
  std::atomic<std::uint64_t> failures{0};
};
class ConsumerApp {
 public:
  explicit ConsumerApp(ConsumerConfig config);
  ~ConsumerApp();
  void start_workers();
  void recover_unfinished();
  void stop_workers();
  const std::filesystem::path incoming() const { return config_.data_root / "incoming"; }
  const std::filesystem::path uploads() const { return config_.data_root / "uploads"; }
  const std::filesystem::path previews() const { return config_.data_root / "previews"; }
  ConsumerConfig config_;
  Database database_;
  BoundedQueue<Video> queue_;
  std::counting_semaphore<1024> upload_slots_;
  std::mutex admission_mutex_;
  Metrics metrics_;
 private:
  void worker_loop(std::size_t worker_id);
  void process_video(const Video& v, std::size_t worker_id);
  std::vector<std::jthread> workers_;
};
void log_line(const std::string& component, const std::string& message);
}
