#include "consumer/grpc_service.hpp"
#include "common/util.hpp"
#include <openssl/evp.h>
#include <array>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>
namespace fs = std::filesystem;
namespace proto = mediaupload::v1;
namespace media {
namespace {
struct UploadPermit {
  ConsumerApp& app;
  bool held = false;
  explicit UploadPermit(ConsumerApp& a) : app(a), held(a.upload_slots_.try_acquire()) {
    if (held) app.metrics_.active_uploads.fetch_add(1);
  }
  ~UploadPermit() {
    if (held) { app.metrics_.active_uploads.fetch_sub(1); app.upload_slots_.release(); }
  }
};
std::string to_hex(const unsigned char* data, unsigned n) {
  constexpr char digits[] = "0123456789abcdef";
  std::string result; result.reserve(n * 2);
  for (unsigned i = 0; i < n; ++i) { result += digits[data[i] >> 4]; result += digits[data[i] & 15]; }
  return result;
}
}
grpc::Status UploadService::UploadVideo(grpc::ServerContext* ctx,
    grpc::ServerReader<proto::UploadRequest>* reader, proto::UploadReply* reply) {
  UploadPermit permit(app_);
  if (!permit.held) {
    reply->set_result(proto::SERVER_BUSY); reply->set_message("Maximum concurrent incoming uploads reached");
    return grpc::Status::OK;
  }
  const auto reject = [&](proto::UploadResult result, const std::string& reason) {
    reply->set_result(result); reply->set_message(reason);
    return grpc::Status::OK;
  };
  proto::UploadRequest request;
  if (!reader->Read(&request) || !request.has_metadata())
    return reject(proto::INVALID_FILE, "First message must be metadata");
  const proto::UploadMetadata header = request.metadata();
  reply->set_upload_id(header.upload_id());
  if (!valid_token(header.upload_id()) || !valid_token(header.producer_id()) ||
      header.original_filename().empty() || header.original_filename().size() > 1024 ||
      header.total_size_bytes() == 0 || header.total_size_bytes() > app_.config_.max_file_bytes)
    return reject(proto::INVALID_FILE, "Invalid metadata, zero size, or exceeds maximum allowed upload");
  const std::string id = random_hex();
  const std::string temp_name = id + ".part";
  const fs::path path = app_.incoming() / temp_name;
  const auto reject_transfer = [&](proto::UploadResult result, const std::exception& error) {
    std::error_code ec;
    fs::remove(path, ec);
    log_line("receiver", "rejected upload=" + header.upload_id() + " error=" + error.what());
    return reject(result, error.what());
  };
  std::uint64_t received = 0;
  unsigned char digest[EVP_MAX_MD_SIZE]{}; unsigned digest_len = 0;
  std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> hash(EVP_MD_CTX_new(), &EVP_MD_CTX_free);
  if (!hash || EVP_DigestInit_ex(hash.get(), EVP_sha256(), nullptr) != 1)
    return grpc::Status(grpc::StatusCode::INTERNAL, "SHA-256 initialization failed");
  try {
    {
      std::ofstream output(path, std::ios::binary | std::ios::trunc);
      if (!output) throw std::runtime_error("Cannot create temporary file");
      while (reader->Read(&request)) {
        if (ctx->IsCancelled()) throw std::invalid_argument("Client cancelled upload");
        if (!request.has_chunk()) throw std::invalid_argument("Unexpected metadata or missing chunk");
        const auto& chunk = request.chunk();
        if (chunk.empty() || chunk.size() > 256 * 1024 ||
            received + chunk.size() > header.total_size_bytes() ||
            received + chunk.size() > app_.config_.max_file_bytes)
          throw std::invalid_argument("Chunk invalid or declared file size exceeded");
        output.write(chunk.data(), static_cast<std::streamsize>(chunk.size()));
        if (!output || EVP_DigestUpdate(hash.get(), chunk.data(), chunk.size()) != 1)
          throw std::runtime_error("Write or SHA-256 failed");
        received += chunk.size();
      }
      output.flush();
      if (!output) throw std::runtime_error("Temporary file flush failed");
    }
    if (ctx->IsCancelled()) throw std::invalid_argument("Upload interrupted by client");
    if (received != header.total_size_bytes()) throw std::invalid_argument("Received bytes do not match declared size");
    if (EVP_DigestFinal_ex(hash.get(), digest, &digest_len) != 1)
      throw std::runtime_error("Final SHA-256 failed");
    const std::string sha = to_hex(digest, digest_len);
    // Serialize all admissions: idempotency, duplicate checks, queue slot check,
    // DB insert, and publication of the descriptor to the queue.
    std::lock_guard admission(app_.admission_mutex_);
    if (auto previous = app_.database_.by_upload_id(header.upload_id())) {
      reply->set_result(proto::ALREADY_ACCEPTED);
      reply->set_video_id(previous->id);
      reply->set_message("Upload id already recorded, state=" + previous->state);
    } else if (auto match = app_.database_.by_hash(sha)) {
      reply->set_result(proto::DUPLICATE); reply->set_video_id(match->id);
      reply->set_message("Byte-identical content already accepted (SHA-256)");
      app_.metrics_.duplicates.fetch_add(1);
    } else if (!app_.queue_.has_room()) {
      reply->set_result(proto::QUEUE_FULL); reply->set_message("Waiting queue is full; incoming video dropped");
      app_.metrics_.dropped.fetch_add(1);
    } else {
      Video v;
      v.id = id; v.upload_id = header.upload_id(); v.producer_id = header.producer_id();
      v.original_filename = safe_filename(header.original_filename()); v.sha256 = sha;
      v.original_size = received; v.temp_name = temp_name; v.state = "QUEUED";
      if (!app_.database_.insert_queued(v)) {
        reply->set_result(proto::DUPLICATE);
        reply->set_message("Concurrent uniqueness conflict; retry or check status");
        app_.metrics_.duplicates.fetch_add(1);
      } else if (!app_.queue_.try_push(v)) {
        // With admission mutex held, only consumers can change queue depth;
        // they only remove items. This should be unreachable except shutdown.
        app_.database_.mark_failed(v.id, "Service shut down during queue insertion");
        reply->set_result(proto::SERVER_ERROR);
        reply->set_message("Service shutting down");
      } else {
        reply->set_result(proto::QUEUED); reply->set_video_id(v.id);
        reply->set_message("Upload accepted for background processing");
        app_.metrics_.accepted.fetch_add(1);
        log_line("admission", "QUEUED video=" + v.id + " producer=" + v.producer_id +
          " queue_depth=" + std::to_string(app_.queue_.size()));
      }
    }
    reply->set_queue_depth(static_cast<std::uint32_t>(app_.queue_.size()));
    if (reply->result() != proto::QUEUED) fs::remove(path);
    return grpc::Status::OK;
  } catch (const std::invalid_argument& error) {
    return reject_transfer(proto::INVALID_FILE, error);
  } catch (const std::exception& error) {
    return reject_transfer(proto::SERVER_ERROR, error);
  }
}
grpc::Status UploadService::GetUploadStatus(grpc::ServerContext*,
    const proto::StatusRequest* req, proto::StatusReply* reply) {
  if (!valid_token(req->upload_id())) return grpc::Status(grpc::StatusCode::INVALID_ARGUMENT, "Invalid upload ID");
  try {
    const auto item = app_.database_.by_upload_id(req->upload_id());
    reply->set_found(item.has_value());
    if (item) { reply->set_video_id(item->id); reply->set_state(item->state); reply->set_message(item->error); }
    return grpc::Status::OK;
  } catch (const std::exception& e) { return grpc::Status(grpc::StatusCode::INTERNAL, e.what()); }
}
grpc::Status UploadService::Health(grpc::ServerContext*,
    const proto::HealthRequest*, proto::HealthReply* reply) {
  reply->set_healthy(true); reply->set_service("media-upload-consumer");
  return grpc::Status::OK;
}
}
