# Unit tests for the identities of the four applications (Qt Core only):
#   cmake -S . -B build && cmake --build build && ./build/tst_appidentity
cmake_minimum_required(VERSION 3.16)
project(tst_appidentity LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Test)

add_executable(tst_appidentity
    tst_appidentity.cpp
    ../../src/cappidentity.h
    ../../src/cappidentity.cpp)
target_include_directories(tst_appidentity PRIVATE ../../src)
target_link_libraries(tst_appidentity PRIVATE Qt6::Core Qt6::Test)
