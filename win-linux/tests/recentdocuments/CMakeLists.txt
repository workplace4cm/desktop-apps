# Unit tests for the recent-documents service (Qt Core only):
#   cmake -S . -B build && cmake --build build && ./build/tst_recentdocuments
cmake_minimum_required(VERSION 3.16)
project(tst_recentdocuments LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Test)

add_executable(tst_recentdocuments
    tst_recentdocuments.cpp
    ../../src/crecentdocuments.h
    ../../src/crecentdocuments.cpp)
target_include_directories(tst_recentdocuments PRIVATE ../../src)
target_link_libraries(tst_recentdocuments PRIVATE Qt6::Core Qt6::Test)
