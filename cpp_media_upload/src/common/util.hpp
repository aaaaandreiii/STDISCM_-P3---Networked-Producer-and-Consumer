#pragma once
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

namespace media {
std::string random_hex(std::size_t nbytes = 16);
std::string sha256_hex(std::string_view text);
std::string safe_filename(const std::string& user_input);
std::string utc_now();
bool valid_token(const std::string& token);
struct CommandResult { int exit_code = -1; bool timed_out = false; std::string stdout_text; };
CommandResult run_command(const std::vector<std::string>& args, int timeout_seconds = 180, bool capture_stdout = false);
std::uint64_t file_bytes(const std::filesystem::path& path);
}
