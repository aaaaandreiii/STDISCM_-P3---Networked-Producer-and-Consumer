#pragma once
#include "consumer/app.hpp"
#include "media.grpc.pb.h"
#include <grpcpp/grpcpp.h>
namespace media {
class UploadService final : public mediaupload::v1::MediaUploadService::Service {
 public:
  explicit UploadService(ConsumerApp& app) : app_(app) {}
  grpc::Status UploadVideo(grpc::ServerContext* context,
      grpc::ServerReader<mediaupload::v1::UploadRequest>* reader,
      mediaupload::v1::UploadReply* reply) override;
  grpc::Status GetUploadStatus(grpc::ServerContext* context,
      const mediaupload::v1::StatusRequest* request,
      mediaupload::v1::StatusReply* reply) override;
  grpc::Status Health(grpc::ServerContext* context,
      const mediaupload::v1::HealthRequest* request,
      mediaupload::v1::HealthReply* reply) override;
 private:
  ConsumerApp& app_;
};
}
