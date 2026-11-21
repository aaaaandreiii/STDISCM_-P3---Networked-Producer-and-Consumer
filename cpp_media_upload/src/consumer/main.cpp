#include "consumer/app.hpp"
#include "consumer/grpc_service.hpp"
#include "consumer/http.hpp"
#include <drogon/drogon.h>
#include <grpcpp/grpcpp.h>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <memory>
#include <pthread.h>
#include <stdexcept>
#include <string>
#include <thread>
namespace {
void usage() {
  std::cout << "Usage: media_consumer [options]\n"
    "  --c N                  Number of consumer workers (default 2)\n"
    "  --q N                  Maximum WAITING queue jobs (default 5)\n"
    "  --grpc-bind HOST:PORT  gRPC bind (default 0.0.0.0:50051)\n"
    "  --http-host HOST       HTTP bind host (default 0.0.0.0)\n"
    "  --http-port PORT       HTTP port (default 8080)\n"
    "  --data PATH            Storage root (default ./data)\n"
    "  --web PATH             Frontend directory (default ./web)\n"
    "  --compress on|off      FFmpeg compression (default on)\n"
    "  --max-mb N             Maximum individual upload MiB (default 512)\n"
    "  --max-inflight N       Concurrent gRPC streams (default 8, up to 1024)\n"
    "  --ffmpeg-timeout N     Seconds per FFmpeg process (default 240)\n"
    "  --demo-delay-ms N      DEMO ONLY: artificial worker delay (default 0)\n";
}
media::ConsumerConfig parse_args(int argc, char** argv) {
  media::ConsumerConfig cfg;
  for (int i = 1; i < argc; ++i) {
    const std::string flag = argv[i];
    if (flag == "--help") { usage(); std::exit(0); }
    if (i + 1 >= argc) throw std::invalid_argument("Missing value for " + flag);
    const std::string value = argv[++i];
    if (flag == "--c") cfg.consumers = std::stoul(value);
    else if (flag == "--q") cfg.queue_capacity = std::stoul(value);
    else if (flag == "--grpc-bind") cfg.grpc_bind = value;
    else if (flag == "--http-host") cfg.http_host = value;
    else if (flag == "--http-port") cfg.http_port = std::stoi(value);
    else if (flag == "--data") cfg.data_root = value;
    else if (flag == "--web") cfg.web_root = value;
    else if (flag == "--compress") {
      if (value != "on" && value != "off") throw std::invalid_argument("--compress must be on or off");
      cfg.compress = value == "on";
    } else if (flag == "--max-mb") {
      auto n = std::stoull(value); if (n == 0 || n > 10240) throw std::invalid_argument("--max-mb out of range");
      cfg.max_file_bytes = n * 1024ULL * 1024ULL;
    } else if (flag == "--max-inflight") cfg.max_inflight = std::stoi(value);
    else if (flag == "--ffmpeg-timeout") cfg.ffmpeg_timeout = std::stoi(value);
    else if (flag == "--demo-delay-ms") cfg.demo_worker_delay_ms = std::stoi(value);
    else throw std::invalid_argument("Unknown option " + flag);
  }
  if (cfg.consumers < 1 || cfg.consumers > 64 || cfg.queue_capacity < 1 || cfg.queue_capacity > 100000 ||
      cfg.max_inflight < 1 || cfg.max_inflight > 1024 || cfg.http_port < 1 || cfg.http_port > 65535 ||
      cfg.ffmpeg_timeout < 1 || cfg.demo_worker_delay_ms < 0 || cfg.demo_worker_delay_ms > 60000)
    throw std::invalid_argument("Consumer configuration outside permitted limits");
  return cfg;
}
}
int main(int argc, char** argv) {
  try {
    const auto config = parse_args(argc, argv);
    // Block termination signals in all subsequently created threads. A detached
    // signal waiter requests graceful HTTP shutdown in a normal thread context.
    sigset_t signals; sigemptyset(&signals); sigaddset(&signals, SIGINT); sigaddset(&signals, SIGTERM);
    pthread_sigmask(SIG_BLOCK, &signals, nullptr);
    media::ConsumerApp app(config);
    app.start_workers();
    app.recover_unfinished();
    media::UploadService service(app);
    grpc::ServerBuilder builder;
    builder.AddListeningPort(config.grpc_bind, grpc::InsecureServerCredentials());
    builder.RegisterService(&service);
    builder.SetMaxReceiveMessageSize(1024 * 1024);
    auto server = builder.BuildAndStart();
    if (!server) throw std::runtime_error("Could not start gRPC server: " + config.grpc_bind);
    media::register_http_routes(app);
    std::thread([signals] {
      int signal_number = 0;
      sigwait(&signals, &signal_number);
      media::log_line("signal", "shutdown requested signal=" + std::to_string(signal_number));
      drogon::app().quit();
    }).detach();
    media::log_line("main", "gRPC=" + config.grpc_bind + " HTTP=" + config.http_host + ":" + std::to_string(config.http_port) +
      " c=" + std::to_string(config.consumers) + " q=" + std::to_string(config.queue_capacity) +
      " compression=" + (config.compress ? "on" : "off"));
    drogon::app().addListener(config.http_host, static_cast<uint16_t>(config.http_port)).setThreadNum(2).run();
    // Give active RPCs time to finish before cancelling unfinished transfers.
    // Keep workers running until all accepted jobs have drained.
    server->Shutdown(std::chrono::system_clock::now() + std::chrono::seconds(5));
    app.stop_workers();
    media::log_line("main", "shutdown complete");
  } catch (const std::exception& e) {
    std::cerr << "Consumer error: " << e.what() << '\n'; return 1;
  }
}
