#include "consumer/app.hpp"
#include "common/util.hpp"
#include "core/test_support.hpp"
#include <chrono>
#include <filesystem>
#include <iostream>
#include <thread>
namespace fs = std::filesystem;
int main() try {
  if (media::run_command({"ffmpeg", "-version"}, 5, true).exit_code != 0 ||
      media::run_command({"ffprobe", "-version"}, 5, true).exit_code != 0) {
    std::cout << "SKIP pipeline smoke test: could not run ffmpeg or ffprobe\n";
    return 77;
  }
  const media::test::TempDirectory fixture("media_pipeline_");
  const auto& root = fixture.path();
  const auto sample = root / "sample.mp4";
  const auto create = media::run_command({"ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15", "-t", "2",
    "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p",
    "-an", sample.string()}, 25);
  if (create.exit_code != 0) throw std::runtime_error("Could not generate synthetic test video");
  media::ConsumerConfig conf;
  conf.data_root = root / "storage";
  conf.consumers = 1; conf.queue_capacity = 2;
  conf.compress = true; conf.ffmpeg_timeout = 25;
  media::ConsumerApp app(conf);
  media::Video v;
  v.id = "testvideo1"; v.upload_id = "testupload1";
  v.producer_id = "producer_1"; v.original_filename = "sample.mp4";
  v.sha256 = media::sha256_hex("synthetic");
  v.state = "QUEUED"; v.temp_name = "testvideo1.part";
  v.original_size = fs::file_size(sample);
  fs::copy_file(sample, app.incoming() / v.temp_name);
  CHECK(app.database_.insert_queued(v));
  app.start_workers();
  CHECK(app.queue_.try_push(v));
  bool ready = false;
  for (int i = 0; i < 250; ++i) {
    const auto item = app.database_.by_id(v.id);
    if (item && item->state == "FAILED") throw std::runtime_error("Worker failed: " + item->error);
    if (item && item->state == "READY") { ready = true; break; }
    std::this_thread::sleep_for(std::chrono::milliseconds(40));
  }
  app.stop_workers();
  if (!ready) throw std::runtime_error("Worker never reached READY within deadline");
  CHECK(fs::file_size(app.uploads() / "testvideo1.mp4") > 0);
  CHECK(fs::file_size(app.previews() / "testvideo1.mp4") > 0);
  CHECK(fs::file_size(app.previews() / "testvideo1.jpg") > 0);
  const auto preview = media::run_command({"ffprobe", "-v", "error", "-show_entries",
    "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
    (app.previews() / "testvideo1.mp4").string()}, 10, true);
  CHECK(preview.exit_code == 0);
  const auto duration = std::stod(preview.stdout_text);
  CHECK(duration > 0.0 && duration <= 10.5);
  std::cout << "Media pipeline smoke passed; preview duration=" << duration << " seconds\n";
} catch (const std::exception& error) {
  std::cerr << "Media pipeline smoke failed: " << error.what() << '\n';
  return 1;
}
