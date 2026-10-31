# Unit tests for the template library checks (Qt Core only):
#   cmake -S . -B build && cmake --build build && ./build/tst_templatelibrary
cmake_minimum_required(VERSION 3.16)
project(tst_templatelibrary LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Test)

add_executable(tst_templatelibrary
    tst_templatelibrary.cpp
    ../../src/ctemplatelibrary.h
    ../../src/ctemplatelibrary.cpp)
target_include_directories(tst_templatelibrary PRIVATE ../../src)
target_compile_definitions(tst_templatelibrary PRIVATE
    FIXTURES="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
    TEMPLATES="${CMAKE_CURRENT_SOURCE_DIR}/../../../common/templates")
target_link_libraries(tst_templatelibrary PRIVATE Qt6::Core Qt6::Test)
