cmake_minimum_required(VERSION 3.24)
project(cpp_media_upload VERSION 0.1 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(BUILD_FULL_APP "Build gRPC producer and Drogon consumer" ON)
option(BUILD_TESTING "Build portable tests for queue and storage" ON)

find_package(Threads REQUIRED)
find_package(SQLite3 REQUIRED)
find_package(OpenSSL REQUIRED)
add_library(media_core STATIC
  src/common/util.cpp
  src/common/database.cpp
)
target_include_directories(media_core PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_link_libraries(media_core PUBLIC SQLite::SQLite3 OpenSSL::Crypto Threads::Threads)
target_compile_options(media_core PRIVATE -Wall -Wextra -Wpedantic)

add_library(media_runtime STATIC src/consumer/app.cpp)
target_include_directories(media_runtime PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_link_libraries(media_runtime PUBLIC media_core)
target_compile_options(media_runtime PRIVATE -Wall -Wextra -Wpedantic)

if(BUILD_FULL_APP)
  find_package(Protobuf REQUIRED)
  find_package(gRPC CONFIG REQUIRED)
  find_package(Drogon CONFIG REQUIRED)
  if(NOT TARGET protobuf::protoc)
    message(FATAL_ERROR "BUILD_FULL_APP requires protoc (protobuf-compiler on Ubuntu)")
  endif()
  if(TARGET gRPC::grpc_cpp_plugin)
    set(GRPC_CPP_PLUGIN "$<TARGET_FILE:gRPC::grpc_cpp_plugin>")
  else()
    find_program(GRPC_CPP_PLUGIN NAMES grpc_cpp_plugin REQUIRED)
  endif()
  set(PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/proto")
  set(GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
  file(MAKE_DIRECTORY "${GEN_DIR}")
  add_library(media_proto STATIC "${PROTO_DIR}/media.proto")
  target_include_directories(media_proto PUBLIC "${GEN_DIR}")
  target_link_libraries(media_proto PUBLIC protobuf::libprotobuf gRPC::grpc++)
  # Keep generated headers directly under GEN_DIR, as the C++ sources expect.
  protobuf_generate(TARGET media_proto APPEND_PATH PROTOC_OUT_DIR "${GEN_DIR}")
  protobuf_generate(
    TARGET media_proto LANGUAGE grpc APPEND_PATH
    GENERATE_EXTENSIONS .grpc.pb.h .grpc.pb.cc
    PLUGIN "protoc-gen-grpc=${GRPC_CPP_PLUGIN}"
    PROTOC_OUT_DIR "${GEN_DIR}")

  add_executable(media_producer src/producer/main.cpp)
  target_link_libraries(media_producer PRIVATE media_core media_proto)
  add_executable(media_consumer
    src/consumer/main.cpp
    src/consumer/grpc_service.cpp
    src/consumer/http.cpp)
  target_link_libraries(media_consumer PRIVATE media_runtime media_proto Drogon::Drogon)
endif()

if(BUILD_TESTING)
  enable_testing()
  add_executable(media_core_tests tests/core_tests.cpp)
  target_link_libraries(media_core_tests PRIVATE media_core)
  add_test(NAME media_core_tests COMMAND media_core_tests)
  add_executable(media_pipeline_smoke tests/pipeline_smoke.cpp)
  target_link_libraries(media_pipeline_smoke PRIVATE media_runtime)
  add_test(NAME media_pipeline_smoke COMMAND media_pipeline_smoke)
  set_tests_properties(media_pipeline_smoke PROPERTIES SKIP_RETURN_CODE 77)
endif()
