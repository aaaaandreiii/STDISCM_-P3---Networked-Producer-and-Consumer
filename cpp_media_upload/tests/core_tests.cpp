#include "common/queue.hpp"
#include "common/util.hpp"
#include "common/database.hpp"
#include <atomic>
#include <cassert>
#include <filesystem>
#include <iostream>
#include <thread>
#include <vector>
namespace fs = std::filesystem;
int main() {
  { media::BoundedQueue<int> q(2);
    assert(q.has_room()); assert(q.try_push(1)); assert(q.try_push(2));
    assert(!q.has_room()); assert(!q.try_push(3)); assert(q.size()==2);
    assert(q.pop()==1); assert(q.pop()==2);
    q.close(); assert(!q.try_push(5)); assert(!q.pop().has_value());
  }
  { media::BoundedQueue<int> q(3);
    std::vector<int> received; std::thread consumer([&] {
      while (auto item = q.pop()) received.push_back(*item);
    });
    assert(q.try_push(11)); assert(q.try_push(12));
    q.close(); consumer.join(); assert(received.size()==2);
    assert(received[0]==11 && received[1]==12);
  }
  { media::BoundedQueue<int> q(10);
    std::atomic<int> processed{0}, dropped{0};
    std::vector<std::thread> consumers;
    for(int i=0;i<4;i++) consumers.emplace_back([&]{while(auto item=q.pop()) processed++;});
    std::vector<std::thread> producers;
    for(int i=0;i<8;i++) producers.emplace_back([&,i]{for(int n=0;n<1000;n++)
      if (!q.try_push(i*1000+n)) dropped++;});
    for(auto& t:producers) t.join(); q.close(); for(auto& t:consumers) t.join();
    assert(processed + dropped == 8000); assert(q.size()==0);
  }
  assert(media::sha256_hex("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  assert(media::safe_filename("../../foo.mp4") == "foo.mp4");
  assert(media::valid_token("ABC-1_a")); assert(!media::valid_token("../../etc/passwd"));
  auto root = fs::temp_directory_path()/ ("media_test_" + media::random_hex(8));
  fs::create_directories(root);
  {
    media::Database db(root/"db.sqlite");
    media::Video v;
    v.id="a"; v.upload_id="u1"; v.producer_id="producer_1";
    v.original_filename="movie.mp4"; v.sha256=media::sha256_hex("movie");
    v.temp_name="a.part"; v.original_size=100;
    assert(db.insert_queued(v));
    assert(!db.insert_queued(v));
    assert(db.by_hash(v.sha256).has_value());
    db.mark_processing("a"); assert(db.by_id("a")->state=="PROCESSING");
    db.mark_failed("a","deliberate");
    assert(!db.by_hash(v.sha256).has_value()); // failed hashes no longer claimed
    v.id="b"; v.upload_id="u2"; v.temp_name="b.part";
    assert(db.insert_queued(v));
    db.mark_ready("b",80,true);
    assert(db.by_upload_id("u2")->state=="READY");
    assert(db.ready_videos().size()==1);
    assert(db.count_state("READY")==1);
    assert(db.unfinished_videos().empty());
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
    assert(accepted == 1);
  }
  fs::remove_all(root);
  std::cout << "All core tests passed (queue, synchronization, hash, metadata).\n";
}
