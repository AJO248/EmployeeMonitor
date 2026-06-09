cmake_minimum_required(VERSION 3.10)
project(native-agent)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(native-agent src/main.cpp)
target_compile_definitions(native-agent PRIVATE UNICODE _UNICODE)
if (WIN32)
	target_link_libraries(native-agent PRIVATE ws2_32 sqlite3)
else()
	target_link_libraries(native-agent PRIVATE sqlite3)
endif()
