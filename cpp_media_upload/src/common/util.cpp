#include "common/util.hpp"
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cctype>
#include <ctime>
#include <fcntl.h>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
extern char **environ;

namespace media {
namespace {
std::string hex(const unsigned char* buf, std::size_t size) {
  static constexpr char h[] = "0123456789abcdef";
  std::string out; out.reserve(size * 2);
  for (std::size_t i = 0; i < size; ++i) { out += h[buf[i] >> 4]; out += h[buf[i] & 15]; }
  return out;
}
}
std::string random_hex(std::size_t nbytes) {
  if (nbytes == 0 || nbytes > 64) throw std::invalid_argument("random id size out of bounds");
  std::array<unsigned char, 64> bytes{};
  if (RAND_bytes(bytes.data(), static_cast<int>(nbytes)) != 1) throw std::runtime_error("OpenSSL RAND_bytes failed");
  return hex(bytes.data(), nbytes);
}
std::string sha256_hex(std::string_view text) {
  unsigned char digest[EVP_MAX_MD_SIZE]{}; unsigned int len = 0;
  if (EVP_Digest(text.data(), text.size(), digest, &len, EVP_sha256(), nullptr) != 1)
    throw std::runtime_error("SHA-256 digest failed");
  return hex(digest, len);
}
std::string safe_filename(const std::string& name) {
  const auto base = std::filesystem::path(name).filename().string();
  std::string out; out.reserve(std::min<std::size_t>(base.size(), 200));
  for (unsigned char ch : base) {
    if (out.size() >= 200) break;
    if (ch >= 32 && ch != 127 && ch != '/' && ch != '\\') out.push_back(static_cast<char>(ch));
  }
  if (out.empty() || out == "." || out == "..") return "upload.mp4";
  return out;
}
std::string utc_now() {
  const auto t = std::time(nullptr); std::tm tm{}; gmtime_r(&t, &tm);
  char buf[32]; std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm); return buf;
}
bool valid_token(const std::string& s) {
  if (s.empty() || s.size() > 128) return false;
  for (unsigned char c : s) if (!std::isalnum(c) && c != '_' && c != '-') return false;
  return true;
}
std::uint64_t file_bytes(const std::filesystem::path& path) {
  return std::filesystem::file_size(path);
}

// Safe argv-based invocation: no shell command interpolation. POSIX/Linux only.
CommandResult run_command(const std::vector<std::string>& args, int timeout_seconds, bool capture_stdout) {
  if (args.empty()) throw std::invalid_argument("empty process command");
  std::vector<char*> argv;
  for (const auto& arg : args) argv.push_back(const_cast<char*>(arg.c_str()));
  argv.push_back(nullptr);
  posix_spawn_file_actions_t actions;
  posix_spawn_file_actions_init(&actions);
  int pipe_fd[2] = {-1, -1};
  if (capture_stdout) {
    if (pipe(pipe_fd) != 0) { posix_spawn_file_actions_destroy(&actions); throw std::runtime_error("pipe failed"); }
    posix_spawn_file_actions_adddup2(&actions, pipe_fd[1], STDOUT_FILENO);
    posix_spawn_file_actions_addclose(&actions, pipe_fd[0]);
    posix_spawn_file_actions_addclose(&actions, pipe_fd[1]);
  }
  pid_t pid = -1;
  int rc = posix_spawnp(&pid, args[0].c_str(), &actions, nullptr, argv.data(), environ);
  posix_spawn_file_actions_destroy(&actions);
  if (capture_stdout) close(pipe_fd[1]);
  if (rc != 0) {
    if (capture_stdout) close(pipe_fd[0]);
    return {-1, false, ""};
  }
  if (capture_stdout) fcntl(pipe_fd[0], F_SETFL, fcntl(pipe_fd[0], F_GETFL) | O_NONBLOCK);
  CommandResult result;
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(timeout_seconds);
  int status = 0;
  for (;;) {
    if (capture_stdout) {
      char b[512]; ssize_t n;
      while ((n = read(pipe_fd[0], b, sizeof(b))) > 0) {
        if (result.stdout_text.size() < 4096) result.stdout_text.append(b, std::min<std::size_t>(n, 4096 - result.stdout_text.size()));
      }
    }
    const pid_t w = waitpid(pid, &status, WNOHANG);
    if (w == pid) { result.exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1; break; }
    if (w < 0) { result.exit_code = -1; break; }
    if (std::chrono::steady_clock::now() > deadline) {
      kill(pid, SIGKILL); waitpid(pid, &status, 0); result.timed_out = true; result.exit_code = -1; break;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  if (capture_stdout) {
    char b[512]; ssize_t n;
    while ((n = read(pipe_fd[0], b, sizeof(b))) > 0) {
      if (result.stdout_text.size() < 4096) result.stdout_text.append(b, std::min<std::size_t>(n, 4096 - result.stdout_text.size()));
    }
    close(pipe_fd[0]);
  }
  return result;
}
}
