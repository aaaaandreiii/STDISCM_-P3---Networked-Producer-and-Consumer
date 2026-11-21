#include "common/database.hpp"
#include "common/queue.hpp"
#include "common/util.hpp"
#include "core/test_support.hpp"
#include <atomic>
#include <iostream>
#include <thread>
#include <vector>
int main() try {
  // Deliberately check outside the macro so NDEBUG cannot hide skipped evaluation.
  int evaluations = 0;
  CHECK(++evaluations == 1);
  media::test::check(evaluations == 1, "CHECK must evaluate its expression exactly once");
  { media::BoundedQueue<int> q(2);
    CHECK(q.has_room());
    CHECK(q.try_push(1));
    CHECK(q.try_push(2));
    CHECK(!q.has_room());
    CHECK(!q.try_push(3));
    CHECK(q.size() == 2);
    CHECK(q.pop() == 1);
    CHECK(q.pop() == 2);
    q.close();
    CHECK(!q.try_push(5));
    CHECK(!q.pop().has_value());
  }
  { media::BoundedQueue<int> q(3);
    std::vector<int> received; std::thread consumer([&] {
      while (auto item = q.pop()) received.push_back(*item);
    });
    const bool pushed_first = q.try_push(11);
    const bool pushed_second = q.try_push(12);
    q.close();
    consumer.join();
    CHECK(pushed_first);
    CHECK(pushed_second);
    CHECK(received.size() == 2);
    CHECK(received[0] == 11 && received[1] == 12);
  }
  { media::BoundedQueue<int> q(10);
    std::atomic<int> processed{0}, dropped{0};
    std::vector<std::thread> consumers;
    for(int i=0;i<4;i++) consumers.emplace_back([&]{while(auto item=q.pop()) processed++;});
    std::vector<std::thread> producers;
    for(int i=0;i<8;i++) producers.emplace_back([&,i]{for(int n=0;n<1000;n++)
      if (!q.try_push(i*1000+n)) dropped++;});
    for(auto& t:producers) t.join(); q.close(); for(auto& t:consumers) t.join();
    CHECK(processed + dropped == 8000);
    CHECK(q.size() == 0);
  }
  CHECK(media::sha256_hex("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  CHECK(media::safe_filename("../../foo.mp4") == "foo.mp4");
  CHECK(media::valid_token("ABC-1_a"));
  CHECK(!media::valid_token("../../etc/passwd"));
  const media::test::TempDirectory root("media_test_");
  {
    media::Database db(root.path() / "db.sqlite");
    media::Video v;
    v.id="a"; v.upload_id="u1"; v.producer_id="producer_1";
    v.original_filename="movie.mp4"; v.sha256=media::sha256_hex("movie");
    v.temp_name="a.part"; v.original_size=100;
    CHECK(db.insert_queued(v));
    CHECK(!db.insert_queued(v));
    CHECK(db.by_hash(v.sha256).has_value());
    db.mark_processing("a");
    const auto processing = db.by_id("a");
    CHECK(processing && processing->state == "PROCESSING");
    db.mark_failed("a","deliberate");
    CHECK(!db.by_hash(v.sha256).has_value()); // failed hashes no longer claimed
    v.id="b"; v.upload_id="u2"; v.temp_name="b.part";
    CHECK(db.insert_queued(v));
    db.mark_ready("b",80,true);
    const auto ready = db.by_upload_id("u2");
    CHECK(ready && ready->state == "READY");
    CHECK(db.ready_videos().size() == 1);
    CHECK(db.count_state("READY") == 1);
    CHECK(db.unfinished_videos().empty());
    // Two concurrent admissions may not both claim the same original bytes.
    media::Video left;
    left.id = "race_a"; left.upload_id = "race_u1";
    left.producer_id = "producer_1"; left.original_filename="one.mp4";
    left.sha256 = media::sha256_hex("same-content");
    left.temp_name="race_a.part"; left.original_size = 5;
    media::Video right = left;
    right.id = "race_b"; right.upload_id = "race_u2"; right.temp_name = "race_b.part";
    std::atomic<int> accepted{0};
    std::thread t1([&] { if (db.insert_queued(left)) accepted++; });
    std::thread t2([&] { if (db.insert_queued(right)) accepted++; });
    t1.join(); t2.join();
    CHECK(accepted == 1);
  }
  std::cout << "All core tests passed (always-on checks, queue, synchronization, hash, metadata).\n";
} catch (const std::exception& error) {
  std::cerr << "Core tests failed: " << error.what() << '\n';
  return 1;
}
