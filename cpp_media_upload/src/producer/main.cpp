#include "common/util.hpp"
#include "media.grpc.pb.h"
#include <grpcpp/grpcpp.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <syncstream>
#include <thread>
#include <vector>
namespace fs = std::filesystem;
namespace proto = mediaupload::v1;
namespace {
struct ProducerConfig {
  std::string server = "127.0.0.1:50051";
  fs::path source_root = "./samples";
  std::size_t p = 2;
  std::size_t chunk_bytes = 64 * 1024;
  int deadline_seconds = 1800;
};
void usage() {
  std::cout << "Usage: media_producer [options]\n"
    "  --p N                Producer thread count (default 2)\n"
    "  --source-root PATH   Folders producer_1 ... producer_p (default ./samples)\n"
    "  --server HOST:PORT   Consumer gRPC endpoint (default 127.0.0.1:50051)\n"
    "  --chunk-kb N         Upload chunk KiB, 1..256 (default 64)\n"
    "  --deadline-sec N     Deadline per upload (default 1800)\n";
}
ProducerConfig options(int argc, char** argv) {
  ProducerConfig config;
  for (int i = 1; i < argc; ++i) {
    const std::string flag(argv[i]);
    if (flag == "--help") { usage(); std::exit(0); }
    if (i+1 >= argc) throw std::invalid_argument("Missing value for " + flag);
    const std::string val(argv[++i]);
    if (flag == "--p") config.p = std::stoul(val);
    else if (flag == "--source-root") config.source_root = val;
    else if (flag == "--server") config.server = val;
    else if (flag == "--chunk-kb") config.chunk_bytes = std::stoul(val) * 1024;
    else if (flag == "--deadline-sec") config.deadline_seconds = std::stoi(val);
    else throw std::invalid_argument("Unknown option " + flag);
  }
  if (config.p < 1 || config.p > 64 || config.chunk_bytes < 1024 || config.chunk_bytes > 256*1024 || config.deadline_seconds < 1)
    throw std::invalid_argument("Invalid p, chunk size or deadline");
  return config;
}
void log(const std::string& worker, const std::string& message) {
  std::osyncstream(std::cout) << media::utc_now() << " [" << worker << "] " << message << '\n';
}
bool video_extension(const fs::path& file) {
  std::string ext = file.extension().string();
  std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c) { return std::tolower(c); });
  return ext == ".mp4" || ext == ".mkv" || ext == ".mov" || ext == ".webm";
}
void upload_one(const ProducerConfig& cfg, proto::MediaUploadService::Stub& client,
                const std::string& producer_id, const fs::path& path) {
  const auto bytes = fs::file_size(path);
  if (bytes == 0) { log(producer_id, "skipping empty file " + path.string()); return; }
  // Deterministic logical id: if an RPC reply is lost and the program is run
  // again on the SAME unchanged source file, status lookup avoids a blind retry.
  const auto canonical = fs::weakly_canonical(path).string();
  const auto mtime = fs::last_write_time(path).time_since_epoch().count();
  const std::string logical = media::sha256_hex(producer_id + "|" + canonical + "|" +
    std::to_string(bytes) + "|" + std::to_string(mtime));
  std::string upload_id = logical;
  {
    grpc::ClientContext status_ctx;
    status_ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(10));
    proto::StatusRequest request; request.set_upload_id(upload_id);
    proto::StatusReply reply;
    auto result = client.GetUploadStatus(&status_ctx, request, &reply);
    if (result.ok() && reply.found()) {
      if (reply.state() != "FAILED") {
        log(producer_id, "already recorded " + path.filename().string() +
          " state=" + reply.state() + " video=" + reply.video_id());
        return;
      }
      // Failed attempts release their hash claims. Use a different per-run
      // attempt id so the failed historical record remains available.
      upload_id = media::sha256_hex(logical + "|retry|" + media::random_hex());
    }
  }
  std::ifstream input(path, std::ios::binary);
  if (!input) throw std::runtime_error("Cannot read source file: " + path.string());
  grpc::ClientContext context;
  context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(cfg.deadline_seconds));
  proto::UploadReply result;
  std::unique_ptr<grpc::ClientWriter<proto::UploadRequest>> stream(client.UploadVideo(&context, &result));
  proto::UploadRequest header;
  auto* meta = header.mutable_metadata();
  meta->set_upload_id(upload_id); meta->set_producer_id(producer_id);
  meta->set_original_filename(path.filename().string()); meta->set_total_size_bytes(bytes);
  bool wrote = stream->Write(header);
  std::vector<char> buffer(cfg.chunk_bytes);
  std::uint64_t sent = 0;
  while (wrote && input) {
    input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const auto count = input.gcount();
    if (count <= 0) break;
    proto::UploadRequest packet;
    packet.set_chunk(buffer.data(), static_cast<std::size_t>(count));
    wrote = stream->Write(packet);
    if (wrote) sent += static_cast<std::uint64_t>(count);
  }
  stream->WritesDone();
  const auto grpc_status = stream->Finish();
  if (!grpc_status.ok()) {
    log(producer_id, "gRPC FAILED file=" + path.filename().string() +
      " status=" + grpc_status.error_message());
  } else {
    log(producer_id, "upload file=" + path.filename().string() +
      " bytes_sent=" + std::to_string(sent) +
      " result=" + proto::UploadResult_Name(result.result()) +
      " video=" + result.video_id() + " queue_depth=" + std::to_string(result.queue_depth()) +
      " message=" + result.message());
  }
}
void producer_worker(const ProducerConfig& cfg, std::size_t number,
                     const std::shared_ptr<grpc::Channel>& channel) {
  const auto id = "producer_" + std::to_string(number);
  const auto folder = cfg.source_root / id;
  if (!fs::exists(folder) || !fs::is_directory(folder)) {
    log(id, "folder missing/not a directory: " + folder.string()); return;
  }
  auto stub = proto::MediaUploadService::NewStub(channel);
  std::vector<fs::path> files;
  for (const auto& entry : fs::directory_iterator(folder))
    if (entry.is_regular_file() && video_extension(entry.path())) files.push_back(entry.path());
  std::sort(files.begin(), files.end());
  log(id, "started folder=" + folder.string() + " video_count=" + std::to_string(files.size()));
  for (const auto& file : files) {
    try { upload_one(cfg, *stub, id, file); }
    catch (const std::exception& e) { log(id, "FAILED " + file.string() + " error=" + e.what()); }
  }
  log(id, "finished");
}
}
int main(int argc, char** argv) {
  try {
    const auto config = options(argc, argv);
    log("main", "p=" + std::to_string(config.p) + " server=" + config.server +
      " source_root=" + config.source_root.string());
    auto channel = grpc::CreateChannel(config.server, grpc::InsecureChannelCredentials());
    std::vector<std::jthread> threads;
    for (std::size_t i = 1; i <= config.p; ++i)
      threads.emplace_back([&, i] { producer_worker(config, i, channel); });
    threads.clear(); // joins all producer threads
    log("main", "all producers finished");
  } catch (const std::exception& e) {
    std::cerr << "Producer error: " << e.what() << '\n'; return 1;
  }
}
