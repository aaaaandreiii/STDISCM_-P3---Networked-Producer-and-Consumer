#pragma once
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <optional>
#include <utility>

namespace media {
// A bounded FIFO of waiting JOBS. In-flight uploads and active workers do not
// count against capacity. Non-blocking push drops the NEW arrival on overflow.
template<class T> class BoundedQueue {
 public:
  explicit BoundedQueue(std::size_t capacity) : capacity_(capacity) {}
  BoundedQueue(const BoundedQueue&) = delete;
  BoundedQueue& operator=(const BoundedQueue&) = delete;

  bool try_push(T job) {
    {
      std::lock_guard<std::mutex> lock(mu_);
      if (closed_ || jobs_.size() >= capacity_) return false;
      jobs_.push_back(std::move(job));
    }
    cv_.notify_one();
    return true;
  }
  // If no other thread may push, a slot present now cannot disappear: consumers
  // can only remove items. The admission coordinator serializes all pushes.
  bool has_room() const {
    std::lock_guard<std::mutex> lock(mu_);
    return !closed_ && jobs_.size() < capacity_;
  }
  std::optional<T> pop() {
    std::unique_lock<std::mutex> lock(mu_);
    cv_.wait(lock, [&] { return closed_ || !jobs_.empty(); });
    if (jobs_.empty()) return std::nullopt;
    T result = std::move(jobs_.front());
    jobs_.pop_front();
    return result;
  }
  void close() {
    {
      std::lock_guard<std::mutex> lock(mu_);
      closed_ = true;
    }
    cv_.notify_all();
  }
  std::size_t size() const {
    std::lock_guard<std::mutex> lock(mu_);
    return jobs_.size();
  }
  std::size_t capacity() const { return capacity_; }
 private:
  const std::size_t capacity_;
  mutable std::mutex mu_;
  std::condition_variable cv_;
  std::deque<T> jobs_;
  bool closed_ = false;
};
}
