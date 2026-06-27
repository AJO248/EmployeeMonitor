cmake_minimum_required(VERSION 3.10)
project(native-agent)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(native-agent src/main.cpp src/sqlite3.c)

target_compile_definitions(native-agent PRIVATE UNICODE _UNICODE SQLITE_THREADSAFE=1)

if (WIN32)
    target_link_libraries(native-agent PRIVATE crypt32 winhttp ws2_32)
endif()

target_include_directories(native-agent PRIVATE src)