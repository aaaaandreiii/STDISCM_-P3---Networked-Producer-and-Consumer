#include "consumer/app.hpp"
#include "common/util.hpp"
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <syncstream>
#include <thread>
#include <unordered_set>
namespace fs = std::filesystem;
namespace media {
void log_line(const std::string& component, const std::string& message) {
  std::osyncstream(std::cout) << utc_now() << " [" << component << "] " << message << '\n';
}
ConsumerApp::ConsumerApp(ConsumerConfig config)
  : config_(std::move(config)),
    database_((fs::create_directories(config_.data_root), config_.data_root / "metadata.db")),
    queue_(config_.queue_capacity), upload_slots_(config_.max_inflight) {
  fs::create_directories(incoming());
  fs::create_directories(uploads());
  fs::create_directories(previews());
}
ConsumerApp::~ConsumerApp() { stop_workers(); }
void ConsumerApp::start_workers() {
  for (std::size_t i = 0; i < config_.consumers; ++i)
    workers_.emplace_back([this, i] { worker_loop(i + 1); });
}
void ConsumerApp::recover_unfinished() {
  const auto unfinished = database_.unfinished_videos();
  std::unordered_set<std::string> pending_parts;
  for (const Video& v : unfinished) pending_parts.insert(v.temp_name);

  // Startup runs before gRPC listens. A generated .part outside the pending
  // rows cannot be resumed after a crash and no receiver is still writing it.
  try {
    for (const auto& entry : fs::directory_iterator(incoming())) {
      const auto name = entry.path().filename().string();
      if (name.size() != 37 || !name.ends_with(".part") ||
          name.find_first_not_of("0123456789abcdef") != 32 || pending_parts.contains(name) ||
          !fs::is_regular_file(entry.symlink_status()))
        continue;
      std::error_code error;
      if (fs::remove(entry.path(), error))
        log_line("recovery", "removed unreferenced upload temp=" + name);
      else if (error)
        log_line("recovery", "cannot remove upload temp=" + name + " error=" + error.message());
    }
  } catch (const fs::filesystem_error& error) {
    log_line("recovery", "cannot scan incoming upload temps: " + std::string(error.what()));
  }

  for (const Video& v : unfinished) {
    const fs::path final_path = uploads() / (v.id + ".mp4");
    const fs::path preview_path = previews() / (v.id + ".mp4");
    const fs::path thumb_path = previews() / (v.id + ".jpg");
    try {
      if (fs::exists(final_path) && fs::exists(preview_path) && fs::exists(thumb_path)) {
        database_.mark_ready(v.id, file_bytes(final_path), v.compressed);
        log_line("recovery", "completed already-published video=" + v.id);
      } else if (fs::exists(incoming() / v.temp_name)) {
        // Previously accepted jobs are requeued, not dropped after restart.
        // Workers are already running, so the queue can be drained while we wait.
        fs::remove(final_path); fs::remove(preview_path); fs::remove(thumb_path);
        while (!queue_.try_push(v)) std::this_thread::sleep_for(std::chrono::milliseconds(40));
        log_line("recovery", "requeued video=" + v.id);
      } else {
        database_.mark_failed(v.id, "Recovery: missing original temporary file");
        log_line("recovery", "missing temporary input video=" + v.id);
      }
    } catch (const std::exception& e) {
      log_line("recovery", "error video=" + v.id + " message=" + e.what());
    }
  }
}
void ConsumerApp::stop_workers() {
  queue_.close();
  workers_.clear(); // jthread joins on destruction
}
void ConsumerApp::worker_loop(std::size_t worker_id) {
  log_line("worker", "started worker=" + std::to_string(worker_id));
  while (const auto job = queue_.pop()) {
    metrics_.active_workers.fetch_add(1);
    log_line("worker", "dequeued worker=" + std::to_string(worker_id) + " video=" + job->id +
      " remaining=" + std::to_string(queue_.size()));
    try {
      database_.mark_processing(job->id);
      if (config_.demo_worker_delay_ms > 0)
        std::this_thread::sleep_for(std::chrono::milliseconds(config_.demo_worker_delay_ms));
      process_video(*job, worker_id);
    } catch (const std::exception& e) {
      try { database_.mark_failed(job->id, e.what()); } catch (...) {}
      metrics_.failures.fetch_add(1);
      { std::error_code ec; fs::remove(incoming() / job->temp_name, ec); }
      log_line("worker", "FAILED video=" + job->id + " error=" + e.what());
    }
    metrics_.active_workers.fetch_sub(1);
  }
  log_line("worker", "stopped worker=" + std::to_string(worker_id));
}
void ConsumerApp::process_video(const Video& v, std::size_t worker_id) {
  const auto input = incoming() / v.temp_name;
  const auto transcode = incoming() / (v.id + ".transcoded.mp4");
  const auto thumb_temp = incoming() / (v.id + ".thumbnail.jpg");
  const auto preview_temp = incoming() / (v.id + ".preview.mp4");
  const auto final = uploads() / (v.id + ".mp4");
  const auto final_stage = incoming() / (v.id + ".publish.mp4");
  const auto thumb_final = previews() / (v.id + ".jpg");
  const auto preview_final = previews() / (v.id + ".mp4");
  auto cleanup_intermediates = [&] {
    std::error_code ec; fs::remove(transcode, ec); fs::remove(thumb_temp, ec); fs::remove(preview_temp, ec); fs::remove(final_stage, ec);
  };
  cleanup_intermediates();
  try {
    // ffprobe checks that the uploaded data actually has a decodable video stream.
    auto probe = run_command({"ffprobe", "-v", "error", "-select_streams", "v:0",
      "-show_entries", "stream=codec_name", "-of", "default=nokey=1:noprint_wrappers=1",
      input.string()}, 30, true);
    if (probe.exit_code != 0 || probe.stdout_text.empty()) throw std::runtime_error("No valid video stream");
    std::string codec = probe.stdout_text;
    codec.erase(codec.find_last_not_of("\r\n \t") + 1);
    auto audio = run_command({"ffprobe", "-v", "error", "-select_streams", "a:0",
      "-show_entries", "stream=codec_name", "-of", "default=nokey=1:noprint_wrappers=1",
      input.string()}, 30, true);
    std::string audio_codec = audio.stdout_text;
    if (!audio_codec.empty()) audio_codec.erase(audio_codec.find_last_not_of("\r\n \t") + 1);
    std::string ext = fs::path(v.original_filename).extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c){return std::tolower(c);});
    const bool browser_compatible = ext == ".mp4" && codec == "h264" &&
      (audio_codec.empty() || audio_codec == "aac");
    fs::path selected = input;
    bool actually_compressed = false;
    if (config_.compress) {
      auto result = run_command({"ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", input.string(), "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-threads", "1", "-preset", "veryfast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", transcode.string()}, config_.ffmpeg_timeout);
      if (result.exit_code == 0 && fs::exists(transcode) && file_bytes(transcode) > 0) {
        if (!browser_compatible || file_bytes(transcode) < file_bytes(input)) {
          selected = transcode;
          actually_compressed = true;
        }
      } else if (!browser_compatible) {
        throw std::runtime_error("Conversion failed and original is not browser-compatible");
      }
    } else if (!browser_compatible) {
      throw std::runtime_error("Compression disabled: requires MP4/H.264 with AAC or no audio");
    }
    const auto thumbnail = run_command({"ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
      "-i", selected.string(), "-frames:v", "1", "-vf", "scale=480:-2", thumb_temp.string()}, config_.ffmpeg_timeout);
    if (thumbnail.exit_code != 0 || !fs::exists(thumb_temp) || file_bytes(thumb_temp) == 0)
      throw std::runtime_error("Thumbnail generation failed");
    const auto preview = run_command({"ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
      "-i", selected.string(), "-t", "10", "-an", "-vf", "scale=640:-2",
      "-c:v", "libx264", "-threads", "1", "-preset", "veryfast", "-crf", "30",
      "-pix_fmt", "yuv420p", "-movflags", "+faststart", preview_temp.string()}, config_.ffmpeg_timeout);
    if (preview.exit_code != 0 || !fs::exists(preview_temp) || file_bytes(preview_temp) == 0)
      throw std::runtime_error("Preview generation failed");
    // All files live under one storage root, so rename of each completed asset
    // is atomic. The database transitions to READY only after all are present.
    fs::remove(final); fs::remove(thumb_final); fs::remove(preview_final);
    fs::rename(thumb_temp, thumb_final);
    fs::rename(preview_temp, preview_final);
    fs::copy_file(selected, final_stage, fs::copy_options::overwrite_existing);
    fs::rename(final_stage, final);
    const auto published_size = file_bytes(final);
    database_.mark_ready(v.id, published_size, actually_compressed);
    cleanup_intermediates();
    { std::error_code ec; fs::remove(input, ec); }
    log_line("worker", "READY worker=" + std::to_string(worker_id) + " video=" + v.id +
      " compressed=" + (actually_compressed ? "true" : "false") +
      " output_bytes=" + std::to_string(published_size));
  } catch (...) {
    cleanup_intermediates();
    std::error_code ec;
    fs::remove(final, ec); fs::remove(thumb_final, ec); fs::remove(preview_final, ec);
    // Leave original temp file for startup recovery or forensic inspection.
    throw;
  }
}
}
