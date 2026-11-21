#include "media.grpc.pb.h"
#include <grpcpp/grpcpp.h>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

namespace proto = mediaupload::v1;
using Client = proto::MediaUploadService::Stub;

void report_error(const grpc::Status& status) {
  std::cout << "rpc_error " << status.error_code() << '\n';
  std::cerr << status.error_message() << '\n';
}

void upload(Client& client, grpc::ClientContext& context, const std::string& id,
            const std::string& producer, const std::string& filename,
            const std::filesystem::path& path, const std::string& mode) {
  constexpr std::size_t chunk_limit = 256 * 1024;
  std::ifstream input(path, std::ios::binary);
  if (!input) throw std::runtime_error("Cannot open fixture: " + path.string());
  const auto size = std::filesystem::file_size(path);
  proto::UploadRequest header;
  auto* metadata = header.mutable_metadata();
  metadata->set_upload_id(id);
  metadata->set_producer_id(producer);
  metadata->set_original_filename(filename);
  auto declared = size;
  if (mode == "short") declared++;
  if (mode == "overflow") declared--;
  if (mode == "zero-size") declared = 0;
  if (mode == "large-file") declared = 4 * 1024 * 1024 + 1;
  if (mode == "large-chunk") declared = chunk_limit + 1;
  metadata->set_total_size_bytes(declared);

  proto::UploadReply reply;
  const auto writer = client.UploadVideo(&context, &reply);
  proto::UploadRequest request;
  bool writing = true;
  if (mode == "chunk-first") {
    request.set_chunk("not metadata");
    writing = writer->Write(request);
  } else {
    writing = writer->Write(header);
  }

  if (mode == "repeat-metadata" && writing) {
    writer->Write(header);
  } else if (mode == "large-chunk" && writing) {
    request.set_chunk(std::string(chunk_limit + 1, 'x'));
    writer->Write(request);
  } else if (mode == "empty-chunk" && writing) {
    request.set_chunk("");
    writer->Write(request);
  } else {
    std::string buffer(chunk_limit, '\0');
    while (writing && input) {
      input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
      const auto count = input.gcount();
      if (count == 0) break;
      request.set_chunk(buffer.data(), static_cast<std::size_t>(count));
      writing = writer->Write(request);
    }
    if (input.bad()) throw std::runtime_error("Could not read fixture: " + path.string());
  }

  if (mode == "hold") {
    if (!writing) throw std::runtime_error("Could not send held upload");
    std::cout << "held" << std::endl;
    std::string action;
    if (!std::getline(std::cin, action)) throw std::runtime_error("Missing held upload action");
    if (action == "cancel") context.TryCancel();
    else if (action != "finish") throw std::runtime_error("Unknown held upload action");
  }
  writer->WritesDone();
  const auto result = writer->Finish();
  if (!result.ok()) {
    report_error(result);
  } else {
    std::cout << "upload " << proto::UploadResult_Name(reply.result()) << ' '
              << (reply.video_id().empty() ? "-" : reply.video_id()) << ' ' << reply.queue_depth() << '\n';
    std::cerr << reply.message() << '\n';
  }
}

int main(int argc, char** argv) try {
  if (argc < 3) throw std::runtime_error("Expected TARGET and health, status or upload");
  const auto channel = grpc::CreateChannel(argv[1], grpc::InsecureChannelCredentials());
  const auto client = proto::MediaUploadService::NewStub(channel);
  const std::string command = argv[2];
  grpc::ClientContext context;
  const auto timeout = std::chrono::milliseconds(command == "upload" && argc == 9
      ? std::stoi(argv[8]) : 1000);
  context.set_deadline(std::chrono::system_clock::now() + timeout);
  if (command == "health" && argc == 3) {
    const proto::HealthRequest request;
    proto::HealthReply reply;
    const auto result = client->Health(&context, request, &reply);
    if (!result.ok()) report_error(result);
    else std::cout << "health " << reply.healthy() << ' ' << reply.service() << '\n';
  } else if (command == "status" && argc == 4) {
    proto::StatusRequest request;
    request.set_upload_id(argv[3]);
    proto::StatusReply reply;
    const auto result = client->GetUploadStatus(&context, request, &reply);
    if (!result.ok()) report_error(result);
    else if (reply.found()) std::cout << "status " << reply.state() << ' ' << reply.video_id() << '\n';
    else std::cout << "status missing\n";
  } else if (command == "upload" && argc == 9) {
    upload(*client, context, argv[3], argv[4], argv[5], argv[6], argv[7]);
  } else {
    throw std::runtime_error("Invalid test client arguments");
  }
} catch (const std::exception& error) {
  std::cerr << "gRPC test client: " << error.what() << '\n';
  return 1;
}
