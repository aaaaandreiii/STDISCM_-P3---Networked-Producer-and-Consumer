#include "consumer/http.hpp"
#include "common/util.hpp"
#include <drogon/drogon.h>
#include <json/json.h>
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <optional>
#include <string>
namespace fs = std::filesystem;
namespace media {
namespace {
using Callback = std::function<void(const drogon::HttpResponsePtr&)>;
drogon::HttpResponsePtr json_response(const Json::Value& value) {
  auto result = drogon::HttpResponse::newHttpJsonResponse(value);
  result->addHeader("Cache-Control", "no-store");
  return result;
}
drogon::HttpResponsePtr failure(drogon::HttpStatusCode status, const std::string& message) {
  Json::Value payload; payload["error"] = message;
  auto resp = json_response(payload); resp->setStatusCode(status); return resp;
}
Json::Value video_json(const Video& video) {
  Json::Value out;
  out["id"] = video.id;
  out["filename"] = video.original_filename;
  out["producer"] = video.producer_id;
  out["status"] = video.state;
  out["original_bytes"] = static_cast<Json::UInt64>(video.original_size);
  out["final_bytes"] = static_cast<Json::UInt64>(video.final_size);
  out["compressed"] = video.compressed;
  out["uploaded_at"] = video.created_at;
  out["thumbnail_url"] = "/api/videos/" + video.id + "/thumbnail";
  out["preview_url"] = "/api/videos/" + video.id + "/preview";
  out["stream_url"] = "/api/videos/" + video.id + "/stream";
  return out;
}
struct ByteRange { std::uint64_t start, end; };
std::optional<ByteRange> parse_range(const std::string& text, std::uint64_t size) {
  if (size == 0 || text.rfind("bytes=", 0) != 0) return std::nullopt;
  const std::string spec = text.substr(6);
  if (spec.empty() || spec.find(',') != std::string::npos) return std::nullopt;
  const auto dash = spec.find('-');
  if (dash == std::string::npos || spec.find('-', dash+1) != std::string::npos) return std::nullopt;
  try {
    const auto begin = spec.substr(0,dash), finish = spec.substr(dash+1);
    if (begin.empty()) {
      if (finish.empty() || finish.find_first_not_of("0123456789") != std::string::npos) return std::nullopt;
      const std::uint64_t suffix = std::stoull(finish);
      if (!suffix) return std::nullopt;
      return ByteRange{suffix >= size ? 0 : size-suffix, size-1};
    }
    if (begin.find_first_not_of("0123456789") != std::string::npos ||
        (!finish.empty() && finish.find_first_not_of("0123456789") != std::string::npos)) return std::nullopt;
    const std::uint64_t start = std::stoull(begin);
    if (start >= size) return std::nullopt;
    const std::uint64_t end = finish.empty() ? size-1 : std::min<std::uint64_t>(std::stoull(finish), size-1);
    if (end < start) return std::nullopt;
    return ByteRange{start,end};
  } catch (...) { return std::nullopt; }
}
drogon::HttpResponsePtr serve_file(const drogon::HttpRequestPtr& req,
                                  const fs::path& file, const std::string& mime) {
  if (!fs::exists(file) || !fs::is_regular_file(file))
    return failure(drogon::k404NotFound, "Media file unavailable");
  const auto size = fs::file_size(file);
  const auto range_text = req->getHeader("range");
  drogon::HttpResponsePtr resp;
  if (!range_text.empty()) {
    const auto range = parse_range(range_text, size);
    if (!range) {
      resp = failure(drogon::k416RequestedRangeNotSatisfiable, "Invalid byte range");
      resp->addHeader("Content-Range", "bytes */" + std::to_string(size));
      return resp;
    }
    const auto length = range->end - range->start + 1;
    resp = drogon::HttpResponse::newFileResponse(file.string(),
        static_cast<std::size_t>(range->start), static_cast<std::size_t>(length),
        true, "", drogon::CT_CUSTOM, mime);
    resp->setStatusCode(drogon::k206PartialContent);
    resp->addHeader("Content-Range", "bytes " + std::to_string(range->start) +
      "-" + std::to_string(range->end) + "/" + std::to_string(size));
    resp->addHeader("Content-Length", std::to_string(length));
  } else {
    resp = drogon::HttpResponse::newFileResponse(file.string(), "", drogon::CT_CUSTOM, mime);
  }
  resp->addHeader("Accept-Ranges", "bytes");
  resp->addHeader("Cache-Control", "private, max-age=60");
  resp->setAllowCompression(false);
  return resp;
}
}
void register_http_routes(ConsumerApp& app) {
  drogon::app().registerHandler("/", [&app](const drogon::HttpRequestPtr& req, Callback&& callback) {
    callback(serve_file(req, app.config_.web_root / "index.html", "text/html; charset=utf-8"));
  }, {drogon::Get});
  drogon::app().registerHandler("/style.css", [&app](const drogon::HttpRequestPtr& req, Callback&& callback) {
    callback(serve_file(req, app.config_.web_root / "style.css", "text/css; charset=utf-8"));
  }, {drogon::Get});
  drogon::app().registerHandler("/app.js", [&app](const drogon::HttpRequestPtr& req, Callback&& callback) {
    callback(serve_file(req, app.config_.web_root / "app.js", "text/javascript; charset=utf-8"));
  }, {drogon::Get});
  drogon::app().registerHandler("/health", [](const drogon::HttpRequestPtr&, Callback&& callback) {
    Json::Value data; data["ok"] = true; data["service"] = "media-upload-gallery";
    callback(json_response(data));
  }, {drogon::Get});
  drogon::app().registerHandler("/api/videos", [&app](const drogon::HttpRequestPtr&, Callback&& callback) {
    try {
      Json::Value items(Json::arrayValue);
      for (const auto& v : app.database_.ready_videos()) {
        if (fs::exists(app.uploads() / (v.id + ".mp4")) &&
            fs::exists(app.previews() / (v.id + ".jpg")) &&
            fs::exists(app.previews() / (v.id + ".mp4"))) items.append(video_json(v));
      }
      callback(json_response(items));
    } catch (const std::exception& e) { callback(failure(drogon::k500InternalServerError, e.what())); }
  }, {drogon::Get});
  drogon::app().registerHandler("/api/videos/{1}", [&app](const drogon::HttpRequestPtr&, Callback&& callback, const std::string& id) {
    try {
      if (!valid_token(id)) { callback(failure(drogon::k400BadRequest, "Invalid video ID")); return; }
      const auto video = app.database_.by_id(id);
      if (!video) { callback(failure(drogon::k404NotFound, "Unknown video ID")); return; }
      Json::Value data = video_json(*video); data["error"] = video->error;
      callback(json_response(data));
    } catch (const std::exception& e) { callback(failure(drogon::k500InternalServerError,e.what())); }
  }, {drogon::Get});
  auto media_route = [&app](const drogon::HttpRequestPtr& req, Callback&& callback,
                            const std::string& id, const std::string& kind) {
    try {
      if (!valid_token(id)) { callback(failure(drogon::k400BadRequest,"Invalid video ID")); return; }
      auto video = app.database_.by_id(id);
      if (!video || video->state != "READY") { callback(failure(drogon::k404NotFound,"Video not ready")); return; }
      const fs::path file = kind == "stream" ? app.uploads() / (video->id + ".mp4") :
        app.previews() / (video->id + (kind == "thumbnail" ? ".jpg" : ".mp4"));
      callback(serve_file(req, file, kind == "thumbnail" ? "image/jpeg" : "video/mp4"));
    } catch (const std::exception& e) { callback(failure(drogon::k500InternalServerError,e.what())); }
  };
  drogon::app().registerHandler("/api/videos/{1}/stream", [media_route](const drogon::HttpRequestPtr& r, Callback&& cb, const std::string& id) {
    media_route(r,std::move(cb),id,"stream");
  }, {drogon::Get});
  drogon::app().registerHandler("/api/videos/{1}/preview", [media_route](const drogon::HttpRequestPtr& r, Callback&& cb, const std::string& id) {
    media_route(r,std::move(cb),id,"preview");
  }, {drogon::Get});
  drogon::app().registerHandler("/api/videos/{1}/thumbnail", [media_route](const drogon::HttpRequestPtr& r, Callback&& cb, const std::string& id) {
    media_route(r,std::move(cb),id,"thumbnail");
  }, {drogon::Get});
  drogon::app().registerHandler("/api/stats", [&app](const drogon::HttpRequestPtr&, Callback&& callback) {
    try {
      Json::Value result;
      result["queue_depth"] = static_cast<Json::UInt64>(app.queue_.size());
      result["queue_capacity"] = static_cast<Json::UInt64>(app.queue_.capacity());
      result["active_workers"] = app.metrics_.active_workers.load();
      result["active_uploads"] = app.metrics_.active_uploads.load();
      result["accepted_this_run"] = static_cast<Json::UInt64>(app.metrics_.accepted.load());
      result["dropped_this_run"] = static_cast<Json::UInt64>(app.metrics_.dropped.load());
      result["duplicates_this_run"] = static_cast<Json::UInt64>(app.metrics_.duplicates.load());
      result["ready_total"] = static_cast<Json::Int64>(app.database_.count_state("READY"));
      result["failed_total"] = static_cast<Json::Int64>(app.database_.count_state("FAILED"));
      callback(json_response(result));
    } catch (const std::exception& e) { callback(failure(drogon::k500InternalServerError,e.what())); }
  }, {drogon::Get});
}
}
