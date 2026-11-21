#pragma once

#include "common/util.hpp"
#include <filesystem>
#include <source_location>
#include <stdexcept>
#include <string>
#include <system_error>

namespace media::test {
inline void check(bool passed, const char* expression,
                  std::source_location location = std::source_location::current()) {
  if (!passed) {
    throw std::runtime_error(std::string(location.file_name()) + ":" +
                             std::to_string(location.line()) + ": CHECK failed: " + expression);
  }
}

class TempDirectory {
 public:
  explicit TempDirectory(const char* prefix)
      : path_(std::filesystem::temp_directory_path() / (prefix + random_hex(8))) {
    if (!std::filesystem::create_directory(path_)) {
      throw std::runtime_error("Test directory already exists: " + path_.string());
    }
  }
  ~TempDirectory() {
    std::error_code error;
    std::filesystem::remove_all(path_, error);
  }
  TempDirectory(const TempDirectory&) = delete;
  TempDirectory& operator=(const TempDirectory&) = delete;
  const std::filesystem::path& path() const { return path_; }

 private:
  std::filesystem::path path_;
};
}  // namespace media::test

#define CHECK(expression) ::media::test::check(static_cast<bool>(expression), #expression)
